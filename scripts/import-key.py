"""Import an armored signing key, tolerating a lost header separator when pasted."""
import subprocess
import sys

lines = sys.stdin.read().strip().splitlines()
if not lines or lines[0] != '-----BEGIN PGP PRIVATE KEY BLOCK-----':
    sys.exit('Expected an ASCII-armored private signing key.')
separator = 1
while separator < len(lines) and ':' in lines[separator]:
    separator += 1
if separator < len(lines) and lines[separator]:
    lines.insert(separator, '')
subprocess.run(['gpg', '--batch', '--import'],
               input='\n'.join(lines) + '\n', text=True, check=True)
