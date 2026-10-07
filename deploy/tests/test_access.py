"""Private provisioning: repeat bootstrap preserves access; rotation invalidates it."""
from pathlib import Path
import stat
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from livelife.access import configure, read_key


class PreviewKeyTests(unittest.TestCase):
    def test_repeat_provision_and_rotation(self):
        with tempfile.TemporaryDirectory() as root:
            configure(root)
            first = read_key(root)
            configure(root)
            self.assertEqual(read_key(root), first)
            configure(root, rotate=True)
            self.assertNotEqual(read_key(root), first)
            credentials = Path(root) / 'credentials'
            self.assertEqual(stat.S_IMODE(credentials.stat().st_mode), 0o700)
            for name in ['preview-key.txt', 'preview-key.conf']:
                self.assertEqual(stat.S_IMODE((credentials / name).stat().st_mode), 0o600)
            self.assertEqual((credentials / 'preview-key.conf').read_text(), f'~^{read_key(root)}$ 1;\n')

    def test_invalid_existing_secret_fails_without_replacing_it(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / 'credentials/preview-key.txt'
            path.parent.mkdir()
            path.write_text('invalid\n')
            with self.assertRaises(ValueError):
                configure(root)
            self.assertEqual(path.read_text(), 'invalid\n')
