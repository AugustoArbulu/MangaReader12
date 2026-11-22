#!/usr/bin/env python3
"""DQ host checks for optional iOS12 read-only installed app claim probe."""
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parent.parent
PROBE=ROOT/"ci/build70_dq_installed_bundle_readonly.sh"

class DQReadOnlyShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.src=PROBE.read_text(encoding="utf-8")
    def command(self,*args):
        return subprocess.run(["/bin/sh",str(PROBE),*args],
                              capture_output=True,text=True,timeout=10)
    def test_syntax(self):
        result=subprocess.run(["/bin/sh","-n",str(PROBE)],
                              capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)
    def test_missing_args_denied(self):
        outcome=self.command()
        self.assertEqual(outcome.returncode,2)
        self.assertIn("DQ_STATUS=DENIED_INVALID_OR_UNREADABLE_BUNDLE",outcome.stdout)
        self.assertIn("INSTALLATION_AUTHORIZED=NO",outcome.stdout)
    def test_unrecognized_paths_denied_without_fs_changes(self):
        paths=(".", "./MangaReader12.app", "/tmp/MangaReader12.app",
               "/var/containers/Bundle/Application/UUID/MangaReader12.app",
               "/var/containers/Bundle/Application/../MangaReader12.app",
               "/var/containers/Bundle/Application/UUID/WebReader.app",
               "/var/containers/Bundle/Application/UUID/extra/MangaReader12.app")
        for path in paths:
            with self.subTest(path=path):
                self.assertEqual(self.command(path).returncode,2)
    def test_explicit_only_bundle_path_and_uuid(self):
        for token in (
            'app=$1', 'parent=${app%/*}', 'uuid=${parent##*/}',
            'base=${parent%/*}', '????????-????-????-????-????????????',
            '*[!0123456789abcdefABCDEF-]*) fail',
            '/var/containers/Bundle/Application',
            '/private/var/containers/Bundle/Application'):
            self.assertIn(token,self.src)
    def test_reject_symlink_and_missing_binary(self):
        for token in ('[ -L "$app" ]','[ -L "$app/Info.plist" ]',
                      '[ -L "$app/MangaReader12" ]',
                      '[ ! -f "$app/Info.plist" ]',
                      '[ ! -f "$app/MangaReader12" ]'):
            self.assertIn(token,self.src)
    def test_pinned_readonly_tool_paths(self):
        for token in ("/usr/bin/plutil","/usr/bin/ldid","/usr/bin/awk",
                      'plutil=','ldid=','awkbin=','[ ! -L "$tool" ]'):
            self.assertIn(token,self.src)
    def test_tools_missing_report_unavailable(self):
        for token in ('bundle=UNAVAILABLE', 'build=UNAVAILABLE',
                      'entitlement=UNAVAILABLE',
                      'info=$("$plutil" -p',
                      'entxml=$("$ldid" -e',
                      'safe_string() {'):
            self.assertIn(token,self.src)
    def test_entitlements_only_read_and_never_validity_claim(self):
        self.assertIn('"$ldid" -e "$app/MangaReader12"',self.src)
        self.assertIn('CODE_SIGNATURE_CRYPTOGRAPHIC_VALIDITY_PROVEN=NO',self.src)
        self.assertNotIn('ldid -S',self.src)
    def test_no_privileged_mutating_or_network_commands(self):
        active="\n".join(line for line in self.src.splitlines()
                         if not line.lstrip().startswith("#"))
        forbidden=(r'\bsudo\b',r'\bsu\s',r'\bchown\b',r'\bchmod\b',
                   r'\brm\s',r'\bmv\s',r'\bcp\s',r'\bmkdir\b',
                   r'\bappinst\b',r'\buicache\b',r'\breboot\b',
                   r'\blaunchctl\b',r'\bcurl\b',r'\bwget\b',
                   r'\bssh\b',r'\bscp\b',r'\btee\b',
                   r'\bmount\b',r'\bkill\b',r'\bexec\s')
        for expr in forbidden:
            with self.subTest(expr=expr):
                self.assertIsNone(re.search(expr,active))
    def test_no_scan_or_private_path_output(self):
        for token in ('find /', 'ls -R','Containers/Data/Application',
                      "printf '%s\\n' \"$app\""):
            self.assertNotIn(token,self.src)
    def test_untrusted_output_never_install_authority(self):
        for token in (
            'SOURCE=USER_SELECTED_INSTALLED_APP_BUNDLE_NOT_ATTESTED',
            'CURRENT_DEVICE_PROVEN_BY_SHELL_TEXT=NO',
            'CODE_SIGNATURE_CRYPTOGRAPHIC_VALIDITY_PROVEN=NO',
            'PUBLISHER_IDENTITY_AUTHENTICATED=NO',
            'DATA_CONTAINER_RETENTION_PROVEN=NO',
            'LIBRARY_AND_OFFLINE_PRESERVATION_PROVEN=NO',
            'READY_TO_DISTRIBUTE_IPA=NO',
            'INSTALLATION_AUTHORIZED=NO',
            'INSTALLATION_ATTEMPTED=NO'):
            self.assertIn(token,self.src)
    def test_three_production_hard_stops(self):
        for rel,needle in (
            ("MangaReader12/Core/WebReaderAppinstSocket.swift",
             "static let liveInstallationEnabled = false"),
            ("MangaReader12/Core/WebReaderUpdateChecker.swift",
             "static let productionPublicKeyX963: Data? = nil"),
            ("MangaReader12/Core/WebReaderProductionPublisherTrust.swift",
             "static let independentlyProvisionedSPKISHA256: String? = nil")):
            self.assertIn(needle,(ROOT/rel).read_text())

if __name__=="__main__":
    unittest.main()
