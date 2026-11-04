"""Send only source or a small release descriptor across the overseas SSH link."""
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path


def main():
    sha=os.environ['GITHUB_SHA']
    host=os.environ['DEPLOY_HOST']
    mode=os.environ['DEPLOY_MODE']
    if not re.fullmatch(r'[0-9a-f]{40}',sha) or not re.fullmatch(r'[0-9.]+',host) or mode not in ['build','fetch']:
        raise ValueError('Invalid target, mode, or release')
    with tempfile.TemporaryDirectory(prefix='wecom-ssh-') as directory:
        key=Path(directory)/'id_ed25519'
        known=Path(directory)/'known_hosts'
        key.write_text(os.environ['SSH_PRIVATE_KEY'].strip()+'\n')
        known.write_text(os.environ['SSH_KNOWN_HOSTS'].strip()+'\n')
        os.chmod(str(key),0o600)
        os.chmod(str(known),0o600)
        command=['ssh','-i',str(key),'-o','BatchMode=yes','-o','IdentitiesOnly=yes',
                 '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),
                 '-o','ConnectTimeout=20','-o','ServerAliveInterval=15',
                 '-o','ServerAliveCountMax=4','root@'+host,mode+' '+sha]
        filename='source.tar' if mode=='build' else 'release-descriptor.json'
        descriptor=None
        with (Path('release')/filename).open('rb') as source:
            process=subprocess.Popen(command,stdin=source,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
            for raw in process.stdout:
                line=raw.decode('utf-8',errors='replace').rstrip()
                if line.startswith('RELEASE_DESCRIPTOR_JSON '):
                    descriptor=json.loads(line.split(' ',1)[1])
                    if descriptor.get('commit')!=sha: raise ValueError('Returned release mismatch')
                else:
                    print(line,flush=True)
            if process.wait()!=0: raise RuntimeError('Remote deployment failed')
        if mode=='build':
            if descriptor is None: raise RuntimeError('Test did not publish a release descriptor')
            (Path('release')/'release-descriptor.json').write_text(json.dumps(descriptor,indent=2))
            print('TEST_RELEASE_READY',sha,descriptor['image_id'])


if __name__=='__main__':
    main()
