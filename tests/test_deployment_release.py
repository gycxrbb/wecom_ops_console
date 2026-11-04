"""Release integrity and real shell rollback contracts, with Docker isolated by a fake CLI."""
import copy
import gzip
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/deploy'))
SPEC = importlib.util.spec_from_file_location('release_receiver', ROOT/'scripts/deploy/receive.py')
receiver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receiver)
from source_release import unpack_source
from fetch_release import validate_descriptor,fetch_archive,NoRedirect
from publish_release import prune_artifacts
from ensure_bases import ensure
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
        for action in ['deploy','build','fetch']:
            self.assertEqual(receiver.parse_command(action+' '+SHA),SHA)
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


class SourceAndFetchTests(unittest.TestCase):
    def test_source_bundle_is_small_and_checksummed(self):
        metadata={'protocol':2,'commit':SHA,'files':{'source.bundle':hashlib.sha256(b'bundle').hexdigest()}}
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as tar:
            for name,value in [('source.json',json.dumps(metadata).encode()),('source.bundle',b'bundle')]:
                item=tarfile.TarInfo(name);item.size=len(value)
                tar.addfile(item,io.BytesIO(value))
        stream.seek(0)
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(unpack_source(stream,directory,SHA,disk_free=lambda:10*1024**3),metadata)

    def descriptor(self,data=b'archive'):
        return {'protocol':2,'commit':SHA,'image_id':'sha256:'+'b'*64,
                'url':'https://gezelling.com/uploads/pipeline-releases/'+SHA+'-'+'c'*32+'/release.tar',
                'archive_size':len(data),'archive_sha256':hashlib.sha256(data).hexdigest()}

    def test_fixed_origin_prevents_ssrf_and_path_escape(self):
        base='https://gezelling.com/uploads/pipeline-releases'
        metadata=self.descriptor()
        self.assertEqual(validate_descriptor(metadata,SHA,base),metadata)
        for url in ['http://169.254.169.254/latest/meta-data/',
                    metadata['url'].replace('gezelling.com','evil.example'),
                    metadata['url'].replace('https://','http://'),
                    metadata['url']+'?token=unexpected',
                    metadata['url'].replace('/release.tar','/../private')]:
            with self.subTest(url=url),self.assertRaises(ValueError):
                validate_descriptor(dict(metadata,url=url),SHA,base)

    def test_download_verifies_size_and_checksum(self):
        with tempfile.TemporaryDirectory() as directory:
            path=fetch_archive(self.descriptor(),directory,opener=lambda req,timeout:io.BytesIO(b'archive'))
            self.assertEqual(path.read_bytes(),b'archive')
        with tempfile.TemporaryDirectory() as directory,self.assertRaisesRegex(ValueError,'checksum'):
            fetch_archive(self.descriptor(),directory,opener=lambda req,timeout:io.BytesIO(b'corrupt'))

    def test_artifact_cleanup_preserves_user_assets_and_current_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            old=root/('a'*40+'-'+'a'*32);old.mkdir()
            previous=root/('b'*40+'-'+'b'*32);previous.mkdir()
            current=root/('c'*40+'-'+'c'*32);current.mkdir()
            user=root/'user-assets';user.mkdir()
            os.utime(str(old),(1,1));os.utime(str(previous),(2**31-1,2**31-1))
            prune_artifacts(root,current)
            self.assertFalse(old.exists())
            self.assertTrue(previous.exists())
            self.assertTrue(current.exists())
            self.assertTrue(user.exists())

    def test_redirects_do_not_escape_the_fixed_origin(self):
        with self.assertRaises(ValueError):
            NoRedirect().redirect_request(None,None,302,'redirect',{},'http://169.254.169.254/')


class BaseCacheTests(unittest.TestCase):
    def scenario(self,cached=False,mismatch=False):
        calls=[]
        reference='m.daocloud.io/docker.io/library/node@sha256:'+'a'*64
        config={'base_images':{'node:18-alpine':{'reference':reference,'config_id':'sha256:'+'b'*64}}}
        def run(args,**kwargs):
            calls.append(args)
            if args[1:3]==['image','inspect']:
                if args[-1]=='node:18-alpine':
                    return subprocess.CompletedProcess(args,0 if cached else 1,stdout='existing\n',stderr='')
                return subprocess.CompletedProcess(args,0,stdout='sha256:'+('c' if mismatch else 'b')*64+'\n',stderr='')
            return subprocess.CompletedProcess(args,0,stdout='',stderr='')
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory)/'Dockerfile').write_text('FROM node:18-alpine AS frontend-builder\n')
            if mismatch:
                with self.assertRaisesRegex(ValueError,'differs'):
                    ensure(Path(directory),config,run)
                self.assertFalse(any(args[1]=='tag' for args in calls))
            else:
                ensure(Path(directory),config,run)
        return calls

    def test_existing_base_tag_is_not_replaced(self):
        calls=self.scenario(cached=True)
        self.assertFalse(any(args[1] in ['pull','tag'] for args in calls))

    def test_missing_base_is_verified_before_tagging(self):
        calls=self.scenario()
        self.assertTrue(any(args[1]=='pull' and '@sha256:' in args[-1] for args in calls))
        self.assertEqual(calls[-1][1],'tag')

    def test_mismatched_proxy_image_is_not_trusted(self):
        self.scenario(mismatch=True)


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
    if a[-1] in ['node:18-alpine','python:3.11-slim']:
        print('sha256:'+'c'*64); sys.exit(0)
    if not s.get('has_image'): sys.exit(1)
    if '--format' not in a:
        print(json.dumps([{'Id':s['new'],'Config':{'Labels':{'org.opencontainers.image.revision':s['sha']}},'Architecture':'amd64','Size':10}]))
        sys.exit(0)
    fmt=a[3]
    if '.Id' in fmt: print(s['new'])
    elif 'revision' in fmt: print(s['sha'])
    elif '.Architecture' in fmt: print('amd64')
elif a[0]=='load':
    sys.stdin.buffer.read()
    s['has_image']=True
    print('Loaded test image')
elif a[0]=='build':
    context=Path(a[-1])
    s['build_context_entries']=[str(p.relative_to(context)) for p in context.rglob('*') if p.is_file()]
    s['has_image']=True
elif a[0]=='save':
    sys.stdout.buffer.write(b'fake-docker-image')
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
    def run_scenario(self, fail=False, probe_fail=False, build=False):
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
            (project/'Dockerfile').write_text('FROM scratch\n')
            git('add','marker','Dockerfile')
            git('commit','-m','old')
            old=git('rev-parse','HEAD')
            (project/'marker').write_text('new')
            git('commit','-am','new')
            sha=git('rev-parse','HEAD')
            inbox=root/'inbox'
            inbox.mkdir()
            git('bundle','create',str(inbox/'source.bundle'),old+'..HEAD')
            git('reset','--keep',old)
            (project/'.env').write_text('SYNTHETIC_SECRET=not-for-build-context')
            (project/'data/uploads').mkdir(parents=True)
            config=root/'config.json'
            config.write_text(json.dumps({'artifact_base_url':'https://gezelling.com/uploads/pipeline-releases'}))
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
                     FAKE_DOCKER_STATE=str(state_path),WECOM_STATE_DIR=str(root/'state'),WECOM_HEALTH_ATTEMPTS='1',WECOM_CONFIG_PATH=str(config))
            command=['bash',str(ROOT/'scripts/deploy/deploy.sh'),'test',str(project),sha,str(inbox)]
            if build: command=['bash',str(ROOT/'scripts/deploy/build_test.sh'),str(project),sha,str(inbox)]
            result=subprocess.run(command,
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
                if build:
                    self.assertNotIn('.env',final['build_context_entries'])
                    self.assertIn('Dockerfile',final['build_context_entries'])
                    self.assertIn('RELEASE_DESCRIPTOR_JSON',result.stdout)
                    descriptors=[line.split(' ',1)[1] for line in result.stdout.splitlines() if line.startswith('RELEASE_DESCRIPTOR_JSON ')]
                    validate_descriptor(json.loads(descriptors[-1]),sha,'https://gezelling.com/uploads/pipeline-releases')

    def test_clean_builder_never_copies_untracked_runtime_secrets(self):
        self.run_scenario(build=True)

    def test_success_advances_code_and_image(self):
        self.run_scenario()

    def test_unhealthy_image_rolls_back_code_and_image(self):
        self.run_scenario(fail=True)

    def test_database_probe_failure_rolls_back_code_and_image(self):
        self.run_scenario(probe_fail=True)


if __name__ == '__main__':
    unittest.main()
