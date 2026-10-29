import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'tools/prepare_local_scene.py'
spec = importlib.util.spec_from_file_location('prepare_scene', MODULE)
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)


class PreparationPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.item = self.source / 'synthetic.txt'
        self.item.write_bytes(b'SYNTHETIC_PRIVACY_CANARY')
        self.destination = self.root / 'output.txt'

    def tearDown(self):
        self.temp.cleanup()

    def test_unreviewed_file_is_not_copied(self):
        with self.assertRaises(ValueError):
            prepare.copy_reviewed_file(self.item, self.destination, root=self.source, approved={})
        self.assertFalse(self.destination.exists())

    def test_changed_file_is_not_copied(self):
        approved = {'synthetic.txt': hashlib.sha256(b'previous synthetic input').hexdigest()}
        with self.assertRaises(ValueError):
            prepare.copy_reviewed_file(self.item, self.destination, root=self.source, approved=approved)
        self.assertFalse(self.destination.exists())

    def test_only_reviewed_bytes_are_copied(self):
        approved = {'synthetic.txt': hashlib.sha256(self.item.read_bytes()).hexdigest()}
        prepare.copy_reviewed_file(self.item, self.destination, root=self.source, approved=approved)
        self.assertEqual(self.destination.read_bytes(), b'SYNTHETIC_PRIVACY_CANARY')
