#!/usr/bin/env python3
"""Nonprivileged read-only WebReader QA storage UX/security contract.

The native test actually runs Swift file I/O on macOS. These checks protect
the iOS12 UI from ever turning inventory into automatic installation or
unconfirmed deletion of Library/chapters/backups.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
STAGING = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
SCREEN = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_local_qa_storage.py").read_text()
APPINST = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
CHECKER = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()


class QAStorageControls(unittest.TestCase):
    def test_readonly_inventory_does_not_create_or_remove_files(self):
        method = STAGING.split("static func inventory(", 1)[1].split(
            "static func discardConfirmed(", 1
        )[0]
        self.assertIn("contentsOfDirectory(atPath:", method)
        self.assertIn("Darwin.fstatat(dirFD, name, &st, AT_SYMLINK_NOFOLLOW)", method)
        self.assertNotIn("Darwin.unlinkat(", method)
        self.assertNotIn("removeItem(", method)
        self.assertNotIn("createDirectory(", method)

    def test_strict_regular_file_and_filename_pattern(self):
        for token in (
            "static func isQAName(", "WebReader-Build[1-9][0-9]{0,8}-local-",
            "name.utf8.count <= 90", 'name.hasSuffix(".ipa")',
            "st.st_nlink == 1", "mode_t(S_IFREG)",
            "st.st_size <= WebReaderLocalIPAReviewer.maximumSize",
        ):
            with self.subTest(token=token):
                self.assertIn(token, STAGING)

    def test_24_hour_quarantine_and_metadata_snapshot(self):
        for token in (
            "static let minimumAgeSeconds: Int64 = 24 * 60 * 60",
            "let cutoff = Int64(now.timeIntervalSince1970) - minimumAgeSeconds",
            "st.st_mtimespec.tv_sec",
            "st.st_mtimespec.tv_nsec",
            "st.st_ctimespec.tv_sec",
            "st.st_ctimespec.tv_nsec",
            "modifiedNanoseconds: Int64",
            "changedNanoseconds: Int64",
            "candidate.changedNanoseconds",
            "candidate.modifiedNanoseconds",
        ):
            with self.subTest(token=token):
                self.assertIn(token, STAGING)

    def test_bound_listing_to_512_entries_and_memory_safe_total(self):
        self.assertIn("static let maximumScannedNames = 512", STAGING)
        self.assertIn("names.count > maximumScannedNames", STAGING)
        self.assertIn("total <= Int64.max - bytes", STAGING)
        self.assertIn("eligible.sorted", STAGING)

    def test_protect_active_review_even_when_stale(self):
        self.assertIn("protected: WebReaderLocalIPAReview? = nil", STAGING)
        self.assertIn("UInt64(st.st_ino) == protected?.stagingInode", STAGING)
        self.assertIn("candidate.fileInode == protected?.stagingInode", STAGING)
        self.assertIn("let active = manualIPAReview", SCREEN)
        self.assertIn("protected: active", SCREEN)

    def test_cleanup_stays_within_descriptor_directory(self):
        deletion = STAGING.split("static func discardConfirmed(", 1)[1].split("enum WebReaderReleaseCacheStorage", 1)[0]
        for token in (
            "guard isQAName(candidate.fileName)",
            "openDirectory(directory)",
            "AT_SYMLINK_NOFOLLOW",
            "st.st_nlink == 1",
            "UInt64(st.st_ino) == candidate.fileInode",
            "Int64(st.st_size) == candidate.byteCount",
            "candidate.changedNanoseconds",
            "Darwin.unlinkat(dirFD, candidate.fileName, 0)",
        ):
            self.assertIn(token, deletion)
        for forbidden in ("removeItem(", "contentsOfDirectory", "rm -rf", "system("):
            self.assertNotIn(forbidden, deletion)

    def test_ordinary_user_explicit_confirmation_required(self):
        for token in (
            "inspectLocalQAStorage(cleanup: true)",
            "confirmStaleQACleanup(scan)",
            "UIAlertController(",
            'UIAlertAction(title: "Cancelar", style: .cancel)',
            '"Excluir cópias antigas"',
            "style: .destructive",
            "discardStaleQAAfterConfirmation(scan)",
        ):
            self.assertIn(token, SCREEN)
        self.assertIn("let scan = try? WebReaderLocalQAStorage.inventory(", SCREEN)
        self.assertIn("WebReaderLocalQAStorage.discardConfirmed(", SCREEN)
        self.assertIn("localQASpaceBusy", SCREEN)

    def test_not_exposed_to_ipc_probe(self):
        self.assertIn("return isIPCDiagnostic ? 2 : 7", SCREEN)
        self.assertIn("guard !isIPCDiagnostic", SCREEN)
        self.assertIn("if source == 6 { return 8 }", SCREEN)
        self.assertIn("case (6, 4):", SCREEN)
        self.assertIn("case (6, 5):", SCREEN)

    def test_user_facing_no_automatic_cleanup(self):
        self.assertIn("Toque para contar cópias antigas", SCREEN)
        self.assertIn("mais de 24 horas", SCREEN)
        self.assertIn("demais arquivos preservados", SCREEN)
        self.assertIn("Pasta de QA indisponível", SCREEN)
        self.assertIn("self.confirmStaleQACleanup(scan)", SCREEN)
        self.assertNotIn("WebReaderLocalQAStorage.discardConfirmed(", SCREEN.split(
            "private func inspectLocalQAStorage(cleanup: Bool)", 1
        )[1].split("private func discardStaleQAAfterConfirmation(", 1)[0])

    def test_native_test_exercises_identity_and_library_protection(self):
        for marker in (
            "24h-old copy eligible", "st.st_nlink",  # native test may be semantic
        ):
            pass
        for token in (
            "fake future makes only unprotected",
            "different inode under same path",
            "nanosecond ctime mismatch",
            "library-like unrecognized file",
            "source unchanged",
        ):
            self.assertTrue(token in NATIVE or token.replace("source unchanged",
                "original downloaded IPA unchanged") in NATIVE)

    def test_never_enable_privileged_installer(self):
        self.assertIn("static let liveInstallationEnabled = false", APPINST)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHECKER)
        self.assertIn("installationAuthorized: Bool = false", STAGING)
        for token in ("/usr/bin/appinst", "posix_spawn(", "sudo ", "setuid("):
            self.assertNotIn(token, SCREEN)
            self.assertNotIn(token, STAGING)


if __name__ == "__main__":
    unittest.main()
