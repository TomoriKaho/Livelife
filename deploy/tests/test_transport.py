import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import base64
import hashlib
import importlib.util
import io
import json
import tarfile
import tempfile
import unittest
import zipfile

from livelife.course import Course, unpack

spec = importlib.util.spec_from_file_location("actions_control", Path(__file__).resolve().parents[1] / "actions-control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


def tar_payload(name, kind=None):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w:gz") as archive:
        item = tarfile.TarInfo(name)
        if kind:
            item.type = kind
            item.linkname = "/tmp/escape"
            archive.addfile(item)
        else:
            item.size = 5
            archive.addfile(item, io.BytesIO(b"hello"))
    raw = data.getvalue()
    return base64.b64encode(raw).decode(), hashlib.sha256(raw).hexdigest()


class TransportTests(unittest.TestCase):
    def test_regular_backend_file_extracts(self):
        data, digest = tar_payload("backend/app/main.py")
        with tempfile.TemporaryDirectory() as root:
            unpack(data, root, digest)
            self.assertEqual((Path(root) / "backend/app/main.py").read_text(), "hello")

    def test_tar_traversal_absolute_links_and_foreign_directories_rejected(self):
        cases = [("backend/../../escape", None), ("/etc/config", None),
                 ("frontend/evil", None), ("backend/.venv/bin/python", None),
                 ("backend/link", tarfile.SYMTYPE), ("backend/link", tarfile.LNKTYPE)]
        for name, kind in cases:
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory() as root:
                data, digest = tar_payload(name, kind)
                with self.assertRaises(ValueError):
                    unpack(data, root, digest)

    def test_bundle_digest_is_required(self):
        data, _ = tar_payload("backend/app/main.py")
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                unpack(data, root, "0" * 64)

    def test_release_requires_offline_wheels_before_installing(self):
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode="w:gz") as archive:
            for name in ("backend/app/main.py", "backend/requirements.txt"):
                item = tarfile.TarInfo(name)
                item.size = 5
                archive.addfile(item, io.BytesIO(b"hello"))
        data = payload.getvalue()
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaisesRegex(ValueError, "missing CI wheelhouse"):
                Course(root).handle({"op": "ensure", "instance": "be-" + "a" * 40,
                    "sha": "a" * 40, "port": 18000,
                    "bundle": base64.b64encode(data).decode(), "digest": hashlib.sha256(data).hexdigest()})

    def test_skipped_backend_artifact_is_supported(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"sha": "a" * 40, "available": False}))
        manifest, bundle = control.read_artifact(out.getvalue())
        self.assertFalse(manifest["available"])
        self.assertIsNone(bundle)

    def test_artifact_cannot_ship_a_deployment_script(self):
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as archive:
            archive.writestr("manifest.json", json.dumps({"sha": "a" * 40, "available": False}))
            archive.writestr("control.sh", "exit 1")
        with self.assertRaises(ValueError):
            control.read_artifact(out.getvalue())

    def test_branch_names_become_safe_stable_owner_ids(self):
        first = control.branch_owner("29-后端/preview")
        self.assertRegex(first, r"^branch:[a-f0-9]{32}$")
        self.assertEqual(first, control.branch_owner("29-后端/preview"))
        self.assertNotEqual(first, control.branch_owner("29-backend-preview"))


if __name__ == "__main__":
    unittest.main()
