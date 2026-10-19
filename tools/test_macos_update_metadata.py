import tempfile
import unittest
from pathlib import Path

import yaml
from merge_macos_update_metadata import merge_metadata


class MacMetadataTests(unittest.TestCase):
    def test_both_architectures_keep_their_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for label, digest in [('macos-arm64-apple-silicon', 'arm-hash'), ('macos-x64-intel', 'intel-hash')]:
                directory = root / f'update-metadata-{label}'
                directory.mkdir()
                (directory / 'latest-mac.yml').write_text(yaml.safe_dump({
                    'version': '2.0.0', 'path': 'old.zip', 'sha512': digest,
                    'files': [{'url': 'old.zip', 'sha512': digest, 'size': 123}],
                }))
            result = merge_metadata(root, '2.0.0')
            self.assertEqual([f['url'] for f in result['files']], [
                'freemocap_2.0.0_macos-arm64-apple-silicon.zip', 'freemocap_2.0.0_macos-x64-intel.zip'])
            self.assertEqual([f['sha512'] for f in result['files']], ['arm-hash', 'intel-hash'])
            with self.assertRaisesRegex(ValueError, 'version mismatch'):
                merge_metadata(root, '3.0.0')

    def test_missing_architecture_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'Expected one'):
                merge_metadata(Path(tmp), '2.0.0')
