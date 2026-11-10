import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife.course import Course, runtime_mode, source_runtime_mode
from livelife.runtime import Runtime

A = "a" * 40
IDENT = "be-" + A


class RuntimeCompatibilityTests(unittest.TestCase):
    def test_legacy_recovery_preserves_config_even_with_new_source_marker(self):
        with tempfile.TemporaryDirectory() as temporary:
            course = Course(temporary)
            release = course.releases / IDENT
            (release / "backend").mkdir(parents=True)
            (release / "backend/preview-runtime.json").write_text('{"runtime_mode":"postgres-v1"}')
            metadata = release / "release.json"
            metadata.write_text(json.dumps({"sha": A, "port": 18000}))
            config = course.supervisor.programs / f"{IDENT}.conf"
            original = "legacy command and environment\n"
            config.write_text(original)
            with (patch.object(course.supervisor, "ensure"),
                  patch.object(course.supervisor, "ctl") as ctl,
                  patch.object(course.supervisor, "configure") as configure,
                  patch("livelife.course.check_health") as health):
                result = course.handle({"op": "ensure", "instance": IDENT, "sha": A, "port": 18000})
                configure.assert_not_called()
                ctl.assert_called_once_with("start", IDENT, check=False)
                health.assert_called_once_with(18000, timeout=180, require_database=False)
            self.assertEqual(config.read_text(), original)
            self.assertEqual(result["runtime_mode"], "legacy")
            self.assertFalse((course.root / "databases").exists())
            # Explicit administrator opt-in is honored, never inferred from source.
            metadata.write_text(json.dumps({"sha": A, "port": 18000, "runtime_mode": "postgres-v1"}))
            with (patch.object(course.supervisor, "configure") as configure,
                  patch("livelife.course.check_health") as health):
                course.handle({"op": "ensure", "instance": IDENT, "sha": A, "port": 18000})
                self.assertIn("backend_runtime", configure.call_args.args[1])
                health.assert_called_once_with(18000, timeout=180, require_database=True)

    def test_missing_legacy_config_recreates_uvicorn(self):
        with tempfile.TemporaryDirectory() as temporary:
            course = Course(temporary)
            release = course.releases / IDENT
            release.mkdir()
            (release / "release.json").write_text(json.dumps({"sha": A, "port": 18000}))
            with (patch.object(course.supervisor, "configure") as configure,
                  patch("livelife.course.check_health")):
                course.handle({"op": "ensure", "instance": IDENT, "sha": A, "port": 18000})
            self.assertIn("-m uvicorn", configure.call_args.args[1])

    def test_new_bundle_persists_explicit_source_policy(self):
        for mode in (None, "postgres-v1"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                course = Course(temporary)
                def unpack(_bundle, directory, _digest):
                    backend = directory / "backend"
                    (backend / "app").mkdir(parents=True)
                    (backend / "app/main.py").touch()
                    (backend / "requirements.txt").touch()
                    (backend / ".wheels").mkdir()
                    (backend / ".wheels/test.whl").touch()
                    if mode:
                        (backend / "preview-runtime.json").write_text(json.dumps({"runtime_mode": mode}))
                with (patch("livelife.course.unpack", side_effect=unpack),
                      patch("livelife.course.subprocess.run"),
                      patch.object(course.supervisor, "configure"),
                      patch("livelife.course.check_health")):
                    course.handle({"op": "ensure", "instance": IDENT, "sha": A,
                                   "port": 18000, "bundle": "test", "digest": "test"})
                metadata = json.loads((course.releases / IDENT / "release.json").read_text())
                self.assertEqual(metadata["runtime_mode"], mode or "legacy")
                policy = course.handle({"op": "health_policy", "port": 18000})
                self.assertEqual(policy["require_database"], mode == "postgres-v1")

    def test_invalid_modes_and_missing_port_fail_closed(self):
        for mode in (None, "", "postgres-v2", True, [], {}):
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                runtime_mode({"runtime_mode": mode})
        with tempfile.TemporaryDirectory() as temporary:
            course = Course(temporary)
            with self.assertRaises(ValueError):
                course.handle({"op": "health_policy", "port": 18000})
            (Path(temporary) / "backend").mkdir()
            marker = Path(temporary) / "backend/preview-runtime.json"
            for data in ({}, [], {"runtime_mode": "bad"}):
                marker.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    source_runtime_mode(Path(temporary))

    def test_public_ensure_and_fresh_health_use_course_policy(self):
        for mode in ("legacy", "postgres-v1"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                config = {"root": temporary, "course_user": "user", "course_host": "host"}
                public = Runtime(config)
                public.supervisor = MagicMock()
                policy = {"runtime_mode": mode}
                with (patch.object(public, "rpc", return_value=policy) as rpc,
                      patch.object(public, "ssh", return_value=["ssh"]),
                      patch("livelife.runtime.check_health") as health):
                    public.ensure(IDENT, A, 18000, None)
                    self.assertEqual(rpc.call_count, 1)
                    health.assert_called_once_with(28000, require_database=mode == "postgres-v1")
                # A new controller process, as used by standalone bind, has no cache.
                fresh = Runtime(config)
                with (patch.object(fresh, "rpc", return_value=policy) as rpc,
                      patch("livelife.runtime.check_health") as health):
                    fresh.health(18000)
                    rpc.assert_called_once_with({"op": "health_policy", "port": 18000})
                    health.assert_called_once_with(28000, require_database=mode == "postgres-v1")
                with patch("livelife.runtime.check_health") as health:
                    for policy in ({}, {"runtime_mode": "unknown"}):
                        with self.assertRaises(ValueError):
                            fresh.health(18000, policy=policy)
                    health.assert_not_called()
