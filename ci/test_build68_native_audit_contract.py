#!/usr/bin/env python3
"""Build68 static guardrails; native Swift tests run independently on macOS.

The important distinction: this read-only audit checks contents of an IPA
that the owner may choose to export by hand. It is NOT an authentication
system for an automatic appinst updater. Not an executable policy.
"""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent
AUDITOR = (ROOT / "MangaReader12/Core/WebReaderNativeIPAAuditor.swift").read_text()
STAGER = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
APPINST = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
CHECKER = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
NATIVE_QA = (ROOT / "ci/test_native_webreader_ipa_auditor.py").read_text()


class Build68AtomicIPAAudit(unittest.TestCase):
    def test_native_audit_not_using_path_based_file_reopening(self):
        self.assertIn("import Darwin", AUDITOR)
        self.assertNotIn("FileHandle(forReadingFrom: ipaURL)", AUDITOR)
        self.assertNotIn("FileManager.default.attributesOfItem(atPath: ipaURL.path)", AUDITOR)
        self.assertIn("let file = FileHandle(fileDescriptor: descriptor", AUDITOR)

    def test_descriptor_rejects_symlinks_and_fifos_without_blocking(self):
        self.assertIn("O_NOFOLLOW | O_NONBLOCK", AUDITOR)
        self.assertIn("mode_t(S_IFREG)", AUDITOR)
        self.assertIn("Darwin.fstat(descriptor, &opened)", AUDITOR)
        self.assertIn("Darwin.close(descriptor)", AUDITOR)

    def test_same_descriptor_used_during_zip_and_sha_checks(self):
        self.assertIn("fileSHA256(file)", AUDITOR)
        self.assertIn("let finalDigest = fileSHA256(file)", AUDITOR)
        self.assertIn("file, at: directoryOffset", AUDITOR)
        self.assertIn("defer { file.closeFile() }", AUDITOR)

    def test_same_inode_and_metadata_checked_after_scan(self):
        for term in (
            "Darwin.fstat(descriptor, &finished)",
            "opened.st_dev == finished.st_dev",
            "opened.st_ino == finished.st_ino",
            "opened.st_size == finished.st_size",
            "opened.st_mtimespec.tv_sec == finished.st_mtimespec.tv_sec",
            "opened.st_mtimespec.tv_nsec == finished.st_mtimespec.tv_nsec",
            "opened.st_ctimespec.tv_sec == finished.st_ctimespec.tv_sec",
            "opened.st_ctimespec.tv_nsec == finished.st_ctimespec.tv_nsec",
            "finalDigest == signedUpdate.sha256",
        ):
            with self.subTest(term=term):
                self.assertIn(term, AUDITOR)

    def test_metadata_matches_expected_newer_build(self):
        for term in (
            'properties["CFBundleIdentifier"] as? String',
            '"com.example.MangaReader12"',
            'properties["CFBundleExecutable"] as? String',
            '"MangaReader12"',
            "build == signedUpdate.build",
            "build > installedBuild",
            "rawIOS == signedUpdate.minimumIOS",
        ):
            self.assertIn(term, AUDITOR)

    def test_zip_guardrails_preserved(self):
        for term in (
            "maxArchiveBytes", "maxIndexBytes", "maxEntries",
            "maxPlistBytes", "maxExpandedTotal",
            "validatedPath(nameBytes)", "crc32(bytes) == entry.crc",
            "u32(local, 0) == 0x04034B50",
        ):
            self.assertIn(term, AUDITOR)

    def test_native_symlink_and_fifo_negative_coverage(self):
        for term in (
            "symlink-to-valid", "FIFO-without-writer", "directory-not-ipa",
            "os.mkfifo(fifo_path)", "timeout=10",
        ):
            self.assertIn(term, NATIVE_QA)

    def test_existing_manual_stage_and_recheck_are_nonprivileged(self):
        self.assertIn("WebReaderLocalIPAReviewer.recheck(", UI)
        self.assertIn("WebReaderLocalIPAReviewer.importForReview(", UI)
        self.assertIn("WebReaderNativeIPAAuditor.inspect(", STAGER)
        self.assertIn("WebReaderNativeIPAAuditor.inspect(", UI)
        self.assertIn("publisherAuthenticated: Bool = false", STAGER)
        self.assertIn("installationAuthorized: Bool = false", STAGER)

    def test_local_import_budget_and_symlinked_target_denial(self):
        for term in (
            "static func requiredFreeBytes(ipaBytes: Int64)",
            "static func hasEnoughSpace(freeBytes: Int64, ipaBytes: Int64)",
            "max(Int64(16 * 1024 * 1024)",
            "min(Int64(64 * 1024 * 1024)",
            "free.int64Value",
            "Darwin.fstat(dirFD, &dirInfo)",
            "mode_t(S_IFDIR)",
            "case insufficientSpace",
            "Darwin.fchmod(outputFD, mode_t(0o600))",
        ):
            with self.subTest(term=term):
                self.assertIn(term, STAGER)

    def test_native_import_negative_symlinked_directory_and_headroom(self):
        suite = (ROOT / "ci/test_native_webreader_local_ipa_review.py").read_text()
        for term in (
            "requiredFreeBytes(ipaBytes: small)",
            "hasEnoughSpace(",
            "576 * 1024 * 1024",
            "redirected-QA-directory",
            "mockLibrary",
            "staging directory symlink unexpectedly accepted",
            "private, not inherited world-readable",
        ):
            with self.subTest(term=term):
                self.assertIn(term, suite)
        self.assertIn("Espaço insuficiente para copiar a IPA", UI)

    def test_no_automatic_authorization(self):
        self.assertIn("static let liveInstallationEnabled = false", APPINST)
        self.assertIn("DispatchQueue.main.async { completion(.rejected) }", APPINST)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHECKER)
        for term in ("appinst(", "posix_spawn(", "system(", "fork(", "setuid("):
            self.assertNotIn(term, AUDITOR)
            self.assertNotIn(term, UI)

    def test_stable_baseline_does_not_implicitly_release_build68(self):
        workflow = (ROOT / ".github/workflows/chimera-build68-security-preflight.yml").read_text()
        self.assertNotIn("upload-artifact", workflow)
        self.assertNotIn("package_webreader_build68", workflow)
        self.assertNotIn("gh release", workflow)
        self.assertIn("CODE_SIGNING_ALLOWED=NO", workflow)

    def test_old_build67_release_is_frozen(self):
        prior = (ROOT / ".github/workflows/chimera-build67-private-manual-qa.yml").read_text()
        self.assertNotIn("  push:", prior)
        self.assertIn('test "$GITHUB_SHA" = "df6d8a44b56ed2fe693df4ad114b3de885f69542"', prior)


if __name__ == "__main__":
    unittest.main()
