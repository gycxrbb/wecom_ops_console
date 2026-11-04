"""Bounded streaming tar protocol shared by source and image releases (Python 3.6+)."""
import hashlib
import json
import os
import shutil
import tarfile
from pathlib import Path

RESERVE = 512 * 1024**2


def unpack_entries(stream, directory, expected, limits, manifest_name, validate, disk_free=None):
    seen=set()
    manifest=None
    with tarfile.open(fileobj=stream,mode='r|') as archive:
        for member in archive:
            name=member.name
            if name not in limits or name in seen or not member.isfile():
                raise ValueError('Unexpected, repeated, or unsafe archive entry')
            if not 0 < member.size <= limits[name]:
                raise ValueError('Release entry exceeds size limit')
            if not seen and name != manifest_name:
                raise ValueError('Manifest must be the first entry')
            free=disk_free() if disk_free else shutil.disk_usage(str(directory)).free
            if free < member.size+RESERVE:
                raise ValueError('Insufficient disk space to receive release')
            source=archive.extractfile(member)
            destination=Path(directory)/name
            digest=hashlib.sha256()
            with destination.open('wb') as output:
                os.chmod(str(destination),0o600)
                while True:
                    chunk=source.read(1024*1024)
                    if not chunk: break
                    digest.update(chunk)
                    output.write(chunk)
            seen.add(name)
            if name==manifest_name:
                manifest=validate(json.loads(destination.read_text()),expected)
            elif digest.hexdigest()!=manifest['files'][name]:
                raise ValueError('Release checksum mismatch')
    if seen!=set(limits): raise ValueError('Incomplete release')
    return manifest
