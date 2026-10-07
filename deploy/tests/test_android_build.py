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
