#!/usr/bin/env python3
"""FC: Swift Codable field/type parity and fail-closed sensitive plan policy.

Lab-only. Fixtures are synthetic and contain no user chapters, credentials,
network access, updater, IPA or real SQLite files.
"""
from __future__ import annotations
import copy
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'build70_ev_fd_quarantine.swift'
FIXTURE = HERE / 'fixtures' / 'FCAppCodableModels.swift'
RUNNER = HERE / 'fixtures' / 'FCParityRunner.swift'


def plan():
    return {
        'schemaVersion': 1, 'sourceID': 's',
        'manga': {'id': 'm', 'title': 'Synthetic', 'altTitles': [],
                  'status': 'unknown', 'genres': []},
        'chapter': {'id': 'c', 'name': 'Chapter'},
        'pages': [{'index': 0, 'imageUrl': 'https://example.invalid/image.bin', 'headers': {}}],
        'manifest': {'id': 's', 'name': 'Demo', 'version': '1.0', 'lang': 'en',
                     'author': 'Lab', 'script': 'https://example.invalid/script.js',
                     'apiVersion': 1, 'minAppVersion': '1.0',
                     'domains': ['example.invalid'], 'nsfw': False},
        'queueOrder': 0,
    }


class FCCodableParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which('swiftc'):
            raise unittest.SkipTest('native Swift compiler required')
        cls.tmp = tempfile.TemporaryDirectory(prefix='webreader_fc_compiler_')
        cls.binary = Path(cls.tmp.name) / 'fc_codable_parity'
        subprocess.run(['swiftc', str(FIXTURE), str(RUNNER), '-o', str(cls.binary)],
                       check=True, capture_output=True, text=True, timeout=120)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def probe(self, payload):
        run = subprocess.run([str(self.binary)], input=json.dumps(payload), text=True,
                             capture_output=True, timeout=12, check=True)
        self.assertNotIn('secret', run.stdout)
        self.assertNotIn('token', run.stdout)
        return dict(i.split('=') for i in run.stdout.strip().split(' '))

    def test_1_real_contract_fields_mirrored_in_native_lab(self):
        swift = SOURCE.read_text()
        copy_model = FIXTURE.read_text()
        real_fragment = swift.split('private struct FBPlanEnvelope: Decodable {', 1)[1].split(
            '\nprivate func fbAdmittedFile', 1)[0]
        self.assertIn(real_fragment, copy_model)
        for required in ('var status: MangaStatus', 'let headers: [String: String]',
                         'let sourceID: String', 'let queueOrder: Int',
                         'let requiresFullReplay: Bool?'):
            self.assertIn(required, copy_model)

    def test_2_known_manga_status_enum_parity(self):
        for value in ('unknown', 'ongoing', 'completed', 'hiatus', 'cancelled'):
            with self.subTest(value=value):
                payload = plan(); payload['manga']['status'] = value
                self.assertEqual(self.probe(payload), {'real': '1', 'mirror': '1'})

    def test_3_invalid_manga_status_is_rejected_by_both(self):
        for value in ('archived', 'Completed', '', 123):
            with self.subTest(value=value):
                payload = plan(); payload['manga']['status'] = value
                self.assertEqual(self.probe(payload), {'real': '0', 'mirror': '0'})

    def test_4_required_root_fields_match_real(self):
        for key in ('schemaVersion', 'sourceID', 'manga', 'chapter', 'pages',
                    'manifest', 'queueOrder'):
            with self.subTest(key=key):
                payload = plan(); del payload[key]
                self.assertEqual(self.probe(payload), {'real': '0', 'mirror': '0'})

    def test_5_required_nested_manga_fields_match_real(self):
        for key in ('id', 'title', 'altTitles', 'status', 'genres'):
            with self.subTest(key=key):
                payload = plan(); del payload['manga'][key]
                self.assertEqual(self.probe(payload), {'real': '0', 'mirror': '0'})

    def test_6_required_manifest_fields_match_real(self):
        for key in ('id','name','version','lang','author','script','apiVersion',
                    'minAppVersion','domains','nsfw'):
            with self.subTest(key=key):
                payload=plan();del payload['manifest'][key]
                self.assertEqual(self.probe(payload), {'real':'0','mirror':'0'})

    def test_7_required_page_fields_match_real(self):
        for key in ('index','imageUrl','headers'):
            with self.subTest(key=key):
                payload=plan();del payload['pages'][0][key]
                self.assertEqual(self.probe(payload), {'real':'0','mirror':'0'})

    def test_8_optional_app_fields_remain_optional(self):
        payload=plan()
        self.assertEqual(self.probe(payload), {'real':'1','mirror':'1'})
        payload['manga'].update({'description':'test','url':'https://example.invalid',
                                 'cover':None,'author':None,'artist':None})
        payload['chapter'].update({'date':None,'scanlator':'test','language':'en'})
        payload['manifest'].update({'icon':None,'sha256':None})
        payload['requiresFullReplay']=False
        self.assertEqual(self.probe(payload), {'real':'1','mirror':'1'})

    def test_9_malformed_required_type_rejected(self):
        for keys, value in ((('queueOrder',), '3'), (('pages',), 'not an array'),
                            (('manifest','nsfw'), 'false'),
                            (('manga','altTitles'), 'not an array'),
                            (('pages',0,'headers'), []),
                            (('manifest','domains'), 1)):
            with self.subTest(keys=keys):
                payload=plan();target=payload
                for key in keys[:-1]: target=target[key]
                target[keys[-1]]=value
                self.assertEqual(self.probe(payload), {'real':'0','mirror':'0'})

    def test_10_private_headers_are_decodeable_by_app_but_blocked_by_lab(self):
        for header in ('Authorization', 'Cookie', 'X-Api-Key', 'X-Request-ID'):
            with self.subTest(header=header):
                payload=plan();payload['pages'][0]['headers']={header: 'secret'}
                self.assertEqual(self.probe(payload), {'real':'1','mirror':'0'})

    def test_11_empty_metadata_headers_permitted(self):
        payload=plan();payload['pages'].append({'index':1,'imageUrl':'https://example.invalid/2','headers':{}})
        self.assertEqual(self.probe(payload), {'real':'1','mirror':'1'})

    def test_12_noncontiguous_page_indices_denied_by_lab(self):
        payload=plan();payload['pages'][0]['index']=10
        self.assertEqual(self.probe(payload), {'real':'1','mirror':'0'})

    def test_13_schema_mismatch_denied_by_lab(self):
        payload=plan();payload['schemaVersion']=2
        self.assertEqual(self.probe(payload), {'real':'1','mirror':'0'})

    def test_14_empty_pages_denied_by_lab(self):
        payload=plan();payload['pages']=[]
        self.assertEqual(self.probe(payload), {'real':'1','mirror':'0'})

    def test_15_utf8_and_unknown_properties_compatibility(self):
        payload=plan();payload['manga']['title']='日本語 / capítulo'; payload['futureUnknownKey']='ignored'
        self.assertEqual(self.probe(payload), {'real':'1','mirror':'1'})


class FCHeaderPrivacyNativeIntegration(unittest.TestCase):
    """Test the actual native Swift preflight, not only an isolated decoder."""
    @classmethod
    def setUpClass(cls):
        if not shutil.which('swiftc'):
            raise unittest.SkipTest('native Swift compiler required')
        cls.tmp = tempfile.TemporaryDirectory(prefix='webreader_fc_native_')
        cls.binary = Path(cls.tmp.name) / 'fc_fd_native'
        subprocess.run(['swiftc', str(SOURCE), '-o', str(cls.binary)],
                       check=True, capture_output=True, text=True, timeout=120)

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def setUp(self):
        self.tmpfiles = tempfile.TemporaryDirectory(prefix='webreader_fc_privacy_')
        self.root = Path(self.tmpfiles.name)
        (self.root / '.webreader_ev_disposable_marker').write_bytes(b'EV_SYNTHETIC_ONLY\n')
        self.app=self.root/'synthetic_app'
        self.chapter=self.app/'Downloads'/'s'/'m'/'c'
        self.chapter.mkdir(parents=True)
        (self.chapter/'page-00000.bin').write_bytes(b'fake page data')
        (self.app/'Quarantine').mkdir()

    def tearDown(self): self.tmpfiles.cleanup()

    def command(self,action):
        return subprocess.run([str(self.binary),action,str(self.root),'s','m','c','ev_'+'f'*32],
                              capture_output=True,text=True,timeout=15)

    def add_plan(self, modifier=None):
        payload=plan()
        if modifier: modifier(payload)
        (self.chapter/'_download-plan.json').write_text(json.dumps(payload))
        return payload

    def test_16_valid_plan_is_admitted(self):
        self.add_plan();r=self.command('inspectmeta')
        self.assertEqual(r.returncode,0,r.stderr)

    def test_17_invalid_status_refused_before_any_copy(self):
        self.add_plan(lambda p:p['manga'].__setitem__('status','archived'))
        r=self.command('inspectmeta')
        self.assertNotEqual(r.returncode,0)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))

    def test_18_authorization_header_refused_before_copy(self):
        self.add_plan(lambda p:p['pages'][0]['headers'].update({'Authorization':'secret'}))
        r=self.command('inspectmeta')
        self.assertNotEqual(r.returncode,0)
        self.assertNotIn('secret',r.stderr)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))

    def test_19_cookie_header_refused_before_copy(self):
        self.add_plan(lambda p:p['pages'][0]['headers'].update({'Cookie':'token'}))
        r=self.command('inspectmeta')
        self.assertNotEqual(r.returncode,0)
        self.assertNotIn('token',r.stderr)
        self.assertFalse(list((self.app/'Quarantine').iterdir()))

    def test_20_privacy_rejection_does_not_touch_original_bytes(self):
        payload=self.add_plan(lambda p:p['pages'][0]['headers'].update({'Authorization':'secret'}))
        before=(self.chapter/'_download-plan.json').read_bytes()
        self.command('inspectmeta');self.command('snapshotmeta')
        self.assertEqual((self.chapter/'_download-plan.json').read_bytes(),before)
        self.assertEqual((self.chapter/'page-00000.bin').read_bytes(),b'fake page data')
        self.assertFalse(list((self.app/'Quarantine').iterdir()))


if __name__=='__main__':unittest.main()
