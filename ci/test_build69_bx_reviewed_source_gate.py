#!/usr/bin/env python3
"""Build69 BX: synthetic Git repositories; NEVER build/sign/package an IPA."""
import subprocess
import tempfile
from pathlib import Path
import unittest

from build69_bx_reviewed_source_gate import (
    BRANCH, ReviewedSourceRejected, inspect_reviewed_source
)


def git(root, *args):
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True, capture_output=True, text=True, timeout=15
    ).stdout.strip()


class ReviewedSourceGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="wr69-bx-clean-git-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        git(self.root, "init")
        git(self.root, "checkout", "-b", BRANCH)
        (self.root / "README.md").write_text("approved source\n", encoding="utf-8")
        git(self.root, "add", "README.md")
        git(self.root, "-c", "user.name=QA Fixture",
            "-c", "user.email=qa@example.invalid",
            "commit", "-m", "Synthetic test source")
        self.sha = git(self.root, "rev-parse", "HEAD")

    def test_clean_exact_commit_is_reviewable_not_an_install_permit(self):
        report = inspect_reviewed_source(self.root, self.sha)
        self.assertTrue(report["checkoutClean"])
        self.assertTrue(report["checkoutHeadMatchesReview"])
        self.assertFalse(report["ipaCreated"])
        self.assertFalse(report["appBuiltFromThisCommitProven"])
        self.assertFalse(report["installationAuthorized"])

    def test_wrong_or_ambiguous_review_sha_is_rejected(self):
        for bad in ("", self.sha[:8], self.sha.upper(),
                    "0" * 40, self.sha + "\n", None):
            with self.subTest(sha=bad), self.assertRaises(ReviewedSourceRejected):
                inspect_reviewed_source(self.root, bad)

    def test_untracked_and_modified_files_are_rejected(self):
        untracked = self.root / "untracked.swift"
        untracked.write_text("changed\n", encoding="utf-8")
        with self.assertRaises(ReviewedSourceRejected):
            inspect_reviewed_source(self.root, self.sha)
        untracked.unlink()
        (self.root / "README.md").write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(ReviewedSourceRejected):
            inspect_reviewed_source(self.root, self.sha)

    def test_staged_changes_are_rejected(self):
        (self.root / "README.md").write_text("staged\n", encoding="utf-8")
        git(self.root, "add", "README.md")
        with self.assertRaises(ReviewedSourceRejected):
            inspect_reviewed_source(self.root, self.sha)

    def test_other_branch_and_detached_head_are_rejected(self):
        git(self.root, "checkout", "-b", "main")
        with self.assertRaises(ReviewedSourceRejected):
            inspect_reviewed_source(self.root, self.sha)
        git(self.root, "checkout", "--detach", self.sha)
        with self.assertRaises(ReviewedSourceRejected):
            inspect_reviewed_source(self.root, self.sha)

    def test_nested_directory_and_missing_checkout_are_rejected(self):
        (self.root / "sub").mkdir()
        with self.assertRaises(ReviewedSourceRejected):
            inspect_reviewed_source(self.root / "sub", self.sha)
        with self.assertRaises(ReviewedSourceRejected):
            inspect_reviewed_source(self.root / "does-not-exist", self.sha)

    def test_source_change_cannot_be_pinned_to_old_commit(self):
        (self.root / "README.md").write_text("new reviewed content\n", encoding="utf-8")
        git(self.root, "add", "README.md")
        git(self.root, "-c", "user.name=QA Fixture",
            "-c", "user.email=qa@example.invalid",
            "commit", "-m", "Another test revision")
        with self.assertRaises(ReviewedSourceRejected):
            inspect_reviewed_source(self.root, self.sha)


if __name__ == "__main__":
    unittest.main()
