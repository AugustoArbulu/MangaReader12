#!/usr/bin/env python3
"""Phase Q: safe Release cache cleanup, separate from manual QA imports."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
SWIFT = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
APPINST = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
CHANNEL = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
WORKFLOW = (ROOT / ".github/workflows/chimera-phase-p-qa-storage.yml").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_release_cache_storage.py").read_text()


class ReleaseCachePolicy(unittest.TestCase):
    def test_explicitly_separate_download_cache_and_local_qa_imports(self):
        self.assertIn('appendingPathComponent("WebReaderUpdates"', SWIFT)
        self.assertIn('appendingPathComponent("WebReaderLocalQAImports"', SWIFT)
        self.assertIn("enum WebReaderReleaseCacheStorage", SWIFT)
        self.assertNotIn("WebReaderLocalQAImports", SWIFT.split(
            "enum WebReaderReleaseCacheStorage", 1)[1])

    def test_only_exact_owned_download_names_are_eligible(self):
        body = SWIFT.split("enum WebReaderReleaseCacheStorage", 1)[1]
        for s in (
            "static func isManagedName(", "WebReader-build[1-9][0-9]{0,8}-",
            "webreader-", ".partial", ".ipa", "name.utf8.count <= 100"
        ):
            with self.subTest(s=s):
                self.assertIn(s, body)

    def test_read_only_inventory_is_bounded_and_descriptor_anchored(self):
        body = SWIFT.split("enum WebReaderReleaseCacheStorage", 1)[1]
        inspection = body.split("static func inventory(", 1)[1].split(
            "static func discardConfirmed(", 1)[0]
        for s in (
            "maximumScannedNames = 512",
            "O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW",
            "Darwin.fstatat(fd, name, &st, AT_SYMLINK_NOFOLLOW)",
            "FileManager.default.contentsOfDirectory(atPath: directory.path)",
            "Int64.max - candidate.byteCount", "name != protectedName",
            "minimumAgeSeconds", "st.st_ctimespec.tv_nsec",
        ):
            self.assertIn(s, body)
        for forbidden in ("Darwin.unlinkat(", "removeItem(", "createDirectory("):
            self.assertNotIn(forbidden, inspection)

    def test_deletion_requires_same_inode_metadata_and_age(self):
        body = SWIFT.split("enum WebReaderReleaseCacheStorage", 1)[1]
        for s in (
            "st.st_nlink == 1", "UInt64(st.st_dev) == candidate.fileDevice",
            "UInt64(st.st_ino) == candidate.fileInode",
            "Int64(st.st_size) == candidate.byteCount",
            "candidate.modifiedNanoseconds", "candidate.changedNanoseconds",
            "st.st_mtimespec.tv_sec) <= cutoff",
            "st.st_ctimespec.tv_sec) <= cutoff",
            "Darwin.unlinkat(fd, candidate.fileName, 0)",
            "candidate.fileName != protectedName",
        ):
            self.assertIn(s, body)
        self.assertNotIn("posix_spawn(", body)
        self.assertNotIn("/usr/bin/appinst", body)
        self.assertNotIn("rm -rf", body)

    def test_ui_manual_confirmation_with_separate_actions(self):
        for s in (
            "if source == 6 { return 8 }", "case (6, 6):", "case (6, 7):",
            "inspectReleaseCache(cleanup: false)",
            "inspectReleaseCache(cleanup: true)",
            "confirmReleaseCacheCleanup(scan)",
            '"Excluir cache antigo", style: .destructive',
            "discardReleaseCacheAfterConfirmation(scan)",
            "WebReaderReleaseCacheStorage.discardConfirmed(",
            "activeReleaseCacheName()", "!stagingIPA", "!verifyingExport"
        ):
            self.assertIn(s, UI)
        inspection = UI.split(
            "private func inspectReleaseCache(cleanup: Bool)", 1
        )[1].split("private func confirmReleaseCacheCleanup(", 1)[0]
        self.assertNotIn("WebReaderReleaseCacheStorage.discardConfirmed(", inspection)

    def test_isolated_ipc_app_has_no_release_cache_controls(self):
        self.assertIn("return isIPCDiagnostic ? 2 : 7", UI)
        self.assertIn("guard !isIPCDiagnostic", UI)
        self.assertIn("case (6, 7):", UI)

    def test_native_scenarios_exercise_retention_and_no_privilege(self):
        for scenario in (
            "missing cache empty", "24h retention is enforced",
            "identical bytes new inode rejected", "changed ctime rejects stale receipt",
            "abandoned partial removed", "active saved",
            "original owner file untouched", "unbounded directory listing accepted",
            "directory symlink accepted",
        ):
            self.assertIn(scenario, NATIVE)
        self.assertIn("test_native_webreader_release_cache_storage.py", WORKFLOW)

    def test_release_and_installer_still_fail_closed(self):
        self.assertIn("static let liveInstallationEnabled = false", APPINST)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHANNEL)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)


if __name__ == "__main__":
    unittest.main()
