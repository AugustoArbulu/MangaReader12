#!/usr/bin/env python3
"""DU: static check of PR-only, latest-commit QA matrix scheduling.

This checks source configuration only, not GitHub runner availability.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS = (
    ".github/workflows/chimera-build70-phase-dq-installed-bundle-readonly.yml",
    ".github/workflows/chimera-build70-phase-dr-preupgrade-evidence.yml",
    ".github/workflows/chimera-build70-phase-ds-candidate-evidence.yml",
    ".github/workflows/chimera-build70-phase-dt-postupgrade-readonly.yml",
)


class DUWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {path: (ROOT/path).read_text() for path in WORKFLOWS}

    def test_four_workflows_present(self):
        self.assertEqual(len(set(WORKFLOWS)), 4)
        for path in WORKFLOWS:
            self.assertTrue((ROOT/path).is_file())
            self.assertFalse((ROOT/path).is_symlink())

    def test_pr_dispatch_without_duplicate_push_event(self):
        for path, content in self.sources.items():
            with self.subTest(path=path):
                self.assertIn("on:\n  pull_request:", content)
                self.assertIn("  workflow_dispatch:\n", content)
                self.assertNotIn("\n  push:\n", content)
                self.assertIn("branches: [main]", content.replace(
                    "branches:\n      - main", "branches: [main]"
                ))

    def test_latest_head_supersedes_queued_runs_for_same_pr(self):
        for path, content in self.sources.items():
            with self.subTest(path=path):
                self.assertEqual(content.count("\nconcurrency:\n"), 1)
                self.assertIn("github.workflow", content)
                self.assertIn("github.event.pull_request.number || github.ref", content)
                self.assertIn("  cancel-in-progress: true\n", content)
                self.assertNotIn("cancel-in-progress: false", content)

    def test_no_artifacts_and_both_os_preserved(self):
        for path, content in self.sources.items():
            with self.subTest(path=path):
                self.assertIn("permissions:\n  contents: read\n", content)
                self.assertIn("macos-15", content)
                self.assertIn("ubuntu-latest", content)
                self.assertNotIn("actions/upload-artifact", content)

    def test_native_apple_gate_not_skipped(self):
        self.assertIn(
            "test_build70_ds_candidate_evidence_native.py",
            self.sources[WORKFLOWS[2]],
        )
        self.assertIn("Xcode 16.4", self.sources[WORKFLOWS[2]])

    def test_three_production_guards_remain_disabled(self):
        files = (
            ("MangaReader12/Core/WebReaderUpdateChecker.swift",
             "static let productionPublicKeyX963: Data? = nil"),
            ("MangaReader12/Core/WebReaderProductionPublisherTrust.swift",
             "static let independentlyProvisionedSPKISHA256: String? = nil"),
            ("MangaReader12/Core/WebReaderAppinstSocket.swift",
             "static let liveInstallationEnabled = false"),
        )
        for path, needle in files:
            self.assertIn(needle, (ROOT/path).read_text())


if __name__ == "__main__":
    unittest.main()
