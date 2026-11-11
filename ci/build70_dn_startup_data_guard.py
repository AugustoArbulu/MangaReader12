#!/usr/bin/env python3
"""WebReader Build70/DN — conservative, source-only destructive startup gate.

Rejects new direct destructive calls in narrowly selected UI lifecycle
handlers or weakening of user confirmation around backup restoration and
offline deletion. This is NOT a Swift call graph, cannot prove runtime
behavior, does not inspect device data, and cannot authorize QA distribution
or automatic installation. A changed code shape fails CLOSED for review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
APP = "MangaReader12/AppDelegate.swift"
TABS = "MangaReader12/UI/MainTabBarController.swift"
UPDATES = "MangaReader12/UI/WebReaderAppUpdatesViewController.swift"
BACKUP_UI = "MangaReader12/UI/BackupViewController.swift"
STORAGE_UI = "MangaReader12/UI/DataStorageViewController.swift"
BACKUP_CORE = "MangaReader12/Core/BackupManager.swift"
STORAGE_CORE = "MangaReader12/Core/StorageManager.swift"
CHANNEL = "MangaReader12/Core/WebReaderUpdateChecker.swift"
PUBLISHER = "MangaReader12/Core/WebReaderProductionPublisherTrust.swift"
INSTALLER = "MangaReader12/Core/WebReaderAppinstSocket.swift"


class DNRejected(ValueError):
    pass


def _read(root: Path, relative: str) -> str:
    p = root / relative
    if p.is_symlink() or not p.is_file():
        raise DNRejected("required source file missing or symlinked: " + relative)
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise DNRejected("unreadable Swift source: " + relative) from exc
    if not text or len(text) > 500_000 or "\x00" in text:
        raise DNRejected("invalid or oversized source: " + relative)
    return text


def _unique_section(source: str, first: str, last: str) -> str:
    if source.count(first) != 1 or source.count(last) != 1:
        raise DNRejected("startup or user confirmation method shape changed")
    begin = source.index(first)
    end = source.index(last, begin + len(first))
    if end <= begin:
        raise DNRejected("lifecycle method ordering changed")
    return source[begin:end]


DESTRUCTIVE_DIRECT_CALLS = (
    "restoreBackup", "clearAllDownloads", "reindexDownloads",
    "removeMissingFiles", "clearExcludedDownloadFiles",
    "clearReaderCache", "clearCoverCache",
    "removeItem", "removeItemAtPath", "unlink",
    "deleteAll", "resetLibrary", "purgeDownloads",
    "installApplication", "installIPA", "appinst",
)


def _deny_destructive_calls(section: str, context: str) -> None:
    # Source-only approximate call guard. False positives require code
    # review; this is not an abstract syntax tree / whole-program analysis.
    for candidate in DESTRUCTIVE_DIRECT_CALLS:
        if re.search(r"\b" + re.escape(candidate) + r"\s*\(", section):
            raise DNRejected("direct destructive call in " + context + ": " + candidate)


def audit_upgrade_launch_safety(root: Path = ROOT) -> dict:
    app = _read(root, APP)
    tabs = _read(root, TABS)
    updates = _read(root, UPDATES)
    backup_ui = _read(root, BACKUP_UI)
    storage_ui = _read(root, STORAGE_UI)
    backup_core = _read(root, BACKUP_CORE)
    storage_core = _read(root, STORAGE_CORE)
    channel = _read(root, CHANNEL)
    publisher = _read(root, PUBLISHER)
    installer = _read(root, INSTALLER)

    sections = (
        (_unique_section(app, "    func application(\n        _ application: UIApplication,\n        didFinishLaunchingWithOptions",
                         "    func application(\n        _ application: UIApplication,\n        performFetchWithCompletionHandler"), "AppDelegate launch"),
        (_unique_section(tabs, "    override func viewDidLoad() {", "\n    deinit {"),
         "MainTabBarController first load"),
        (_unique_section(updates, "    override func viewDidLoad() {",
                         "    override func viewDidAppear(_ animated: Bool) {"),
         "WebReader Updates first load"),
        (_unique_section(updates, "    override func viewDidAppear(_ animated: Bool) {",
                         "    override func viewWillDisappear(_ animated: Bool) {"),
         "WebReader Updates appear"),
        (_unique_section(storage_ui, "    override func viewDidLoad() {",
                         "    override func viewWillAppear(_ animated: Bool) {"),
         "Storage UI first load"),
        (_unique_section(storage_ui, "    override func viewWillAppear(_ animated: Bool) {",
                         "    override func numberOfSections(in tableView: UITableView) -> Int {"),
         "Storage UI appear"),
        (_unique_section(backup_ui, "    override func viewDidLoad() {",
                         "    override func numberOfSections(in tableView: UITableView) -> Int {"),
         "Backup UI first load"),
    )
    for body, name in sections:
        _deny_destructive_calls(body, name)

    # The updater may scan stale PARTIAL files on entry, but cannot
    # clean them as a side effect of opening the screen.
    if 'inspectReleaseCache(cleanup: false)' not in sections[3][0]:
        raise DNRejected("recovery inspection on Updates screen no longer cleanup=false")
    if "didInspectRecoveryOnOpen = true" not in sections[3][0]:
        raise DNRejected("updater recovery once-only inspection changed")
    if "BackgroundLibraryUpdateManager.shared.applyScheduling()" not in sections[0][0]:
        raise DNRejected("launch scheduling changed: require manual review")

    # Backup restore remains allowed only after owner document selection
    # AND a destructive confirm dialog, never by app launch or QA scripts.
    restore_method = "    private func performSelectedBackupRestore(from url: URL) {"
    if backup_ui.count(restore_method) != 1:
        raise DNRejected("backup restore method changed")
    if backup_ui.count("            self.performSelectedBackupRestore(from: url)") != 1:
        raise DNRejected("backup restore action call changed")
    if backup_ui.count("let report = try manager.restoreBackup(from: url)") != 1:
        raise DNRejected("backup API call count changed")
    if not all(token in backup_ui for token in (
        'title: "Restaurar backup e remover downloads?"',
        'title: "Restaurar e apagar downloads", style: .destructive',
        "guard !restoring, !restoreConfirmationPending else { return }",
        "restoreConfirmationPending = true",
        "self.restoreConfirmationPending = false",
        "private func performSelectedBackupRestore(from url: URL)",
        "O backup .mr12backup não contém páginas.",
    )):
        raise DNRejected("explicit backup restore confirmation/warning changed")
    pick = _unique_section(
        backup_ui, "    func documentPicker(\n", "    private func performSelectedBackupRestore("
    )
    if not re.search(
        r'title: "Restaurar e apagar downloads", style: \.destructive'
        r'\s*\) \{ \[weak self\] _ in'
        r'(?:(?!\n    \}).)*self\.performSelectedBackupRestore\(from: url\)',
        pick, flags=re.S,
    ):
        raise DNRejected("backup restoration no longer behind destructive confirmation")

    # Reindexing can delete database records, clearing removes offline pages.
    # Both operations remain explicit UI actions with destructive warning.
    if storage_ui.count("try manager.reindexDownloads()") != 1:
        raise DNRejected("manual download reindex action changed")
    if storage_ui.count("try manager.clearAllDownloads()") != 1:
        raise DNRejected("manual clear-all action changed")
    if not all(token in storage_ui for token in (
        'title: "Reindexar e remover registros?"',
        'UIAlertAction(title: "Reindexar mesmo assim", style: .destructive)',
        'title: "Apagar todos os downloads?"',
        'title: "Apagar",',
        'style: .destructive',
        "confirmReindexDownloads()",
        "confirmClearDownloads()",
        "O .mr12backup não contém páginas offline.",
    )):
        raise DNRejected("explicit offline destructive confirmation changed")
    if 'func restoreBackup(from url: URL) throws -> BackupRestoreReport {' not in backup_core:
        raise DNRejected("backup restore contract changed")
    if ('try clearExcludedDownloadFiles()' not in backup_core
            or 'try fileManager.removeItem(at: downloads)' not in backup_core):
        raise DNRejected("backup restore erasure risk changed; manual re-review")
    if ('func clearAllDownloads() throws' not in storage_core
            or 'try downloadsRepository.clearAll()' not in storage_core):
        raise DNRejected("storage erasure contract changed; manual re-review")

    # The app's live updater is still a hard stop, not a new call path.
    for source, guard in (
        (channel, "static let productionPublicKeyX963: Data? = nil"),
        (publisher, "static let independentlyProvisionedSPKISHA256: String? = nil"),
        (installer, "static let liveInstallationEnabled = false"),
    ):
        if guard not in source:
            raise DNRejected("production publisher/installer gate changed")

    return {
        "status": "DN_SOURCE_STARTUP_DESTRUCTIVE_CALL_GATE_PASSED_HOST_ONLY",
        "checkedStartAndViewLifecycleSections": len(sections),
        "automaticCleanupOnUpdaterOpenDetected": False,
        "directDestructiveCallInCheckedStartupSectionsDetected": False,
        "backupRestoreRequiresManualDestructiveConfirmationBySourceInspection": True,
        "downloadReindexRequiresManualDestructiveConfirmationBySourceInspection": True,
        "clearAllDownloadsRequiresManualDestructiveConfirmationBySourceInspection": True,
        "backupRestoreErasesOfflineDownloadsWarningStillPresent": True,
        "runtimeInvocationGraphProven": False,
        "deviceDataUnchangedProvenByThisHostCheck": False,
        "iOS12InstallerBehaviorProven": False,
        "actualPhysicalBuild71UpgradeTested": False,
        "ownerDistributionApprovalRecorded": False,
        "publisherAuthenticityProven": False,
        "readyToDistributePrivateIPA": False,
        "readyToInstall": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.parse_args()
    try:
        print(json.dumps(audit_upgrade_launch_safety(), ensure_ascii=False,
                         indent=2, sort_keys=True))
    except DNRejected as exc:
        cli.error("BLOCKED: " + str(exc))


if __name__ == "__main__":
    main()
