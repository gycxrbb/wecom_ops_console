"""Send an artifact over a pinned SSH connection; secrets never enter command arguments."""
import os
import re
import subprocess
import tempfile
from pathlib import Path


def main():
    sha = os.environ['GITHUB_SHA']
    host = os.environ['DEPLOY_HOST']
    if not re.fullmatch(r'[0-9a-f]{40}', sha) or not re.fullmatch(r'[0-9.]+', host):
        raise ValueError('Invalid target or release')
    with tempfile.TemporaryDirectory(prefix='wecom-ssh-') as directory:
        key = Path(directory)/'id_ed25519'
        known = Path(directory)/'known_hosts'
        key.write_text(os.environ['SSH_PRIVATE_KEY'].strip()+'\n')
        known.write_text(os.environ['SSH_KNOWN_HOSTS'].strip()+'\n')
        os.chmod(key, 0o600)
        os.chmod(known, 0o600)
        command = ['ssh','-i',str(key),'-o','BatchMode=yes','-o','IdentitiesOnly=yes',
                   '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(known),
                   '-o','ConnectTimeout=20','-o','ServerAliveInterval=15',
                   '-o','ServerAliveCountMax=4','root@'+host,'deploy '+sha]
        with Path('release/release.tar').open('rb') as source:
            subprocess.run(command, stdin=source, check=True)


if __name__ == '__main__':
    main()
