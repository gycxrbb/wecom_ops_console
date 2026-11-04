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
    match = re.fullmatch(r'(?:deploy|build|fetch) ([0-9a-f]{40})', command)
    if not match:
        raise ValueError('Only deploy/build/fetch followed by a full commit SHA is permitted')
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
    from archive_protocol import unpack_entries
    return unpack_entries(stream,directory,expected,LIMITS,'manifest.json',validate_manifest,disk_free)


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
    environment=sys.argv[1]
    if environment not in PROJECTS: raise ValueError('Unknown deployment environment')
    command=os.environ.get('SSH_ORIGINAL_COMMAND','')
    sha=parse_command(command)
    action=command.split(' ',1)[0]
    if action=='build' and environment!='test':
        raise ValueError('Images may only be built on the test host')
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='wecom-release-',dir='/var/tmp') as directory:
        home=Path(__file__).parent
        if action=='build':
            from source_release import unpack_source,check_build_resources
            unpack_source(sys.stdin.buffer,directory,sha)
            check_build_resources(directory)
            subprocess.run(['bash',str(home/'build_test.sh'),PROJECTS[environment],sha,directory],check=True)
            return
        if action=='fetch':
            from fetch_release import fetch_archive,validate_descriptor
            config=json.loads((home/'config.json').read_text())
            raw=sys.stdin.buffer.read(65537)
            if len(raw)>65536: raise ValueError('Release descriptor too large')
            descriptor=validate_descriptor(json.loads(raw),sha,config['artifact_base_url'])
            archive=fetch_archive(descriptor,directory)
            with archive.open('rb') as source: manifest=unpack(source,directory,sha)
            if manifest['image_id']!=descriptor['image_id']: raise ValueError('Descriptor image mismatch')
            archive.unlink()
        else:
            manifest=unpack(sys.stdin.buffer,directory,sha)
        check_resources(directory,manifest)
        subprocess.run(['bash',str(home/'deploy.sh'),environment,PROJECTS[environment],sha,directory],check=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('DEPLOY_FAILED: ' + str(exc), file=sys.stderr)
        sys.exit(1)
