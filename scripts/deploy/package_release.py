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


def create_release(sha,source_bundle,root):
    import shutil
    root=Path(root)
    root.mkdir(exist_ok=True)
    source_bundle=Path(source_bundle)
    if source_bundle.resolve()!=(root/'source.bundle').resolve():
        shutil.copyfile(str(source_bundle),str(root/'source.bundle'))
    image_tag='wecom-ops-console-release:'+sha
    image=json.loads(subprocess.check_output(['docker','image','inspect',image_tag]))[0]
    if image['Config']['Labels'].get('org.opencontainers.image.revision')!=sha:
        raise ValueError('Image revision mismatch')
    process=subprocess.Popen(['docker','save',image_tag],stdout=subprocess.PIPE)
    with gzip.open(str(root/'image.tar.gz'),'wb',compresslevel=6) as target:
        while True:
            chunk=process.stdout.read(1024*1024)
            if not chunk: break
            target.write(chunk)
    if process.wait()!=0: raise RuntimeError('docker save failed')
    manifest={'protocol':1,'commit':sha,'image_id':image['Id'],'image_tag':image_tag,
              'architecture':image['Architecture'],'image_size':image['Size'],
              'files':{name:digest(root/name) for name in ['source.bundle','image.tar.gz']}}
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2))
    with tarfile.open(str(root/'release.tar'),'w') as output:
        for name in ['manifest.json','source.bundle','image.tar.gz']:
            output.add(str(root/name),arcname=name,recursive=False)
    return manifest


if __name__=='__main__':
    import sys
    if len(sys.argv)==5 and sys.argv[1]=='--from-bundle':
        manifest=create_release(sys.argv[2],sys.argv[3],sys.argv[4])
        print('RELEASE_PACKAGED',manifest['commit'],manifest['image_id'])
    else:
        raise SystemExit('Use --from-bundle SHA BUNDLE OUTPUT_DIRECTORY')
