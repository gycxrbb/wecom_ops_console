"""Restricted SSH entry point; compatible with the test host's Python 3.6."""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

PROJECTS = {'test': '/www/wwwroot/wecom-ops-console', 'production': '/home/xr/wecom-ops-console'}
LIMITS = {'manifest.json': 65536, 'source.bundle': 512 * 1024**2, 'image.tar.gz': 3 * 1024**3}
RESERVE = 512 * 1024**2


def parse_command(command):
    match = re.fullmatch(r'deploy ([0-9a-f]{40})', command)
    if not match:
        raise ValueError('Only deploy followed by a full commit SHA is permitted')
    return match.group(1)


def validate_manifest(data, expected):
    if data.get('protocol') != 1 or data.get('commit') != expected:
        raise ValueError('Release protocol or commit mismatch')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}', data.get('image_id', '')):
        raise ValueError('Invalid image identifier')
    if data.get('image_tag') != 'wecom-ops-console-release:' + expected:
        raise ValueError('Unexpected image tag')
    if data.get('architecture') != 'amd64':
        raise ValueError('Unsupported image architecture')
    if type(data.get('image_size')) is not int or not 0 < data['image_size'] < 5 * 1024**3:
        raise ValueError('Invalid image size')
    if set(data.get('files', {})) != {'source.bundle', 'image.tar.gz'}:
        raise ValueError('Unexpected release files')
    if not all(re.fullmatch(r'[0-9a-f]{64}', h) for h in data['files'].values()):
        raise ValueError('Invalid release checksum')
    return data


def unpack(stream, directory, expected, disk_free=None):
    seen = set()
    manifest = None
    with tarfile.open(fileobj=stream, mode='r|') as archive:
        for member in archive:
            name = member.name
            if name not in LIMITS or name in seen or not member.isfile():
                raise ValueError('Unexpected, repeated, or unsafe archive entry')
            if not 0 < member.size <= LIMITS[name]:
                raise ValueError('Release entry exceeds size limit')
            if not seen and name != 'manifest.json':
                raise ValueError('Manifest must be the first entry')
            free = disk_free() if disk_free else shutil.disk_usage(str(directory)).free
            if free < member.size + RESERVE:
                raise ValueError('Insufficient disk space to receive release')
            source = archive.extractfile(member)
            destination = Path(directory) / name
            digest = hashlib.sha256()
            with destination.open('wb') as output:
                os.chmod(str(destination), 0o600)
                while True:
                    chunk = source.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    output.write(chunk)
            seen.add(name)
            if name == 'manifest.json':
                manifest = validate_manifest(json.loads(destination.read_text()), expected)
            elif digest.hexdigest() != manifest['files'][name]:
                raise ValueError('Release checksum mismatch')
    if seen != set(LIMITS):
        raise ValueError('Incomplete release')
    return manifest


def check_resources(directory, manifest):
    memory = {}
    with open('/proc/meminfo') as source:
        for line in source:
            key, value = line.split(':', 1)
            memory[key] = int(value.strip().split()[0])
    if memory.get('MemAvailable', 0) < 256 * 1024:
        raise ValueError('Host has less than 256 MiB available memory; retry later')
    if os.getloadavg()[0] > (os.cpu_count() or 1) * 4:
        raise ValueError('Host load is too high; retry after resource recovery')
    if shutil.disk_usage(directory).free < manifest['image_size'] + RESERVE:
        raise ValueError('Insufficient disk space to load image safely')


def main():
    environment = sys.argv[1]
    if environment not in PROJECTS:
        raise ValueError('Unknown deployment environment')
    sha = parse_command(os.environ.get('SSH_ORIGINAL_COMMAND', ''))
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='wecom-release-', dir='/var/tmp') as directory:
        manifest = unpack(sys.stdin.buffer, directory, sha)
        check_resources(directory, manifest)
        worker = Path(__file__).with_name('deploy.sh')
        subprocess.run(['bash', str(worker), environment, PROJECTS[environment], sha, directory], check=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('DEPLOY_FAILED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
