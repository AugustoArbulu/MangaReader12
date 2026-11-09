#!/usr/bin/env python3
"""Build69 BG: Native UIKit continuity collection must not block iOS12 main UI."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()


class NonblockingReadOnlySnapshotUI(unittest.TestCase):
    def test_background_sqlite_and_main_thread_clipboard_only(self):
        body = UI.split("private func copyUpgradeContinuitySnapshot() {", 1)[1].split(
            "private func copySignedChannelReadinessReport()", 1
        )[0]
        for marker in (
            "guard !isIPCDiagnostic, !continuitySnapshotBusy else { return }",
            "continuitySnapshotBusy = true",
            "continuitySnapshotBusy = false",
            "let currentBuild = installedBuild",
            "let ios = ProcessInfo.processInfo.operatingSystemVersion",
            "DispatchQueue.global(qos: .utility).async { [weak self] in",
            "WebReaderUpgradeContinuitySnapshot.report(",
            "DispatchQueue.main.async {",
            "guard self.view.window != nil else { return }",
            "UIPasteboard.general.string = report",
            "self.present(alert, animated: true)"
        ):
            self.assertIn(marker, body, marker)
        self.assertLess(body.index("DispatchQueue.global"),
                        body.index("WebReaderUpgradeContinuitySnapshot.report("))
        self.assertLess(body.index("WebReaderUpgradeContinuitySnapshot.report("),
                        body.index("DispatchQueue.main.async"))
        self.assertLess(body.index("DispatchQueue.main.async"),
                        body.index("UIPasteboard.general.string = report"))
        self.assertLess(body.index("self.continuitySnapshotBusy = false"),
                        body.index("UIPasteboard.general.string = report"))
        for forbidden in ("appinst(", "URLSession(", "removeItem(", "UserDefaults"):
            self.assertNotIn(forbidden, body)

    def test_single_row_disabled_during_snapshot_and_isolated_from_ipc_diagnostic(self):
        row = UI.split("case (3, 6):", 1)[1].split("case (4, 0):", 1)[0]
        self.assertIn('Copiar contagens da biblioteca para comparar', row)
        self.assertIn("continuitySnapshotBusy ?", row)
        self.assertIn("if !continuitySnapshotBusy", row)
        self.assertIn("cell.accessoryType = .disclosureIndicator", row)
        self.assertIn("cell.selectionStyle = .default", row)
        self.assertIn("if source == 3 { return 8 }", UI)
        self.assertIn("return isIPCDiagnostic ? 2 : 7", UI)
        self.assertIn("if selectedSection == 3, indexPath.row == 6, !isIPCDiagnostic {", UI)


if __name__ == "__main__":
    unittest.main()
