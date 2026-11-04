"""Portable config identity across classic Docker and Docker 29 containerd stores."""
import copy
import hashlib
import io
import json
import sys
import tarfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts/deploy'))
from image_identity import configuration_id,verified_image_id

REVISION='a'*40
CONFIG={'architecture':'amd64','os':'linux','rootfs':{'type':'layers','diff_ids':['sha256:'+'e'*64]},
        'config':{'Env':['PATH=/bin'],'Cmd':['sh','-c','start'],'WorkingDir':'/app',
                  'Labels':{'org.opencontainers.image.revision':REVISION}}}
RAW=json.dumps(CONFIG,sort_keys=True).encode()
CONFIG_ID='sha256:'+hashlib.sha256(RAW).hexdigest()
MANIFEST=json.dumps({'schemaVersion':2,'config':{'digest':CONFIG_ID},'layers':[]},sort_keys=True).encode()
NATIVE_ID='sha256:'+hashlib.sha256(MANIFEST).hexdigest()
INFO={'Id':NATIVE_ID,'Descriptor':{'digest':NATIVE_ID},'Architecture':'amd64','Os':'linux',
      'RootFS':{'Layers':CONFIG['rootfs']['diff_ids']},'Config':CONFIG['config']}


def archive(oci=True,raw=RAW,config_reference=CONFIG_ID):
    output=io.BytesIO()
    entries=[('blobs/sha256/'+CONFIG_ID[7:] if oci else CONFIG_ID[7:]+'.json',raw)]
    if oci: entries.append(('blobs/sha256/'+NATIVE_ID[7:],MANIFEST))
    else: entries.append(('manifest.json',json.dumps([{'Config':config_reference[7:]+'.json','Layers':['layer.tar']}]).encode()))
    with tarfile.open(fileobj=output,mode='w') as tar:
        for name,value in entries:
            member=tarfile.TarInfo(name);member.size=len(value)
            tar.addfile(member,io.BytesIO(value))
    output.seek(0)
    return output


class ImageIdentityTests(unittest.TestCase):
    def test_containerd_manifest_resolves_original_config(self):
        self.assertNotEqual(INFO['Id'],CONFIG_ID)
        self.assertEqual(configuration_id(archive(),INFO),CONFIG_ID)

    def test_classic_export_manifest_is_also_supported(self):
        self.assertEqual(configuration_id(archive(oci=False),INFO),CONFIG_ID)

    def test_changed_config_bytes_cannot_hide_under_correct_filename(self):
        changed=copy.deepcopy(CONFIG);changed['config']['Cmd']=['malicious']
        with self.assertRaisesRegex(ValueError,'checksum'):
            configuration_id(archive(raw=json.dumps(changed).encode()),INFO)

    def test_unreferenced_matching_config_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'No referenced'):
            configuration_id(archive(oci=False,config_reference='sha256:'+'f'*64),INFO)

    def test_different_filesystem_layers_are_rejected(self):
        info=copy.deepcopy(INFO);info['RootFS']['Layers']=['sha256:'+'f'*64]
        with self.assertRaises(ValueError): configuration_id(archive(),info)

    def test_different_effective_command_is_rejected(self):
        info=copy.deepcopy(INFO);info['Config']['Cmd']=['other-command']
        with self.assertRaises(ValueError): configuration_id(archive(),info)

    def test_classic_id_fast_path_does_not_export(self):
        info=copy.deepcopy(INFO);info['Id']=CONFIG_ID
        with patch('image_identity.subprocess.check_output',return_value=json.dumps([info]).encode()), patch('image_identity.subprocess.Popen',side_effect=AssertionError('must not export')):
            self.assertEqual(verified_image_id('image',CONFIG_ID,REVISION),CONFIG_ID)

    def test_oci_verification_returns_local_manifest_id_for_tagging(self):
        class Export:
            stdout=archive()
            def poll(self): return 0
            def wait(self,timeout=None): return 0
        with patch('image_identity.subprocess.check_output',return_value=json.dumps([INFO]).encode()), patch('image_identity.subprocess.Popen',return_value=Export()):
            self.assertEqual(verified_image_id('image',CONFIG_ID,REVISION),NATIVE_ID)

    def test_revision_mismatch_is_rejected_before_tagging(self):
        with patch('image_identity.subprocess.check_output',return_value=json.dumps([INFO]).encode()), self.assertRaisesRegex(ValueError,'revision'):
            verified_image_id('image',CONFIG_ID,'b'*40)


if __name__=='__main__': unittest.main()
