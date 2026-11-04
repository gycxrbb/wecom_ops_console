"""Fetch a checksummed public-code image from the fixed domestic test distribution endpoint."""
import hashlib
import re
import shutil
import time
import urllib.parse
import urllib.request
from pathlib import Path
from archive_protocol import RESERVE


def validate_descriptor(data,expected,base):
    if data.get('protocol')!=2 or data.get('commit')!=expected:
        raise ValueError('Descriptor protocol or commit mismatch')
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',data.get('image_id','')):
        raise ValueError('Invalid descriptor image ID')
    if not re.fullmatch(r'[0-9a-f]{64}',data.get('archive_sha256','')):
        raise ValueError('Invalid archive checksum')
    if type(data.get('archive_size')) is not int or not 0<data['archive_size']<4*1024**3:
        raise ValueError('Invalid archive size')
    url=urllib.parse.urlsplit(data.get('url',''))
    allowed=urllib.parse.urlsplit(base)
    prefix=allowed.path.rstrip('/')+'/'
    if url.scheme!='https' or url.scheme!=allowed.scheme or url.netloc!=allowed.netloc:
        raise ValueError('Artifact origin is not permitted')
    suffix=url.path[len(prefix):] if url.path.startswith(prefix) else ''
    if not re.fullmatch(expected+r'-[0-9a-f]{32}/release\.tar',suffix):
        raise ValueError('Artifact path is not permitted')
    if url.username or url.password or url.query or url.fragment:
        raise ValueError('Unexpected artifact URL credentials or parameters')
    return data


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        raise ValueError('Artifact redirects are not permitted')


def fetch_archive(descriptor,directory,opener=None):
    if shutil.disk_usage(directory).free<descriptor['archive_size']+RESERVE:
        raise ValueError('Insufficient disk space for image archive')
    request=urllib.request.Request(descriptor['url'],headers={'Accept-Encoding':'identity'})
    target=Path(directory)/'download.tar'
    digest=hashlib.sha256()
    count=0
    started=time.monotonic()
    open_url=opener or urllib.request.build_opener(NoRedirect).open
    try:
        with open_url(request,timeout=60) as source, target.open('wb') as output:
            while True:
                chunk=source.read(1024*1024)
                if not chunk: break
                count+=len(chunk)
                if count>descriptor['archive_size'] or time.monotonic()-started>2700:
                    raise ValueError('Artifact transfer exceeds declared size or time limit')
                digest.update(chunk)
                output.write(chunk)
                if count%(32*1024**2)==0:
                    print('ARTIFACT_DOWNLOADED_MIB',count//1024**2,flush=True)
    except Exception as exc:
        raise ValueError('Artifact HTTPS download failed: '+type(exc).__name__)
    if count!=descriptor['archive_size'] or digest.hexdigest()!=descriptor['archive_sha256']:
        raise ValueError('Downloaded artifact size or checksum mismatch')
    return target
