#!/usr/bin/env python3
"""CB: exercise fail-closed one-shot QA policy without signing/creating an IPA."""
import os
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

from build70_actions_qa_package import (
    BRANCH, EXPECTED_WORKFLOW, MARKER, OneShotQARejected,
    require_owner_approved_actions_context
)

ROOT = Path(__file__).resolve().parent.parent
PACKAGER = ROOT / "ci/build70_actions_qa_package.py"
WORKFLOW = ROOT / EXPECTED_WORKFLOW


class OneShotManualArtifactPolicy(TestCase):
    def test_not_approved_host_cannot_run(self):
        with patch.dict(os.environ, {
            "GITHUB_ACTIONS": "false",
            "GITHUB_EVENT_NAME": "push",
            "GITHUB_REF": "refs/heads/" + BRANCH,
        }, clear=True):
            with self.assertRaises(OneShotQARejected):
                require_owner_approved_actions_context()

    def test_packager_has_all_owner_and_source_guards(self):
        src = PACKAGER.read_text(encoding="utf-8")
        for token in (
            'GITHUB_WORKFLOW_REF', 'GITHUB_ACTIONS', 'GITHUB_EVENT_NAME',
            'HEAD^', '"diff", "--name-only", "HEAD^", "HEAD"',
            '"status", "--porcelain=v1", "--untracked-files=all"',
            'inspect_unsigned_candidate(app)',
            'preflight_private_qa_ipa(', '/usr/bin/ditto',
            '/usr/bin/codesign', '/usr/bin/zip',
            'os.link(staged_checksum, checksum)',
            'os.link(staged, ipa)', '_hash_regular(ipa)',
            'installedApplicationIdentifierMatch',
            'releasePublisherAuthenticated": False',
            'automaticInstallationEnabled": False',
            'installationAuthorized": False', 'installationPerformed": False'
        ):
            with self.subTest(token=token):
                self.assertIn(token, src)
        self.assertIn('baseline=69', src)
        self.assertIn('from build70_private_qa_ipa_preflight import', src)
        self.assertIn('from build70_unsigned_candidate_audit import', src)
        self.assertNotIn('appinst ', src)
        self.assertNotIn('gh release', src)
        self.assertNotIn('git push', src)
        self.assertNotIn('git merge', src)
        self.assertNotIn('sudo ', src)

    def test_workflow_is_approved_trigger_only(self):
        src = WORKFLOW.read_text(encoding="utf-8")
        for token in (
            "ci/build70_owner_approved_qa_trigger.txt",
            "feat/chimera-updater-phase1-protocol-audit",
            MARKER,
            "fetch-depth: 2",
            "CURRENT_PROJECT_VERSION=70",
            "CODE_SIGNING_ALLOWED=NO",
            "build70_actions_qa_package.py",
            "build70_private_qa_ipa_preflight.py",
            "actions/upload-artifact@v4",
            "retention-days: 14",
            "contents: read",
        ):
            with self.subTest(token=token):
                self.assertIn(token, src)
        self.assertIn('test_reader_webtoon_landscape_width.py', src)
        self.assertIn('python3 ci/build70_unsigned_candidate_audit.py', src)
        self.assertIn('python3 ci/build70_private_qa_ipa_preflight.py', src)
        self.assertIn('--installed-build 69', src)
        self.assertNotIn("workflow_dispatch:", src)
        self.assertNotIn("schedule:", src)
        self.assertNotIn("pull_request:", src)
        self.assertNotIn("gh release", src)
        self.assertNotIn("appinst ", src)
        self.assertNotIn("WebReaderAppinstSocket.install(", src)


if __name__ == "__main__":
    main()
