"""Release integrity and real shell rollback contracts, with Docker isolated by a fake CLI."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('release_receiver', ROOT/'scripts/deploy/receive.py')
receiver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receiver)
SHA = 'a'*40
BLOBS = {'source.bundle': b'bundle', 'image.tar.gz': b'image'}
MANIFEST = {'protocol':1, 'commit':SHA, 'image_id':'sha256:'+'b'*64,
            'image_tag':'wecom-ops-console-release:'+SHA, 'architecture':'amd64', 'image_size':10,
            'files':{name:hashlib.sha256(data).hexdigest() for name,data in BLOBS.items()}}


def archive(entries=None, manifest=None):
    entries = entries if entries is not None else list(BLOBS.items())
    output=io.BytesIO()
    with tarfile.open(fileobj=output,mode='w') as tar:
        for name,data in [('manifest.json',json.dumps(manifest or MANIFEST).encode())]+entries:
            info=tarfile.TarInfo(name)
            if data is None:
                info.type=tarfile.SYMTYPE
                info.linkname='/etc/passwd'
                tar.addfile(info)
            else:
                info.size=len(data)
                tar.addfile(info,io.BytesIO(data))
    output.seek(0)
    return output


class ReleaseIntegrityTests(unittest.TestCase):
    def unpack(self, stream):
        with tempfile.TemporaryDirectory() as folder:
            return receiver.unpack(stream, folder, SHA, disk_free=lambda: 10*1024**3)

    def test_valid_release(self):
        self.assertEqual(self.unpack(archive()), MANIFEST)

    def test_command_accepts_only_full_sha(self):
        self.assertEqual(receiver.parse_command('deploy '+SHA), SHA)
        for command in ['bash','deploy '+SHA+'; id','deploy '+SHA+'\n','deploy abc','deploy '+'A'*40]:
            with self.subTest(command=command), self.assertRaises(ValueError):
                receiver.parse_command(command)

    def test_manifest_commit_and_image_are_bound(self):
        for key,value in [('commit','c'*40),('image_id','latest'),('architecture','arm64'),
                          ('image_tag','other:latest'),('protocol',2),('image_size',True)]:
            data=copy.deepcopy(MANIFEST)
            data[key]=value
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.unpack(archive(manifest=data))

    def test_corrupted_image_rejected(self):
        with self.assertRaisesRegex(ValueError,'checksum'):
            self.unpack(archive([('source.bundle',b'bundle'),('image.tar.gz',b'corrupted')]))

    def test_traversal_and_symlinks_rejected(self):
        for entry in [('../escape',b'bad'),('/etc/escape',b'bad'),('source.bundle',None)]:
            with self.subTest(entry=entry), self.assertRaises(ValueError):
                self.unpack(archive([entry]))

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            self.unpack(archive(list(BLOBS.items())+[('source.bundle',b'bundle')]))

    def test_incomplete_rejected(self):
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            self.unpack(archive([('source.bundle',b'bundle')]))

    def test_disk_reserve_enforced_before_writing(self):
        with tempfile.TemporaryDirectory() as folder, self.assertRaisesRegex(ValueError,'disk space'):
            receiver.unpack(archive(),folder,SHA,disk_free=lambda: 10)

    def test_oversized_header_rejected_without_reading_body(self):
        info=tarfile.TarInfo('manifest.json')
        info.size=65537
        with self.assertRaisesRegex(ValueError,'size limit'):
            self.unpack(io.BytesIO(info.tobuf()+b'\0'*10240))


FAKE_DOCKER = r'''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
path=Path(os.environ['FAKE_DOCKER_STATE'])
s=json.loads(path.read_text())
a=sys.argv[1:]
if a[0]=='inspect':
    fmt=a[2]
    if '.Config.Image' in fmt: print('wecom-test:latest')
    elif '.State.Status' in fmt: print('running')
    elif '.State.Health' in fmt: print('unhealthy' if s['current']==s['new'] and s['fail'] else 'healthy')
    else: print(s['current'])
elif a[:2]==['image','inspect']:
    fmt=a[3]
    if '.Id' in fmt: print(s['new'])
    elif 'revision' in fmt: print(s['sha'])
    elif '.Architecture' in fmt: print('amd64')
elif a[0]=='load':
    sys.stdin.buffer.read()
    print('Loaded test image')
elif a[0]=='tag' and a[2]=='wecom-test:latest':
    s['tag']=a[1]
elif a[0]=='compose':
    s['current']=s['tag']
elif a[0]=='exec':
    sys.stdin.buffer.read()
    if s.get('probe_fail') and s['current']==s['new']: sys.exit(1)
path.write_text(json.dumps(s))
'''


@unittest.skipUnless(os.name == 'posix', 'Linux shell integration runs in CI/on the test host')
class DeploymentTransactionTests(unittest.TestCase):
    def run_scenario(self, fail=False, probe_fail=False):
        with tempfile.TemporaryDirectory(prefix='wecom-deploy-test-') as folder:
            root=Path(folder)
            project=root/'project'
            project.mkdir()
            def git(*args):
                return subprocess.check_output(['git',*args],cwd=str(project),stderr=subprocess.DEVNULL,universal_newlines=True).strip()
            git('init')
            git('config','user.name','Deployment test')
            git('config','user.email','deployment-test@example.invalid')
            (project/'marker').write_text('old')
            git('add','marker')
            git('commit','-m','old')
            old=git('rev-parse','HEAD')
            (project/'marker').write_text('new')
            git('commit','-am','new')
            sha=git('rev-parse','HEAD')
            inbox=root/'inbox'
            inbox.mkdir()
            git('bundle','create',str(inbox/'source.bundle'),old+'..HEAD')
            git('reset','--keep',old)
            with gzip.open(str(inbox/'image.tar.gz'),'wb') as image:
                image.write(b'isolated fake image stream')
            manifest=copy.deepcopy(MANIFEST)
            manifest['commit']=sha
            manifest['image_tag']='wecom-ops-console-release:'+sha
            (inbox/'manifest.json').write_text(json.dumps(manifest))
            state={'current':'sha256:'+'a'*64,'tag':'sha256:'+'a'*64,'new':MANIFEST['image_id'],
                   'sha':sha,'fail':fail,'probe_fail':probe_fail}
            state_path=root/'docker-state.json'
            state_path.write_text(json.dumps(state))
            binary=root/'bin'
            binary.mkdir()
            docker=binary/'docker'
            docker.write_text(FAKE_DOCKER)
            docker.chmod(0o755)
            env=dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'],
                     FAKE_DOCKER_STATE=str(state_path),WECOM_STATE_DIR=str(root/'state'),WECOM_HEALTH_ATTEMPTS='1')
            result=subprocess.run(['bash',str(ROOT/'scripts/deploy/deploy.sh'),'test',str(project),sha,str(inbox)],
                                  env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,universal_newlines=True,timeout=40)
            final=json.loads(state_path.read_text())
            if fail or probe_fail:
                self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(git('rev-parse','HEAD'),old)
                self.assertEqual(final['current'],state['current'])
                self.assertIn('ROLLBACK_RESTORED',result.stdout)
            else:
                self.assertEqual(result.returncode,0,result.stdout+result.stderr)
                self.assertEqual(git('rev-parse','HEAD'),sha)
                self.assertEqual(final['current'],state['new'])
                self.assertIn('DEPLOY_OK',result.stdout)

    def test_success_advances_code_and_image(self):
        self.run_scenario()

    def test_unhealthy_image_rolls_back_code_and_image(self):
        self.run_scenario(fail=True)

    def test_database_probe_failure_rolls_back_code_and_image(self):
        self.run_scenario(probe_fail=True)


if __name__ == '__main__':
    unittest.main()
