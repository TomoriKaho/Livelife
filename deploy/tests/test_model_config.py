import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife import model_config
from livelife.common import atomic_json


class ModelConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.directory = self.root / "credentials"
        self.directory.mkdir(mode=0o700)
        self.path = self.directory / "model.json"
        self.value = {
            "trusted_shas": ["a" * 40],
            "environment": {
                "AGENT_LLM_BASE_URL": "https://api.example.test/v1",
                "AGENT_LLM_API_KEY": "test-secret",
                "AGENT_LLM_MODEL": "test-model",
                "AGENT_LLM_REASONING_EFFORT": "high",
                "HTTPS_PROXY": "http://test:secret@127.0.0.1:17890",
            },
        }

    def test_only_exact_trusted_version_receives_environment(self):
        self.assertEqual(model_config.load(self.root, "be-" + "a" * 40), {})
        atomic_json(self.path, self.value)
        result = model_config.load(self.root, "be-" + "a" * 40)
        self.assertEqual(result["AGENT_LLM_API_KEY"], "test-secret")
        self.assertEqual(result["NO_PROXY"], "localhost,127.0.0.1,::1")
        for ident in ("be-" + "b" * 40, "a" * 40, "main", "*"):
            self.assertEqual(model_config.load(self.root, ident), {})

    def test_rejects_links_permissions_and_corrupt_json_without_secret(self):
        atomic_json(self.path, self.value)
        self.path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "^" + model_config.INVALID + "$"):
            model_config.load(self.root, "be-" + "a" * 40)
        self.path.chmod(0o600)
        self.path.write_text('{"test-secret": invalid')
        with self.assertRaisesRegex(ValueError, "^" + model_config.INVALID + "$"):
            model_config.load(self.root, "be-" + "a" * 40)
        self.path.unlink()
        self.path.symlink_to(self.root / "absent")
        with self.assertRaises(ValueError):
            model_config.load(self.root, "be-" + "a" * 40)
        self.path.unlink()
        self.directory.rmdir()
        self.directory.symlink_to(self.root / "absent")
        with self.assertRaises(ValueError):
            model_config.load(self.root, "be-" + "a" * 40)

    def test_rejects_wildcards_arbitrary_environment_and_unsafe_values(self):
        for key, value in (
            ("PYTHONPATH", "/test"),
            ("AUTH_TEST_LOGIN_ENABLED", "true"),
            ("AGENT_LLM_BASE_URL", "http://example.test"),
            ("AGENT_LLM_API_KEY", "secret\nvalue"),
            ("HTTPS_PROXY", "http://example.test:123"),
            ("AGENT_LLM_REASONING_EFFORT", "invalid"),
            ("AGENT_LLM_TIMEOUT_SECONDS", "0"),
        ):
            candidate = json.loads(json.dumps(self.value))
            candidate["environment"][key] = value
            atomic_json(self.path, candidate)
            with self.subTest(key=key), self.assertRaises(ValueError):
                model_config.load(self.root, "be-" + "a" * 40)
        self.value["trusted_shas"] = ["*"]
        atomic_json(self.path, self.value)
        with self.assertRaises(ValueError):
            model_config.load(self.root, "be-" + "a" * 40)
