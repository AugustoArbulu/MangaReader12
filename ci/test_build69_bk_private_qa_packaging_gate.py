#!/usr/bin/env python3
"""Build69 BK: private QA packager must remain disabled by default.

Host tests inspect the packaged script and intentionally NEVER supply approval
or a built WebReader application. No IPA is created by these tests.
"""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "ci/package_webreader_build69_private_qa_ipa.sh"


class PrivatePackagingGate(unittest.TestCase):
    def test_shell_script_parses(self):
        subprocess.run(["bash", "-n", str(PACKAGE)],
                       check=True, timeout=10, capture_output=True)

    def test_consent_missing_or_wrong_cannot_create_any_file(self):
        with tempfile.TemporaryDirectory(prefix="wr69-bk-packaging-denied-") as td:
            root = Path(td)
            dummy = root / "MangaReader12.app"
            dummy.mkdir()
            expected = root / "WebReader-Build69-iOS12-adhoc.ipa"
            for value in ("", "YES", "I-APPROVE-BUILD69-PRIVATE-QA",
                          "I-APPROVE-BUILD69-PUBLIC-RELEASE"):
                env = dict(os.environ)
                env.pop("WR69_PRIVATE_QA_PACKAGE_APPROVAL", None)
                if value:
                    env["WR69_PRIVATE_QA_PACKAGE_APPROVAL"] = value
                response = subprocess.run(
                    ["bash", str(PACKAGE), str(dummy), str(expected)],
                    env=env, capture_output=True, text=True, timeout=10
                )
                self.assertNotEqual(response.returncode, 0)
                self.assertIn("BLOCKED", response.stderr)
                self.assertFalse(expected.exists())
                self.assertFalse(Path(str(expected)+".sha256").exists())

    def test_script_signs_only_temporary_copy_and_never_uploads(self):
        source = PACKAGE.read_text()
        for required in (
            'CONSENT="I-APPROVE-BUILD69-PRIVATE-QA-PACKAGING"',
            'if [[ "${WR69_PRIVATE_QA_PACKAGE_APPROVAL:-}" != "$CONSENT" ]]',
            'umask 077',
            'if [[ "$EUID" -eq 0 ]]',
            'git -C "$ROOT" branch --show-current',
            'feat/chimera-updater-phase1-protocol-audit',
            'WebReader-Build69-iOS12-adhoc.ipa',
            'build69_ba_unsigned_candidate_audit.py',
            'TMP="$(mktemp -d)"',
            'trap cleanup EXIT',
            '/usr/bin/ditto "$APP_PATH" "$TMP/Payload/MangaReader12.app"',
            'APP="$TMP/Payload/MangaReader12.app"',
            'chimera_webreader_qa.entitlements',
            '/usr/bin/codesign --force --sign - --timestamp=none',
            '/usr/bin/codesign --verify --verbose=2 "$APP"',
            'inspect_ipa(',
            'audit_code_signature_snapshot(',
            'assert seal["installedApplicationIdentifierMatch"]',
            '/usr/bin/zip -qry "$OUTPUT" Payload',
            '/usr/bin/shasum -a 256 "$OUTPUT"',
            'no GitHub upload, release, main change, or Chimera installation',
        ):
            with self.subTest(required=required):
                self.assertIn(required, source)
        for forbidden in (
            "appinst ", "posix_spawn", "curl ", "wget ", "gh release",
            "git push", "git checkout main", "git merge",
            "upload-artifact", "actions/upload-artifact",
            "installer -pkg", "codesign --deep", "security import",
            "I-APPROVE-BUILD69-PUBLIC-RELEASE",
        ):
            self.assertNotIn(forbidden, source)

    def test_production_workflow_cannot_package_by_default(self):
        integrated = (
            ROOT / ".github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml"
        ).read_text()
        steps = integrated.split("\njobs:\n", 1)[1]
        self.assertNotIn("package_webreader_build69_private_qa_ipa.sh", steps)
        self.assertNotIn("WR69_PRIVATE_QA_PACKAGE_APPROVAL:", steps)
        self.assertNotIn("upload-artifact@", steps)


if __name__ == "__main__":
    unittest.main()
