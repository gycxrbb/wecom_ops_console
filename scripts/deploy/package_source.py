"""Package only a tiny exact-commit Git bundle for the restricted test builder."""
import hashlib
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path
from package_release import BASELINE,digest

sha=os.environ['GITHUB_SHA']
if not re.fullmatch(r'[0-9a-f]{40}',sha): raise ValueError('Invalid release SHA')
actual=subprocess.check_output(['git','rev-parse','HEAD'],universal_newlines=True).strip()
if actual!=sha: raise ValueError('Checkout differs from release')
subprocess.run(['git','merge-base','--is-ancestor',BASELINE,sha],check=True)
root=Path('release');root.mkdir(exist_ok=True)
subprocess.run(['git','bundle','create','--version=2',str(root/'source.bundle'),BASELINE+'..HEAD'],check=True)
metadata={'protocol':2,'commit':sha,'files':{'source.bundle':digest(root/'source.bundle')}}
(root/'source.json').write_text(json.dumps(metadata))
with tarfile.open(str(root/'source.tar'),'w') as archive:
    for name in ['source.json','source.bundle']:
        archive.add(str(root/name),arcname=name,recursive=False)
print('SOURCE_BUNDLE_PACKAGED',sha,(root/'source.tar').stat().st_size)
