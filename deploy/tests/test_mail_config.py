"""SMTP configuration persistence, private files and non-disclosing failures."""

import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife import mail_config as mail

CONFIG = {
    "SMTP_HOST": "smtp.example.invalid",
    "SMTP_PORT": "465",
    "SMTP_FROM": "sender@example.invalid",
    "SMTP_USERNAME": "test-user",
    "SMTP_PASSWORD": "test-only-password",
}


class MailConfigurationTests(unittest.TestCase):
    def test_opt_in_only_and_no_parent_environment_discovery(self):
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, CONFIG):
            (Path(root) / ".env").write_text("SMTP_PASSWORD=not-a-source")
            self.assertEqual(mail.load(root), {})

    def test_private_config_survives_releases_and_updates(self):
        with tempfile.TemporaryDirectory() as root:
            config = {**CONFIG, "SMTP_PASSWORD": " password with spaces "}
            mail.save(root, config)
            for sha in ("a" * 40, "b" * 40):
                (Path(root) / "releases" / ("be-" + sha)).mkdir(parents=True)
                self.assertEqual(mail.load(root), config)
            path = Path(root) / "credentials/smtp.json"
            if os.name == "posix":
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)
                self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
            mail.save(root, {**CONFIG, "SMTP_PASSWORD": "replacement"})
            self.assertEqual(mail.load(root)["SMTP_PASSWORD"], "replacement")
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_bad_configuration_is_rejected_without_disclosing_values(self):
        invalid = [
            [],
            {**CONFIG, "GH_TOKEN": "do-not-disclose"},
            {**CONFIG, "SMTP_PORT": "0"},
            {**CONFIG, "SMTP_PORT": "65536"},
            {**CONFIG, "SMTP_PORT": True},
            {**CONFIG, "SMTP_HOST": " "},
            {**CONFIG, "SMTP_PORT": "٤٦٥"},
            {**CONFIG, "SMTP_PORT": "9" * 5000},
            {**CONFIG, "SMTP_PASSWORD": ""},
            {**CONFIG, "SMTP_PASSWORD": "do-not-disclose\n"},
            {key: value for key, value in CONFIG.items() if key != "SMTP_HOST"},
            {key: value for key, value in CONFIG.items() if key != "SMTP_USERNAME"},
        ]
        with tempfile.TemporaryDirectory() as root:
            mail.save(root, CONFIG)
            path = Path(root) / "credentials/smtp.json"
            for value in invalid:
                with self.subTest(value_type=type(value).__name__):
                    path.write_text(json.dumps(value))
                    with self.assertRaises(ValueError) as caught:
                        mail.load(root)
                    self.assertEqual(str(caught.exception), mail.INVALID)
            for content in ('{"SMTP_PASSWORD":"do-not-disclose"', "x" * 16385):
                path.write_text(content)
                with self.assertRaises(ValueError) as caught:
                    mail.load(root)
                self.assertEqual(str(caught.exception), mail.INVALID)

    @unittest.skipUnless(os.name == "posix", "requires Unix modes and symlinks")
    def test_rejects_public_permissions_and_links(self):
        with tempfile.TemporaryDirectory() as root:
            mail.save(root, CONFIG)
            path = Path(root) / "credentials/smtp.json"
            for item, mode in ((path, 0o644), (path.parent, 0o755)):
                original = item.stat().st_mode & 0o777
                item.chmod(mode)
                try:
                    with self.assertRaises(ValueError):
                        mail.load(root)
                finally:
                    item.chmod(original)
            outside = Path(root) / "outside.json"
            path.rename(outside)
            path.symlink_to(outside)
            with self.assertRaises(ValueError):
                mail.load(root)
            with self.assertRaises(ValueError):
                mail.save(root, CONFIG)
            self.assertEqual(json.loads(outside.read_text()), CONFIG)
            path.unlink()
            path.parent.rmdir()
            path.parent.symlink_to(Path(root) / "missing")
            with self.assertRaises(ValueError):
                mail.load(root)

    def test_check_reports_presence_only_and_rejects_invalid_files(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(sys, "argv", ["mail", "--root", root, "--check"]):
                with patch("sys.stdout", new_callable=io.StringIO) as out:
                    self.assertEqual(mail.main(), 1)
                    self.assertIn("not configured", out.getvalue())
                mail.save(root, CONFIG)
                with patch("sys.stdout", new_callable=io.StringIO) as out:
                    self.assertEqual(mail.main(), 0)
                    self.assertEqual(out.getvalue(), "SMTP configuration is valid\n")
                (Path(root) / "credentials/smtp.json").write_text("do-not-disclose")
                with patch("sys.stderr", new_callable=io.StringIO) as err:
                    self.assertEqual(mail.main(), 1)
                    self.assertEqual(err.getvalue(), mail.INVALID + "\n")

    def test_setup_uses_hidden_input_and_rejects_noninteractive_input(self):
        with tempfile.TemporaryDirectory() as root:
            argv = [
                "mail",
                "--root",
                root,
                "--host",
                CONFIG["SMTP_HOST"],
                "--port",
                "465",
                "--sender",
                CONFIG["SMTP_FROM"],
                "--username",
                CONFIG["SMTP_USERNAME"],
            ]
            with (
                patch.object(sys, "argv", argv),
                patch("sys.stdin.isatty", return_value=True),
                patch.object(
                    mail.getpass, "getpass", return_value=CONFIG["SMTP_PASSWORD"]
                ),
                patch("sys.stdout", new_callable=io.StringIO) as out,
            ):
                self.assertEqual(mail.main(), 0)
                self.assertNotIn(CONFIG["SMTP_PASSWORD"], out.getvalue())
                self.assertEqual(mail.load(root), CONFIG)
            with (
                patch.object(sys, "argv", argv),
                patch("sys.stdin.isatty", return_value=False),
                patch.object(mail.getpass, "getpass") as prompt,
                patch("sys.stderr", new_callable=io.StringIO),
                self.assertRaises(SystemExit),
            ):
                mail.main()
            prompt.assert_not_called()
