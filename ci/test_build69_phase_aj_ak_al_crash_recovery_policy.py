#!/usr/bin/env python3
"""Build69 AJ/AK/AL: post-crash download recovery is strictly non-destructive."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
STAGER = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
NATIVE_CACHE = (ROOT / "ci/test_native_webreader_release_cache_storage.py").read_text()
NATIVE_STAGE = (ROOT / "ci/test_native_webreader_ipa_stager.py").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
CHANNEL = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()


class RecoveryIsNonPrivileged(unittest.TestCase):
    def test_summary_is_read_only_and_classifies_stale_files(self):
        body = STAGER.split("struct WebReaderReleaseRecoverySummary {", 1)[1].split(
            "/// Separate from WebReaderLocalQAImports", 1
        )[0]
        for token in (
            "let interruptedFiles: Int", "let interruptedBytes: Int64",
            "let completedFiles: Int", "let completedBytes: Int64",
            "let ignoredEntries: Int",
            "let canResumePartial: Bool = false",
            "let cleanupRequiresOwnerConfirmation: Bool = true",
            "let installationAuthorized: Bool = false",
            "static func readOnly(",
            'entry.fileName.hasSuffix(".partial")',
            'entry.fileName.hasSuffix(".ipa")',
        ):
            self.assertIn(token, body)
        for prohibited in (
            "FileManager.", "URLSession", "open(", "unlink(", "unlinkat(",
            "removeItem(", "createFile(", "Data(contentsOf:", "appinst(",
            "posix_spawn(", "install(", "try ", "throw ",
        ):
            self.assertNotIn(prohibited, body)

    def test_old_only_and_owner_confirmed_cleanup_stays_unmodified(self):
        gate = STAGER.split("enum WebReaderReleaseCacheStorage {", 1)[1]
        self.assertIn("minimumAgeSeconds: Int64 = 24 * 60 * 60", gate)
        self.assertIn("maximumScannedNames = 512", gate)
        self.assertIn("Darwin.fstatat(fd, name, &st, AT_SYMLINK_NOFOLLOW)", gate)
        self.assertIn("st.st_nlink == 1", gate)
        self.assertIn("candidate.fileName != protectedName", gate)
        self.assertIn("UInt64(st.st_ino) == candidate.fileInode", gate)
        self.assertIn("Int64(st.st_ctimespec.tv_sec) == candidate.changedSeconds", gate)
        self.assertIn("static func discardConfirmed(", gate)
        self.assertNotIn("recursively", gate)
        self.assertIn("activeReleaseCacheName()", UI)

    def test_ui_auto_checks_once_but_never_auto_cleans(self):
        appearance = UI.split("override func viewDidAppear(", 1)[1].split(
            "override func viewWillDisappear", 1
        )[0]
        for token in (
            "super.viewDidAppear(animated)",
            "!isIPCDiagnostic, !didInspectRecoveryOnOpen",
            "didInspectRecoveryOnOpen = true",
            "inspectReleaseCache(cleanup: false)",
        ):
            self.assertIn(token, appearance)
        self.assertNotIn("discardConfirmed(", appearance)
        self.assertNotIn("cleanup: true", appearance)
        rendering = UI.split("private func inspectReleaseCache(", 1)[1].split(
            "private func confirmReleaseCacheCleanup(", 1
        )[0]
        self.assertIn("WebReaderReleaseCacheStorage.inventory(", rendering)
        self.assertIn("WebReaderReleaseRecoverySummary.readOnly(scan)", rendering)
        self.assertIn("summary.interruptedFiles", rendering)
        self.assertIn("summary.completedFiles", rendering)
        self.assertIn("Sem retomada de arquivos parciais", rendering)
        self.assertIn("limpeza só com confirmação", rendering)
        # Only clicking the existing destructive row may request consent.
        self.assertIn("UIAlertController(", UI)
        self.assertIn("discardReleaseCacheAfterConfirmation(scan)", UI)

    def test_restart_is_full_verification_from_new_uuid_not_range_resume(self):
        first_stage = STAGER.split("func stage(completion", 1)[1].split(
            "func cancel()", 1
        )[0]
        for token in (
            '".webreader-" + UUID().uuidString + ".partial"',
            "OutputStream(url: staging, append: false)",
            'request.httpMethod = "GET"',
            "CC_SHA256_Init(&digest)",
            "task.resume()",
        ):
            self.assertIn(token, first_stage)
        for prohibited in ("Range", "Content-Range", "append: true", "resumeData"):
            self.assertNotIn(prohibited, first_stage)
        for label in (
            "old abandoned partial preserved until explicit owner cleanup",
            "owner retry validates fresh complete ZIP bytes from zero",
            "fresh recovery performs one full GET rather than Range resume",
            "fresh download never deletes abandoned bytes automatically",
        ):
            self.assertIn(label, NATIVE_STAGE)

    def test_mac_native_cases_cover_aged_and_recent_and_link_hardening(self):
        for label in (
            "recent in-progress file not treated as abandoned",
            "crash-recovery summary splits aged partials and completed IPAs",
            "counting old partials cannot resume, delete or install",
            "active, stranger, symlink, hardlink retained",
            "abandoned partial removed",
            "directory symlink accepted",
            "unbounded directory listing accepted",
        ):
            self.assertIn(label, NATIVE_CACHE)

    def test_approved_build68_and_installation_are_unchanged(self):
        self.assertEqual(PROJECT.count("CURRENT_PROJECT_VERSION = 56;"), 2)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHANNEL)
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)
        self.assertNotIn("posix_spawn(", UI)


if __name__ == "__main__":
    unittest.main()
