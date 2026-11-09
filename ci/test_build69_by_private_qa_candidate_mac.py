#!/usr/bin/env python3
"""Build69 BY: private macOS candidate stays opt-in; NO IPA in CI."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "ci/build69_by_private_qa_candidate_mac.sh"
PACKAGER = ROOT / "ci/package_webreader_build69_private_qa_ipa.sh"
CONSENT = "I-APPROVE-BUILD69-PRIVATE-QA-PACKAGING"


def run_denial(output, *, approval=None, reviewed=None, ci=None):
    env = dict(os.environ)
    for key in ("CI", "GITHUB_ACTIONS", "WR69_PRIVATE_QA_PACKAGE_APPROVAL",
                "WR69_PRIVATE_QA_REVIEWED_COMMIT"):
        env.pop(key, None)
    if approval is not None:
        env["WR69_PRIVATE_QA_PACKAGE_APPROVAL"] = approval
    if reviewed is not None:
        env["WR69_PRIVATE_QA_REVIEWED_COMMIT"] = reviewed
    if ci is not None:
        env[ci] = "true"
    return subprocess.run(
        ["bash", str(SCRIPT), str(output)],
        env=env, check=False, capture_output=True, text=True, timeout=10
    )


class PrivateCandidateSourceBuildTests(unittest.TestCase):
    def test_bash_syntax_and_no_automatic_execution(self):
        subprocess.run(["bash", "-n", str(SCRIPT)], check=True,
                       capture_output=True, timeout=10)

    def test_missing_and_wrong_owner_approval_never_write(self):
        with tempfile.TemporaryDirectory(prefix="wr69-by-deny-") as td:
            output = Path(td) / "WebReader-Build69-iOS12-adhoc.ipa"
            for value in (None, "", "yes", "I-APPROVE-BUILD69-PUBLIC-RELEASE"):
                with self.subTest(value=value):
                    result = run_denial(output, approval=value)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("BLOCKED", result.stderr)
                    self.assertFalse(output.exists())
                    self.assertFalse(Path(str(output)+".sha256").exists())

    def test_real_approval_still_cannot_work_in_ci(self):
        with tempfile.TemporaryDirectory(prefix="wr69-by-ci-deny-") as td:
            output = Path(td) / "WebReader-Build69-iOS12-adhoc.ipa"
            for ci in ("CI", "GITHUB_ACTIONS"):
                with self.subTest(ci=ci):
                    result = run_denial(
                        output, approval=CONSENT, reviewed="a" * 40, ci=ci
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn("never be created by CI", result.stderr)
                    self.assertFalse(output.exists())
                    self.assertFalse(Path(str(output)+".sha256").exists())

    def test_reviewed_archive_is_only_build_source(self):
        body = SCRIPT.read_text(encoding="utf-8")
        required = (
            'WR69_PRIVATE_QA_PACKAGE_APPROVAL',
            'WR69_PRIVATE_QA_REVIEWED_COMMIT',
            'build69_bx_reviewed_source_gate.py',
            'git -C "$ROOT" archive --format=tar "$REVIEWED_COMMIT"',
            'SOURCE="$TMP/Source"',
            'python3 ci/prepare_webreader_icons.py',
            'bash ci/prepare_libwebp_ios.sh',
            'xcodebuild -project MangaReader12.xcodeproj',
            'CURRENT_PROJECT_VERSION=69',
            'CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO clean build',
            'build69_ba_unsigned_candidate_audit.py',
            'package_webreader_build69_private_qa_ipa.sh',
            'rm -rf "$TMP"',
        )
        for token in required:
            with self.subTest(token=token):
                self.assertIn(token, body)
        archive = body.index('git -C "$ROOT" archive --format=tar')
        prepare = body.index('python3 ci/prepare_webreader_icons.py')
        build = body.index('xcodebuild -project MangaReader12.xcodeproj')
        audit = body.index('build69_ba_unsigned_candidate_audit.py')
        package = body.index('bash "$ROOT/ci/package_webreader_build69_private_qa_ipa.sh"')
        self.assertLess(archive, prepare)
        self.assertLess(prepare, build)
        self.assertLess(build, audit)
        self.assertLess(audit, package)
        self.assertEqual(body.count('build69_bx_reviewed_source_gate.py'), 2)

    def test_no_automatic_publish_install_or_unapproved_output(self):
        body = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('if [[ -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" ]]', body)
        self.assertIn('EXPECTED_NAME="WebReader-Build69-iOS12-adhoc.ipa"', body)
        self.assertIn('if [[ -e "$OUTPUT" || -L "$OUTPUT"', body)
        self.assertIn('if [[ "$OUTPUT_DIR/" == "$ROOT/"* ]]', body)
        for forbidden in (
            "appinst ", "posix_spawn", "gh release", "gh api",
            "curl https://github.com", "actions/upload-artifact",
            "git push", "git checkout main", "git merge", "security import",
            "upload-artifact@", "I-APPROVE-BUILD69-PUBLIC-RELEASE",
        ):
            with self.subTest(token=forbidden):
                self.assertNotIn(forbidden, body)
        self.assertIn('WR69_PRIVATE_QA_REVIEWED_COMMIT', PACKAGER.read_text())


if __name__ == "__main__":
    unittest.main()
