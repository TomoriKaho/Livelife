import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from livelife.android_build import validate_apk, validate_config
from livelife.build_queue import BuildQueue


def config(code=1):
    ident = "b" * 32
    return dict(
        schema_version=1,
        apk_id=ident,
        build_id="apk-" + ident,
        frontend_sha="a" * 40,
        backend_sha="c" * 40,
        backend_mode="fixed",
        api_base_url="https://192.144.253.40/api/versions/be-" + "c" * 40 + "/",
        status_url="https://192.144.253.40/downloads/android/build-"
        + ident
        + "/status.json",
        version_code=code,
        version_name=f"0.1.0-test.{code}",
        expires=1900000000,
        environment="pr-42",
    )


def apk(c, extra=None):
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as z:
        for name, value in {
            "AndroidManifest.xml": b"manifest",
            "classes.dex": b"dex",
            "assets/public/index.html": b"html",
            "assets/public/native-config.json": json.dumps(c),
            **(extra or {}),
        }.items():
            z.writestr(name, value)
    return out.getvalue()


class AndroidBuildTests(unittest.TestCase):
    def test_tool_install_failure_preserves_already_verified_download_record(self):
        import importlib.util
        import tarfile
        from unittest.mock import patch

        spec = importlib.util.spec_from_file_location(
            "android_tools", Path(__file__).parents[1] / "install-android-tools.py"
        )
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w:gz") as tar:
            item = tarfile.TarInfo("jdk/bin/java")
            item.size = 4
            tar.addfile(item, io.BytesIO(b"java"))
        metadata = json.dumps(
            dict(
                java_version=[21, 0, 8],
                download_url="https://cdn.azul.com/test.tar.gz",
                sha256_hash="63f56bbb46958cf57352fba08f2755e0953799195e5545acc0c8a92920beff1e",
            )
        ).encode()
        xml = b'<sdk><remotePackage path="build-tools;36.0.0"><archives><archive><host-os>linux</host-os><complete><checksum type="sha1">hash</checksum><url>sdk.zip</url></complete></archive></archives></remotePackage></sdk>'
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(installer, "download", side_effect=[metadata, xml]),
            patch.object(
                installer,
                "verified",
                side_effect=[archive.getvalue(), RuntimeError("SDK download failed")],
            ),
        ):
            with self.assertRaises(RuntimeError):
                installer.install(Path(tmp), signing_only=True)
            record = json.loads(
                (Path(tmp) / "build-tools/android-tools.json").read_text()
            )
            self.assertEqual(record["jdk"]["version"], installer.JDK)
            self.assertEqual(set(record), {"jdk"})

    def test_invalid_binding_and_unsafe_archives_rejected(self):
        c = config()
        validate_config(c)
        validate_apk(apk(c), c)
        for fields in (
            {"api_base_url": "http://localhost:8000/"},
            {"frontend_sha": "bad"},
            {"version_code": True},
        ):
            with self.assertRaises(ValueError):
                validate_config({**c, **fields})
        for extra in ({"../evil": "bad"}, {"/absolute": "bad"}):
            with self.assertRaises(ValueError):
                validate_apk(apk(c, extra), c)
        with self.assertRaises(ValueError):
            validate_apk(apk(config(2)), c)

    def test_android_joins_global_slots_and_preserves_binding_per_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            q = BuildQueue(Path(tmp))
            base = dict(sha="a" * 40, branch="feature", run_id=10, attempt=1)
            first = q.submit({**base, "component": "android", "config": config()})
            q.submit({**base, "component": "frontend"})
            second = q.submit(
                {**base, "attempt": 2, "component": "android", "config": config(2)}
            )
            self.assertNotEqual(first["id"], second["id"])
            self.assertEqual(second["config"]["version_code"], 2)
            self.assertIsNotNone(q.claim())
            self.assertIsNotNone(q.claim())
            self.assertIsNone(q.claim())

    def test_sandbox_identity_has_no_host_home_or_accounts(self):
        import os
        from livelife.build_runner import Runner, sandbox_command

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = Runner(root)
            contents = (runner.tools / "sandbox/passwd").read_text()
            self.assertEqual(
                contents, f"sandbox:x:{os.getuid()}:{os.getgid()}::/tmp/home:/bin/sh\n"
            )
            command = sandbox_command(root, root / "workspace", ["true"])
            self.assertIn(str(runner.tools / "sandbox/passwd"), command)
            self.assertIn("--unshare-all", command)
            self.assertEqual(command[command.index("/proc") - 1], "--tmpfs")
            env = runner.environment(
                dict(sha="a" * 40, run_id=1, attempt=1, component="android")
            )
            self.assertEqual(
                env["LD_LIBRARY_PATH"],
                f"{runner.tools}/jdk/lib:{runner.tools}/jdk/lib/jli:{runner.tools}/jdk/lib/server",
            )
            self.assertNotIn("/home/group5", contents)
