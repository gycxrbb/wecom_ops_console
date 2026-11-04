"""Create a bounded, checksummed release from an already built immutable image."""
import gzip
import hashlib
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path

BASELINE = 'b85d526c5a3fa639ce8585d533fcc478e7aed02e'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    sha = os.environ['GITHUB_SHA']
    if not re.fullmatch(r'[0-9a-f]{40}', sha):
        raise ValueError('Full commit SHA is required')
    actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    if actual != sha:
        raise ValueError('Checkout does not match release SHA')
    subprocess.run(['git', 'merge-base', '--is-ancestor', BASELINE, sha], check=True)
    root = Path('release')
    root.mkdir(exist_ok=True)
    image_tag = 'wecom-ops-console-release:' + sha
    image = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image_tag]))[0]
    if image['Config']['Labels'].get('org.opencontainers.image.revision') != sha:
        raise ValueError('Image revision mismatch')
    subprocess.run(['git', 'bundle', 'create', str(root/'source.bundle'), BASELINE+'..HEAD'], check=True)
    process = subprocess.Popen(['docker', 'save', image_tag], stdout=subprocess.PIPE)
    with gzip.open(root/'image.tar.gz', 'wb', compresslevel=1) as target:
        while True:
            chunk = process.stdout.read(1024 * 1024)
            if not chunk:
                break
            target.write(chunk)
    if process.wait() != 0:
        raise RuntimeError('docker save failed')
    manifest = {'protocol':1, 'commit':sha, 'image_id':image['Id'], 'image_tag':image_tag,
                'architecture':image['Architecture'], 'image_size':image['Size'],
                'files':{name:digest(root/name) for name in ['source.bundle','image.tar.gz']}}
    (root/'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    with tarfile.open(root/'release.tar', 'w') as output:
        for name in ['manifest.json','source.bundle','image.tar.gz']:
            output.add(root/name, arcname=name, recursive=False)
    print('RELEASE_PACKAGED', sha, image['Id'])


if __name__ == '__main__':
    main()
