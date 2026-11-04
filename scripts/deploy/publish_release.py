"""Publish only the verified public-code release via the test site's existing HTTPS uploads route."""
import json
import os
import re
import secrets
import shutil
import sys
import time
from pathlib import Path
from package_release import digest


def prune_artifacts(public,current):
    owned=[p for p in public.iterdir() if p.is_dir() and not p.is_symlink()
           and re.fullmatch(r'[0-9a-f]{40}-[0-9a-f]{32}',p.name)]
    previous=sorted([p for p in owned if p!=current],key=lambda p:p.stat().st_mtime,reverse=True)
    keep={current.name}
    if previous: keep.add(previous[0].name)
    for child in owned:
        expired=time.time()-child.stat().st_mtime>7*86400
        if child!=current and (expired or child.name not in keep):
            if child.resolve().parent==public.resolve(): shutil.rmtree(str(child))


def publish(project,sha,release,config,state_dir):
    manifest=json.loads((release/'manifest.json').read_text())
    if manifest['commit']!=sha: raise ValueError('Published commit differs from tested commit')
    public=Path(project)/'data/uploads/pipeline-releases'
    if public.is_symlink(): raise ValueError('Artifact root may not be a symlink')
    public.mkdir(exist_ok=True)
    os.chmod(str(public),0o755)
    name=sha+'-'+secrets.token_hex(16)
    directory=public/name
    directory.mkdir()
    os.chmod(str(directory),0o755)
    partial=directory/'release.tar.part'
    shutil.move(str(release/'release.tar'),str(partial))
    target=directory/'release.tar'
    os.replace(str(partial),str(target))
    os.chmod(str(target),0o644)
    prune_artifacts(public,directory)
    descriptor={'protocol':2,'commit':sha,'image_id':manifest['image_id'],
                'url':config['artifact_base_url'].rstrip('/')+'/'+name+'/release.tar',
                'archive_size':target.stat().st_size,'archive_sha256':digest(target)}
    state=Path(state_dir)
    state.mkdir(parents=True,exist_ok=True)
    os.chmod(str(state),0o700)
    (state/('release-'+sha+'.json')).write_text(json.dumps(descriptor))
    return descriptor


if __name__=='__main__':
    config_path=Path(os.environ.get('WECOM_CONFIG_PATH',str(Path(__file__).with_name('config.json'))))
    config=json.loads(config_path.read_text())
    descriptor=publish(Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3]),config,
                       os.environ.get('WECOM_STATE_DIR','/var/lib/wecom-deploy/test'))
    print('RELEASE_DESCRIPTOR_JSON '+json.dumps(descriptor),flush=True)
