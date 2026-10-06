import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import importlib.util
import io
import tarfile
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("prepare", Path(__file__).resolve().parents[1] / "prepare-backend.py")
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PackagingTests(unittest.TestCase):
    def test_uv_lock_takes_priority_over_legacy_requirements(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(prepare.dependency_format(root))
            for name in ("requirements.txt", "pyproject.toml", "uv.lock"):
                (Path(root) / name).touch()
            self.assertEqual(prepare.dependency_format(root), "uv")

    def test_bundle_contains_tracked_source_export_and_wheels(self):
        tracked = io.BytesIO()
        with tarfile.open(fileobj=tracked, mode="w") as archive:
            item = tarfile.TarInfo("backend/app/main.py")
            item.size = 7
            archive.addfile(item, io.BytesIO(b"tracked"))
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            requirements = root / "runtime.txt"
            requirements.write_text("fastapi==0.142.2\n")
            wheels = root / "wheels"
            wheels.mkdir()
            (wheels / "fastapi.whl").write_bytes(b"wheel")
            (root / "untracked-secret").write_text("must not package")
            with patch.object(prepare.subprocess, "check_output", return_value=tracked.getvalue()) as git:
                prepare.package("a" * 40, root / "backend.tgz", requirements, wheels)
                self.assertEqual(git.call_args.args[0], ["git", "archive", "--format=tar", "a" * 40, "backend"])
            with tarfile.open(root / "backend.tgz") as bundle:
                self.assertEqual(set(bundle.getnames()), {"backend/app/main.py",
                    "backend/.deploy-requirements.txt", "backend/.wheels/fastapi.whl"})


if __name__ == "__main__":
    unittest.main()
