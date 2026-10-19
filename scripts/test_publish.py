import tempfile
import unittest
from pathlib import Path
from publish import validate_site, MAX_ASSET, MAX_FILES

class PagesLimits(unittest.TestCase):
    def test_checks_deployed_bytes_not_compressed_bundle_size(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'summary').write_bytes(b'metadata')
            self.assertEqual(validate_site(root)['files'], 1)
            with (root / 'object').open('wb') as stream:
                stream.truncate(MAX_ASSET + 1)
            with self.assertRaisesRegex(ValueError, 'limits exceeded'):
                validate_site(root)

    def test_exact_limit_is_accepted_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with (root / 'object').open('wb') as stream:
                stream.truncate(MAX_ASSET)
            self.assertEqual(validate_site(root)['largest_asset_bytes'], MAX_ASSET)
            (root / 'link').symlink_to(root / 'object')
            with self.assertRaisesRegex(ValueError, 'symlinks'):
                validate_site(root)

if __name__ == '__main__':
    unittest.main()
