# FarisZR Flatpak repository

Signed native desktop apps at **https://flatpak.fariszr.com**. No Flathub publication.

```sh
flatpak install --user https://flatpak.fariszr.com/gseek.flatpakref
```

Or open [GSeek’s install file](https://flatpak.fariszr.com/gseek.flatpakref) in your software manager. Both x86-64 and ARM64 use the same install link. Updates use GNOME Software, KDE Discover, or `flatpak update`.

GSeek downloads its model and official inference runtimes separately. They are not stored on Pages. The shared GNOME runtime comes from Flathub.

## Publication

GSeek’s release workflow builds and tests both architectures. This repository checks for new published releases every 15 minutes, validates the bundles, signs OSTree commits and metadata, and uploads the static repository directly to Cloudflare Pages at `flatpak.fariszr.com`. The successfully published state is retained on the `pages` branch. `flathub.fariszr.com` is an alias.

The pipeline retains three generations of repository objects, creates no static deltas, and rejects deployments above **25 MiB per file** or **20,000 files**. A missing object returns HTTP 404, and mutable OSTree metadata is never cached as an immutable asset. Pages deployment is atomic.

The public signing key is `fariszr.gpg`. Configure its matching ASCII-armored private key as the **`FLATPAK_GPG_PRIVATE_KEY`** Actions secret. Publication fails if the key does not match. Keep a secure backup: replacing the signing key requires deliberate trust rotation for installed clients. Also configure a `CLOUDFLARE_API_TOKEN` secret with Account → Cloudflare Pages → Edit for the account containing `fariszr-flatpak`. The Pages project uses direct upload and does not require a GitHub app installation.

To reproduce publication with a local GPG key:

```sh
python3 scripts/publish.py --site site --bundles release-bundles --key KEY_FINGERPRINT --version v0.2.0
```

The `pages` branch contains only public repository assets. Private keys never enter Git, release assets, or the deployment.
