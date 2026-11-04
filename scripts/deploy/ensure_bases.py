"""Warm only missing public base images using administrator-verified Docker Hub digests."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def ensure(context,config,run=subprocess.run):
    stages=set()
    images=[]
    for line in (Path(context)/'Dockerfile').read_text(encoding='utf-8').splitlines():
        parts=line.strip().split()
        if not parts or parts[0].upper()!='FROM': continue
        image=parts[1]
        if image!='scratch' and image not in stages: images.append(image)
        if len(parts)>=4 and parts[-2].upper()=='AS': stages.add(parts[-1])
    for image in images:
        result=run(['docker','image','inspect','--format','{{.Id}}',image],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        if result.returncode==0: continue  # Never overwrite another project's existing tag.
        pin=config.get('base_images',{}).get(image)
        if not pin: raise ValueError('Missing administrator-approved base cache metadata: '+image)
        reference=pin['reference']
        if not re.fullmatch(r'm\.daocloud\.io/docker\.io/library/(?:node|python)@sha256:[0-9a-f]{64}',reference):
            raise ValueError('Unapproved base image origin or mutable tag')
        if not re.fullmatch(r'sha256:[0-9a-f]{64}',pin['config_id']):
            raise ValueError('Invalid official base config identifier')
        run(['docker','pull','--platform','linux/amd64',reference],check=True)
        result=run(['docker','image','inspect','--format','{{.Id}}',reference],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,check=True)
        if result.stdout.strip()!=pin['config_id']:
            raise ValueError('Base image differs from the verified official Docker Hub image')
        again=run(['docker','image','inspect','--format','{{.Id}}',image],stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True)
        if again.returncode!=0:
            run(['docker','tag',reference,image],check=True)
        print('APPROVED_BASE_CACHE_READY',image,flush=True)


if __name__=='__main__':
    config_path=Path(os.environ.get('WECOM_CONFIG_PATH',str(Path(__file__).with_name('config.json'))))
    ensure(Path(sys.argv[1]),json.loads(config_path.read_text()))
