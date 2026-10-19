#!/usr/bin/env python3
"""Import tested release bundles into the signed, bounded OSTree repository."""
import argparse
import base64
import json
from pathlib import Path
import subprocess
import tempfile

APP = 'com.fariszr.gseek'
URL = 'https://flatpak.fariszr.com'
ARCHES = ('x86_64', 'aarch64')
MAX_ASSET = 25 * 1024 * 1024
MAX_FILES = 20_000


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def validate_site(site):
    files = [p for p in Path(site).rglob('*') if p.is_file()]
    if any(p.is_symlink() for p in Path(site).rglob('*')):
        raise ValueError('Deployment must contain regular files, not symlinks')
    oversized = [str(p) for p in files if p.stat().st_size > MAX_ASSET]
    if oversized or len(files) > MAX_FILES:
        raise ValueError(f'Cloudflare Pages limits exceeded: {len(files)} files; oversized: {oversized}')
    return {'files': len(files), 'bytes': sum(p.stat().st_size for p in files),
            'largest_asset_bytes': max((p.stat().st_size for p in files), default=0)}


def publish(site, bundles, key, version):
    site.mkdir(parents=True, exist_ok=True)
    repo = site / 'repo'
    if not repo.exists():
        run('ostree', f'--repo={repo}', 'init', '--mode=archive-z2')
    for arch in ARCHES:
        bundle = bundles / f'gseek-{arch}.flatpak'
        # Importing through Flatpak validates bundle checksums and its app/ref.
        with tempfile.TemporaryDirectory(prefix='flatpak-import-') as temp:
            incoming = Path(temp) / 'repo'
            run('ostree', f'--repo={incoming}', 'init', '--mode=archive-z2')
            run('flatpak', 'build-import-bundle', str(incoming), str(bundle))
            ref = f'app/{APP}/{arch}/stable'
            refs = subprocess.check_output(['ostree', f'--repo={incoming}', 'refs'], text=True).splitlines()
            if refs != [ref]:
                raise ValueError(f'Unexpected release refs: {refs}')
            run('ostree', f'--repo={repo}', 'pull-local', str(incoming), ref)
        run('flatpak', 'build-sign', f'--gpg-sign={key}', str(repo), APP, 'stable', arch)
    public = subprocess.check_output(['gpg', '--export', key])
    if not public:
        raise ValueError('Signing key has no public key')
    (site / 'fariszr.gpg').write_bytes(public)
    encoded = base64.b64encode(public).decode('ascii')
    run('flatpak', 'build-update-repo', '--title=FarisZR Apps',
        '--homepage=' + URL, '--default-branch=stable', '--prune', '--prune-depth=3',
        f'--gpg-sign={key}', str(repo))
    (site / 'fariszr.flatpakrepo').write_text(f'''[Flatpak Repo]
Title=FarisZR Apps
Url={URL}/repo
Homepage={URL}
Description=Native desktop applications by FarisZR
GPGKey={encoded}
''')
    (site / 'gseek.flatpakref').write_text(f'''[Flatpak Ref]
Name={APP}
Branch=stable
Title=GSeek
Url={URL}/repo
SuggestRemoteName=fariszr
IsRuntime=false
RuntimeRepo=https://flathub.org/repo/flathub.flatpakrepo
GPGKey={encoded}
''')
    (site / 'index.html').write_text('''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FarisZR Apps</title>
<style>body{font:18px system-ui;max-width:44rem;margin:12vh auto;padding:24px;line-height:1.6;color:#222;background:#fafafa}a{color:#1c71d8}pre{padding:16px;background:#eee;overflow:auto;border-radius:12px}h1{letter-spacing:-.04em}small{color:#555}</style>
<h1>FarisZR Apps</h1><h2>GSeek</h2><p>Find your files by what you remember, from GNOME Activities.</p>
<p><a href="gseek.flatpakref">Install GSeek</a> · <a href="https://github.com/FarisZR/GSeek">About GSeek</a></p>
<p>Open the downloaded file in GNOME Software or KDE Discover, or install from a terminal:</p>
<pre>flatpak install --user https://flatpak.fariszr.com/gseek.flatpakref</pre>
<p>To add the repository:</p><pre>flatpak remote-add --user --if-not-exists fariszr https://flatpak.fariszr.com/fariszr.flatpakrepo
flatpak install --user fariszr com.fariszr.gseek</pre>
<p>Signed packages for x86-64 and ARM64. Updates arrive through your software manager or <code>flatpak update</code>.</p>
<small>This is an independent repository. It is not affiliated with Flathub.</small></html>''')
    (site / '_headers').write_text('''/repo/objects/*
  Cache-Control: public, max-age=31536000, immutable
/repo/summary*
  Cache-Control: no-cache
/repo/config
  Cache-Control: no-cache
/*.flatpakref
  Content-Type: application/vnd.flatpak.ref
  Cache-Control: no-cache
/*.flatpakrepo
  Content-Type: application/vnd.flatpak.repo
  Cache-Control: no-cache
''')
    # Cloudflare Pages must not turn missing OSTree objects into HTML via SPA fallback.
    (site / '404.html').write_text('<!doctype html><title>Not found</title><h1>Not found</h1>')
    stats = validate_site(site)
    (site / 'release.json').write_text(json.dumps({'gseek': version, 'architectures': list(ARCHES), **stats}, indent=2) + '\n')
    print(json.dumps(validate_site(site), indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--bundles', type=Path, required=True)
    parser.add_argument('--key', required=True)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    publish(args.site, args.bundles, args.key, args.version)
