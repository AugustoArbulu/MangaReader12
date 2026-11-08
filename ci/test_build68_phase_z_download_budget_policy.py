#!/usr/bin/env python3
"""Build68 Phase Z: downloaded IPA must not threaten offline chapter storage."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
STAGER = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
BUDGET = (ROOT / "MangaReader12/Core/WebReaderIPADownloadBudget.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
CHECKER = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_ipa_download_budget.py").read_text()
INTEGRATION = (ROOT / "ci/test_native_webreader_ipa_stager.py").read_text()


class DownloadBudgetContract(unittest.TestCase):
    def test_budget_source_is_in_ios12_target(self):
        name = "WebReaderIPADownloadBudget.swift"
        self.assertEqual(PROJECT.count(f"{name} in Sources"), 2)
        self.assertIn(f"A20000000000000000000040 /* {name} */,", PROJECT)
        self.assertIn(f"A10000000000000000000040 /* {name} in Sources */,", PROJECT)

    def test_bounded_free_space_formula_and_fail_closed_directory(self):
        for value in (
            "maximumIPASize: Int64 = 512 * 1024 * 1024",
            "minimumReserve: Int64 = 32 * 1024 * 1024",
            "overheadReserve: Int64 = 8 * 1024 * 1024",
            "ipaBytes / 8",
            "ipaBytes.addingReportingOverflow(reserve)",
            "Darwin.open(", "O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW",
            "Darwin.fstat(fd, &descriptorStat)",
            "Darwin.fstatfs(fd, &volume)",
            ".multipliedReportingOverflow(by:",
        ):
            with self.subTest(value=value):
                self.assertIn(value, BUDGET)

    def test_preflight_runs_before_creating_partial_ipa_or_network(self):
        before = STAGER.split("func stage(completion", 1)[1].split(
            "func cancel()", 1
        )[0]
        i_budget = before.index("WebReaderIPADownloadBudget.enoughSpace(")
        i_partial = before.index('".webreader-" + UUID().uuidString')
        i_request = before.index("newSession.dataTask(with: request)")
        i_resume = before.index("task.resume()")
        self.assertTrue(i_budget < i_partial < i_request < i_resume)
        self.assertIn("callback(.failed(.insufficientSpace))", before)
        self.assertIn("callback(.failed(.storage))", before)
        self.assertIn("testProtocolClasses == nil ? nil : testAvailableSpace", STAGER)

    def test_percent_is_throttled_and_never_claims_final_integrity(self):
        for value in (
            "lastProgressBucket = 0",
            "let bucket = min(19, percent / 5)",
            "progressPercent = min(95, bucket * 5)",
            "onProgress?(percent)",
            "Recebidos ", "% • hash e ZIP são conferidos ao concluir",
            "downloadSessionID == id",
            "self.downloadSessionID = nil",
            "Espaço livre insuficiente • preserve os capítulos offline",
        ):
            with self.subTest(value=value):
                self.assertIn(value, STAGER + UI)

    def test_native_budget_and_network_mock_negative_cases(self):
        for label in (
            "symlink directory denied",
            "one byte below threshold denied",
            "no automatic mkdir",
            "over 512 MiB denied",
        ):
            self.assertIn(label, NATIVE)
        for label in (
            "low-space download was not refused",
            "low-space admission must not request network bytes",
            "insufficient space must not leave partial files",
            "transfer progress bounded at 95 until integrity finalized",
            "download progress monotonic",
        ):
            self.assertIn(label, INTEGRATION)

    def test_library_code_install_and_publisher_identity_untouched(self):
        self.assertNotIn("Library.sqlite", BUDGET)
        for forbidden in (
            "removeItem(", "unlinkat(", "deleteFile(", "posix_spawn(",
            "appinst(", "URLSession(", "FileHandle(", "FileManager.default.remove",
        ):
            self.assertNotIn(forbidden, BUDGET)
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHECKER)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)


if __name__ == "__main__":
    unittest.main()
