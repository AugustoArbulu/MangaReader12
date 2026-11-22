#!/usr/bin/env python3
"""Future Build69 AG/AH/AI: cancel-vs-commit, stale progress, storage headroom."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
STAGER = (ROOT / "MangaReader12/Core/WebReaderIPAStager.swift").read_text()
BUDGET = (ROOT / "MangaReader12/Core/WebReaderIPADownloadBudget.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_ipa_stager.py").read_text()
BUDGET_NATIVE = (ROOT / "ci/test_native_webreader_ipa_download_budget.py").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
CHANNEL = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()


class RaceSafeIPAStaging(unittest.TestCase):
    def test_cancel_commits_decision_before_stopping_transport(self):
        code = STAGER.split("    func cancel() {", 1)[1].split(
            "    /// iOS 12 compatible response-header", 1
        )[0]
        for token in (
            "guard let active = currentTask, completion != nil,",
            "!cancelRequested",
            "cancelRequested = true",
            "stateLock.unlock()",
            "active.cancel()",
            "finish(.failed(.cancelled))",
        ):
            self.assertIn(token, code)
        self.assertLess(code.index("cancelRequested = true"), code.index("active.cancel()"))
        self.assertLess(code.index("active.cancel()"), code.index("finish(.failed(.cancelled))"))

    def test_atomic_checked_promotion_and_exactly_once_completion(self):
        after = STAGER.split("beforeFinalCommit?()", 1)[1].split(
            "    private func finish(", 1
        )[0]
        for marker in (
            "defer { afterFinalCommit?() }",
            "stateLock.lock()",
            "guard currentTask === task, completion != nil,",
            "!cancelRequested, partialURL == fileURL",
            "try FileManager.default.moveItem(at: fileURL, to: destination)",
            "partialURL = nil",
            "currentTask = nil",
            "stateLock.unlock()",
            "finish(.staged(destination))",
        ):
            self.assertIn(marker, after)
        self.assertLess(after.index("stateLock.lock()"),
                        after.index("try FileManager.default.moveItem("))
        self.assertLess(after.index("currentTask = nil"),
                        after.index("finish(.staged(destination))"))
        finishing = STAGER.split(
            "    private func finish(_ result: WebReaderIPAStageResult) {", 1
        )[1].split("// MARK: - iOS12 local QA", 1)[0]
        for marker in (
            "let resolved: WebReaderIPAStageResult =",
            "cancelRequested ? .failed(.cancelled) : result",
            "completion = nil",
            "currentTask = nil",
            "oldSession?.invalidateAndCancel()",
            "if let temp = temp { try? FileManager.default.removeItem(at: temp) }",
            "callback?(resolved)",
        ):
            self.assertIn(marker, finishing)

    def test_test_only_race_hooks_cannot_run_on_production_transport(self):
        for token in (
            "self.beforeFinalCommit = testProtocolClasses == nil ? nil : beforeFinalCommit",
            "self.afterFinalCommit = testProtocolClasses == nil ? nil : afterFinalCommit",
            "self.testFreeBytesSampler = testProtocolClasses == nil ?",
            "nil : testFreeBytesSampler",
        ):
            self.assertIn(token, STAGER)
        self.assertIn("guard currentTask == nil && completion == nil", STAGER)
        for marker in (
            "cancel WHILE the verified ZIP",
            "cancellation between full ZIP audit and rename must not orphan .ipa",
            "retry of same stager yields identical validated bytes",
            "cancel after successful final commit does not remove IPA",
            "verified full ZIP reached final promotion decision",
        ):
            self.assertIn(marker, NATIVE)

    def test_cancellation_invalidates_queued_progress_both_ways(self):
        nav = UI.split("override func viewWillDisappear", 1)[1].split(
            "override func numberOfSections", 1
        )[0]
        self.assertIn("downloadSessionID = nil", nav)
        self.assertLess(nav.index("downloadSessionID = nil"), nav.index("stager?.cancel()"))
        tap = UI.split('ipaStatus = "Cancelando transferência', 1)[1].split(
            "tableView.reloadData()", 1
        )[0]
        self.assertIn("downloadSessionID = nil", tap)
        self.assertLess(tap.index("downloadSessionID = nil"), tap.index("stager?.cancel()"))
        self.assertIn("self.downloadSessionID == id", UI)
        self.assertIn("self.stager === downloader", UI)


class DownloadPreservesOfflineSpace(unittest.TestCase):
    def test_preserve_original_ipa_reserve_during_transfer(self):
        for token in (
            "static func enoughSpaceDuringTransfer(",
            "remainingBytes: Int64, totalIPABytes: Int64",
            "remainingBytes <= totalIPABytes",
            "let reserve = max(minimumReserve, totalIPABytes / 8)",
            "remainingBytes.addingReportingOverflow(reserve)",
            "first.addingReportingOverflow(overheadReserve)",
        ):
            self.assertIn(token, BUDGET)
        active = STAGER.split("didReceive data: Data", 1)[1].split(
            "didCompleteWithError error:", 1
        )[0]
        for token in (
            "count == 0 || count - lastSpaceCheckAt >= 4 * 1024 * 1024",
            "WebReaderIPADownloadBudget.enoughSpaceDuringTransfer(",
            "remainingBytes: update.ipaSize - count",
            "totalIPABytes: update.ipaSize",
            "finish(.failed(.insufficientSpace))",
            "lastSpaceCheckAt = count",
        ):
            self.assertIn(token, active)
        self.assertLess(active.index("enoughSpaceDuringTransfer("),
                        active.index("let success = data.withUnsafeBytes"))
        for marker in (
            "mid-transfer loss of safety reserve",
            "mid-transfer low-space failure removes only private .partial",
            "sampled before GET and during first chunk",
        ):
            self.assertIn(marker, NATIVE)
        for marker in (
            "exact original budget remains after last chunk",
            "cannot spend fixed original safety reserve on the final chunk",
            "invalid remaining bytes denied",
        ):
            self.assertIn(marker, BUDGET_NATIVE)

    def test_preserve_owner_build68_and_install_disabled(self):
        self.assertEqual(PROJECT.count("CURRENT_PROJECT_VERSION = 56;"), 2)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", CHANNEL)
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)
        self.assertNotIn("appinst(", BUDGET)
        self.assertNotIn("removeItem(", BUDGET)
        self.assertNotIn("posix_spawn(", STAGER)


if __name__ == "__main__":
    unittest.main()
