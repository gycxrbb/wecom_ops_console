"""Small Git source bundle entry point, never a copy of the host working directory."""
import os
import re
import shutil
from archive_protocol import unpack_entries,RESERVE

SOURCE_LIMITS={'source.json':65536,'source.bundle':512*1024**2}


def validate_source(data,expected):
    if data.get('protocol')!=2 or data.get('commit')!=expected:
        raise ValueError('Source protocol or commit mismatch')
    if set(data.get('files',{}))!={'source.bundle'}:
        raise ValueError('Unexpected source files')
    if not re.fullmatch(r'[0-9a-f]{64}',data['files']['source.bundle']):
        raise ValueError('Invalid source checksum')
    return data


def unpack_source(stream,directory,expected,disk_free=None):
    return unpack_entries(stream,directory,expected,SOURCE_LIMITS,'source.json',validate_source,disk_free)


def check_build_resources(directory):
    with open('/proc/meminfo') as source:
        memory=dict((line.split(':',1)[0],int(line.split(':',1)[1].strip().split()[0])) for line in source)
    if memory.get('MemAvailable',0)<1024*1024:
        raise ValueError('Test builder needs at least 1 GiB available memory')
    if os.getloadavg()[0]>(os.cpu_count() or 1)*4:
        raise ValueError('Test builder host load is too high')
    if shutil.disk_usage(directory).free<3*1024**3+RESERVE:
        raise ValueError('Test builder needs more disk space before building')
