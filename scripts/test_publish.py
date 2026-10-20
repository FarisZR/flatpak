import tempfile
import unittest
from pathlib import Path
from publish import validate_site, MAX_ASSET, MAX_FILES

class RepositoryInputs(unittest.TestCase):
    def test_archive_rejects_links_and_unexpected_members(self):
        import io
        import tarfile
        from publish import unpack_bundles
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for linked in [False, True]:
                archive = root / 'inputs.tar'
                with tarfile.open(archive, 'w') as inputs:
                    for name in ['gseek-x86_64.flatpak', 'gseek-aarch64.flatpak', *([] if linked else ['../unexpected'])]:
                        member = tarfile.TarInfo(name)
                        if linked:
                            member.type = tarfile.SYMTYPE
                            member.linkname = '../outside'
                            inputs.addfile(member)
                        else:
                            member.size = 1
                            inputs.addfile(member, io.BytesIO(b'x'))
                with self.assertRaisesRegex(ValueError, 'exactly'):
                    unpack_bundles(archive, root)

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

class SignedRepository(unittest.TestCase):
    @unittest.skipUnless(__import__('shutil').which('flatpak'), 'Needs Flatpak and OSTree')
    def test_both_architectures_are_imported_signed_and_trusted_by_flatpak(self):
        import os
        import subprocess
        from unittest.mock import patch
        from publish import publish, APP, ARCHES
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            keyring = root / 'gnupg'
            keyring.mkdir(mode=0o700)
            env = {**os.environ, 'GNUPGHOME': str(keyring), 'FLATPAK_USER_DIR': str(root / 'user')}
            def command(*args):
                result = subprocess.run(args, env=env, capture_output=True, text=True)
                if result.returncode: raise RuntimeError(f'{args[0]} failed: {result.stderr}')
                return result.stdout
            command('gpg', '--batch', '--pinentry-mode', 'loopback', '--passphrase', '', '--quick-generate-key', 'Repository CI <ci@example.invalid>', 'ed25519', 'sign', '0')
            key = next(line.split(':')[9] for line in command('gpg', '--with-colons', '--list-secret-keys').splitlines() if line.startswith('fpr:'))
            bundles = root / 'bundles'
            bundles.mkdir()
            for arch in ARCHES:
                build = root / arch
                (build / 'files/bin').mkdir(parents=True)
                (build / 'export').mkdir()
                (build / 'metadata').write_text(f'[Application]\nname={APP}\nruntime=org.gnome.Platform/{arch}/51\nsdk=org.gnome.Sdk/{arch}/51\ncommand=gseek\n')
                program = build / 'files/bin/gseek'
                program.write_text('#!/bin/sh\nprintf "Repository CI fixture\\n"\n')
                program.chmod(0o755)
                incoming = root / f'incoming-{arch}'
                command('flatpak', 'build-export', f'--arch={arch}', str(incoming), str(build), 'stable')
                command('flatpak', 'build-bundle', f'--arch={arch}', str(incoming), str(bundles / f'gseek-{arch}.flatpak'), APP, 'stable')
            with patch.dict(os.environ, env):
                import tarfile
                with tarfile.open(bundles / 'gseek-repository-inputs.tar', 'w') as archive:
                    for bundle in sorted(bundles.glob('*.flatpak')):
                        archive.add(bundle, arcname=bundle.name)
                        bundle.unlink()
                publish(root / 'site', bundles, key, 'v0.0.0-test')
            site = root / 'site'
            command('flatpak', 'remote-add', '--user', '--gpg-import=' + str(site / 'fariszr.gpg'), 'signed-ci', str(site / 'repo'))
            for arch in ARCHES:
                commit = command('flatpak', 'remote-info', '--user', f'--arch={arch}', '--show-commit', 'signed-ci', APP).strip()
                self.assertEqual(len(commit), 64)
            installer = root / 'gseek.flatpakref'
            installer.write_text((site / 'gseek.flatpakref').read_text().replace(
                'Url=https://flatpak.fariszr.com/repo', 'Url=' + (site / 'repo').as_uri()))
            command('flatpak', 'install', '--user', '--noninteractive', '--no-deps', '--no-related', '-y', str(installer))
            origin = command('flatpak', 'info', '--user', '--show-origin', APP).strip()
            self.assertEqual(command('flatpak', 'info', '--user', '--show-commit', APP).strip(),
                command('flatpak', 'remote-info', '--user', '--show-commit', origin, APP).strip())
            self.assertEqual(validate_site(site)['files'] > 0, True)
            self.assertIn('GPGKey=', (site / 'gseek.flatpakref').read_text())
            self.assertFalse((site / 'repo/deltas').exists() and any((site / 'repo/deltas').iterdir()))
