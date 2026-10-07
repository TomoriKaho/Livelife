import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from livelife.registry import Registry
from test_registry import Runtime, A, B, C
from test_android_build import apk


class ApkTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.now = 1000
        self.runtime = Runtime()
        self.r = Registry(
            Path(self.temp.name) / "state",
            self.runtime,
            "https://192.144.253.40",
            grace=10,
            clock=lambda: self.now,
        )
        self.r.deploy("main", A, 1, b"bundle")
        self.r.deploy("pr:42", B, 1, b"bundle")
        self.r.deploy("pr:43", C, 1, b"bundle")

    def reserve(self, gen=10, **extra):
        return self.r.apks.reserve(
            dict(
                environment="pr-42",
                branch="feature",
                sha=A,
                generation=gen,
                target="be-" + B,
                mode="fixed",
                **extra,
            )
        )

    def publish(self, result, fail=False):
        config = {
            k: v
            for k, v in result.items()
            if k
            in (
                "schema_version",
                "apk_id",
                "build_id",
                "frontend_sha",
                "version_code",
                "version_name",
                "environment",
                "api_base_url",
                "backend_mode",
                "backend_sha",
                "status_url",
                "expires",
            )
        }
        data = apk(config)

        def sign(directory, c):
            path = directory / f"livelife-test-{c['version_code']}.apk"
            path.write_bytes(data)
            return path

        with (
            patch.object(
                self.runtime,
                "rpc",
                return_value={
                    "bundle": __import__("base64").b64encode(data).decode(),
                    "manifest": {
                        "config": config,
                        "digest": hashlib.sha256(data).hexdigest(),
                    },
                },
                create=True,
            ),
            patch.object(self.r.apks, "sign", side_effect=sign),
            patch.object(self.r.apks, "write_page"),
        ):
            self.runtime.fail_publish = fail
            return self.r.apks.publish_built(
                {"apk_id": result["apk_id"], "job": "b" * 32}
            )

    def test_fixed_binding_reuse_and_independent_apk_reference(self):
        first = self.reserve(explicit=True)
        self.publish(first)
        self.r.release("pr:42", 11)
        self.assertIn(
            "apk:" + first["apk_id"], [r["owner"] for r in self.r.snapshot()["refs"]]
        )
        next_ = self.r.apks.reserve(
            dict(
                environment="pr-42",
                branch="feature",
                sha=C,
                generation=12,
                target="be-" + C,
                mode="own",
            )
        )
        self.assertEqual(next_["backend_sha"], B)
        self.assertEqual(next_["backend_mode"], "fixed")
        self.assertGreater(next_["version_code"], first["version_code"])

    def test_close_tombstone_and_reopen(self):
        first = self.reserve()
        self.r.apks.release("pr-42", 20)
        self.assertEqual(self.r.apks.lookup("pr-42")["status"], "released")
        self.assertEqual(self.reserve(gen=19)["status"], "superseded")
        reopened = self.reserve(gen=21)
        self.assertGreater(reopened["version_code"], first["version_code"])
        self.assertNotIn(
            "apk:" + first["apk_id"], [r["owner"] for r in self.r.snapshot()["refs"]]
        )

    def test_new_failure_keeps_previous_success_and_releases_candidate(self):
        first = self.reserve()
        self.publish(first)
        second = self.reserve(gen=11, force=True)
        with self.assertRaises(RuntimeError):
            self.publish(second, fail=True)
        self.r.apks.fail(second["apk_id"], "gateway failure")
        result = self.r.apks.lookup("pr-42")
        self.assertEqual(result["status"], "failure")
        self.assertEqual(result["last_success"]["apk_id"], first["apk_id"])
        refs = [r["owner"] for r in self.r.snapshot()["refs"]]
        self.assertIn("apk:" + first["apk_id"], refs)
        self.assertNotIn("apk:" + second["apk_id"], refs)
        self.assertTrue(
            (
                self.r.apks.root
                / first["apk_id"]
                / f"livelife-test-{first['version_code']}.apk"
            ).exists()
        )

    def test_expiry_and_main_retention(self):
        first = self.reserve()
        self.publish(first)
        main = self.r.apks.reserve(
            dict(
                environment="main",
                branch="main",
                sha=A,
                generation=12,
                target="staging",
                mode="staging",
            )
        )
        self.publish(main)
        self.now += 8 * 86400
        self.r.collect()
        self.r.apks.prune_files()
        self.assertEqual(self.r.apks.lookup("pr-42")["status"], "expired")
        self.assertEqual(self.r.apks.lookup("main")["status"], "ready")
        self.assertFalse(list((self.r.apks.root / first["apk_id"]).glob("*.apk")))

    def test_reruns_increment_code_but_duplicate_notifications_reuse(self):
        first = self.reserve()
        same = self.reserve(gen=11)
        self.assertEqual(same["apk_id"], first["apk_id"])
        rerun = self.reserve(gen=12, force=True)
        self.assertGreater(rerun["version_code"], first["version_code"])

    def test_interrupted_candidates_recover_and_release(self):
        first = self.reserve()
        self.now += 7201
        self.r.recover()
        self.assertEqual(self.r.apks.lookup("pr-42")["status"], "failure")
        self.assertNotIn(
            "apk:" + first["apk_id"], [r["owner"] for r in self.r.snapshot()["refs"]]
        )

    def test_capacity_rejection_does_not_replace_current_or_drop_its_reference(self):
        first = self.reserve()
        self.publish(first)
        second = self.reserve(gen=11, force=True)
        with patch("livelife.apks.MAX_STORAGE", 1), self.assertRaises(ValueError):
            self.publish(second)
        self.r.apks.fail(second["apk_id"], "capacity")
        self.assertEqual(
            self.r.apks.lookup("pr-42")["last_success"]["apk_id"], first["apk_id"]
        )
        self.assertIn(
            "apk:" + first["apk_id"], [r["owner"] for r in self.r.snapshot()["refs"]]
        )
