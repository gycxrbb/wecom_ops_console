"""Verify a portable image configuration digest, then return Docker's local store identifier."""
import hashlib
import json
import re
import subprocess
import sys
import tarfile

MAX_METADATA=4*1024**2


def path_digest(name):
    while name.startswith('./'): name=name[2:]
    match=re.fullmatch(r'(?:blobs/sha256/)?([0-9a-f]{64})(?:\.json)?',name)
    return 'sha256:'+match.group(1) if match else None


def configuration_id(stream,info):
    configs={}
    references=set()
    native=(info.get('Descriptor') or {}).get('digest',info['Id'])
    with tarfile.open(fileobj=stream,mode='r|') as archive:
        for member in archive:
            name=member.name
            while name.startswith('./'): name=name[2:]
            content_id=path_digest(name)
            if not member.isfile() or member.size>MAX_METADATA: continue
            if name!='manifest.json' and not content_id: continue
            raw=archive.extractfile(member).read()
            try: data=json.loads(raw)
            except (ValueError,UnicodeError): continue
            actual='sha256:'+hashlib.sha256(raw).hexdigest()
            if name=='manifest.json' and isinstance(data,list):
                references.update(path_digest(item.get('Config','')) for item in data if isinstance(item,dict))
            elif isinstance(data,dict) and content_id:
                if 'rootfs' in data:
                    if actual!=content_id: raise ValueError('Exported configuration content checksum mismatch')
                    configs[actual]=data
                elif content_id==native and actual==native:
                    config_ref=data.get('config',{}).get('digest')
                    if config_ref: references.add(config_ref)
            for digest in references:
                config=configs.get(digest)
                if not config: continue
                if config.get('architecture')!=info.get('Architecture') or config.get('os')!=info.get('Os','linux'): continue
                if config.get('rootfs',{}).get('diff_ids')!=info.get('RootFS',{}).get('Layers'): continue
                fields=[('Env',[]),('Cmd',[]),('Entrypoint',[]),('WorkingDir',''),('User',''),('Labels',{}),('ExposedPorts',{}),('Volumes',{})]
                if any((config.get('config',{}).get(key) or default)!=(info.get('Config',{}).get(key) or default) for key,default in fields): continue
                return digest
    raise ValueError('No referenced configuration matches the inspected filesystem and runtime configuration')


def verified_image_id(reference,expected,revision=None):
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',expected): raise ValueError('Invalid expected configuration digest')
    info=json.loads(subprocess.check_output(['docker','image','inspect',reference],stderr=subprocess.PIPE))[0]
    if info.get('Architecture')!='amd64' or info.get('Os','linux')!='linux':
        raise ValueError('Expected a linux/amd64 image')
    if revision is not None and (info.get('Config',{}).get('Labels') or {}).get('org.opencontainers.image.revision')!=revision:
        raise ValueError('Image revision label mismatch')
    native=info['Id']
    if native==expected: return native
    # Docker 29/containerd reports the manifest digest as .Id. Verify the original
    # config blob and its manifest reference, filesystem and effective settings.
    process=subprocess.Popen(['docker','image','save',reference],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
    try:
        actual=configuration_id(process.stdout,info)
    finally:
        process.stdout.close()
        if process.poll() is None: process.terminate()
        try: process.wait(timeout=15)
        except subprocess.TimeoutExpired: process.kill();process.wait()
    if actual!=expected: raise ValueError('Image configuration digest mismatch')
    return native


if __name__=='__main__':
    try:
        print(verified_image_id(sys.argv[1],sys.argv[2],sys.argv[3] if len(sys.argv)>3 else None))
    except Exception as exc:
        print('IMAGE_IDENTITY_REJECTED: '+str(exc),file=sys.stderr)
        sys.exit(1)
