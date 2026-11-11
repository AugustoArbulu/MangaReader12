#!/usr/bin/env python3
"""Build70/DN tests: no destructive call at launch or passive update viewing.

Mocked source mutations only. These are narrow source guards, not a full
Swift data-flow analysis or proof about the physical iPad's private data.
"""
import ast
from pathlib import Path
import shutil
import tempfile
import unittest

from build70_dn_startup_data_guard import (
    DNRejected, APP, TABS, UPDATES, BACKUP_UI, STORAGE_UI,
    BACKUP_CORE, STORAGE_CORE, CHANNEL, PUBLISHER, INSTALLER,
    audit_upgrade_launch_safety,
)

ROOT = Path(__file__).resolve().parent.parent
ALL = (APP, TABS, UPDATES, BACKUP_UI, STORAGE_UI,
       BACKUP_CORE, STORAGE_CORE, CHANNEL, PUBLISHER, INSTALLER)


class DNNonDestructiveLaunchHostTests(unittest.TestCase):
    def fixture(self):
        temp = tempfile.TemporaryDirectory(prefix="wr-dn-startup-host-")
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for path in ALL:
            dest = root / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, dest)
        return root

    def mutate(self, base, file, before, after):
        path = base / file
        original = path.read_text()
        self.assertIn(before, original, (file, before))
        path.write_text(original.replace(before, after, 1))

    def test_original_app_guards_pass_without_install_permission(self):
        receipt = audit_upgrade_launch_safety()
        self.assertEqual(receipt["status"], "DN_SOURCE_STARTUP_DESTRUCTIVE_CALL_GATE_PASSED_HOST_ONLY")
        self.assertEqual(receipt["checkedStartAndViewLifecycleSections"], 7)
        self.assertTrue(receipt["backupRestoreRequiresManualDestructiveConfirmationBySourceInspection"])
        self.assertTrue(receipt["clearAllDownloadsRequiresManualDestructiveConfirmationBySourceInspection"])
        self.assertTrue(receipt["downloadReindexRequiresManualDestructiveConfirmationBySourceInspection"])
        for key in (
            "automaticCleanupOnUpdaterOpenDetected",
            "directDestructiveCallInCheckedStartupSectionsDetected",
            "runtimeInvocationGraphProven",
            "deviceDataUnchangedProvenByThisHostCheck",
            "iOS12InstallerBehaviorProven",
            "actualPhysicalBuild71UpgradeTested",
            "ownerDistributionApprovalRecorded",
            "publisherAuthenticityProven",
            "readyToDistributePrivateIPA",
            "readyToInstall", "installationAuthorized",
            "installationPerformed",
        ):
            self.assertIs(receipt[key], False, key)

    def test_bootstrapping_direct_download_eraser_is_rejected(self):
        root = self.fixture()
        self.mutate(root, APP, "ThemeManager.shared.applyGlobalAppearance()",
                    "StorageManager.defaultManager()?.clearAllDownloads()\n"
                    "        ThemeManager.shared.applyGlobalAppearance()")
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_main_tab_auto_reindex_in_view_did_load_rejected(self):
        root = self.fixture()
        self.mutate(root, TABS, "        super.viewDidLoad()",
                    "        reindexDownloads()\n        super.viewDidLoad()")
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_updates_view_entry_must_not_auto_clean_download_files(self):
        root = self.fixture()
        self.mutate(root, UPDATES,
                    "inspectReleaseCache(cleanup: false)",
                    "inspectReleaseCache(cleanup: true)")
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_updates_view_load_cannot_auto_restore_backup(self):
        root = self.fixture()
        self.mutate(root, UPDATES,
                    '        title = "Atualizações do WebReader"',
                    '        restoreBackup(from: candidate)\n'
                    '        title = "Atualizações do WebReader"')
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_storage_screen_load_cannot_clear_downloads(self):
        root = self.fixture()
        self.mutate(root, STORAGE_UI, "        refreshSnapshot()",
                    "        clearAllDownloads()\n        refreshSnapshot()")
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_backup_screen_load_cannot_auto_restore(self):
        root = self.fixture()
        self.mutate(root, BACKUP_UI, '        title = "Backup e restauração"',
                    "        restoreBackup(from: hidden)\n"
                    '        title = "Backup e restauração"')
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_backup_confirmation_must_remain_destructive_action(self):
        root = self.fixture()
        self.mutate(root, BACKUP_UI,
                    'title: "Restaurar e apagar downloads", style: .destructive',
                    'title: "Restaurar e apagar downloads", style: .default')
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_backup_restore_cannot_be_invoked_outside_confirmation(self):
        root = self.fixture()
        self.mutate(root, BACKUP_UI,
                    "            self.performSelectedBackupRestore(from: url)",
                    "            self.performSelectedBackupRestore(from: otherURL)")
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_download_reindex_confirmation_must_remain_destructive(self):
        root = self.fixture()
        self.mutate(root, STORAGE_UI,
                    'UIAlertAction(title: "Reindexar mesmo assim", style: .destructive)',
                    'UIAlertAction(title: "Reindexar mesmo assim", style: .default)')
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_download_deletion_warning_must_remain_visible(self):
        root = self.fixture()
        self.mutate(root, STORAGE_UI,
                    'title: "Apagar todos os downloads?"',
                    'title: "Realizar manutenção?"')
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_backup_restore_wipe_danger_must_be_revisited_if_changed(self):
        root = self.fixture()
        self.mutate(root, BACKUP_CORE,
                    "try clearExcludedDownloadFiles()",
                    "// dangerous side-effect removed")
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_backup_core_and_storage_core_wipe_are_not_silently_renamed(self):
        root = self.fixture()
        self.mutate(root, STORAGE_CORE,
                    "try downloadsRepository.clearAll()",
                    "// moved")
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_default_deny_production_install_and_publisher_switches(self):
        for name, original, new in (
            (CHANNEL, "static let productionPublicKeyX963: Data? = nil",
             "static let productionPublicKeyX963: Data? = Data([1])"),
            (PUBLISHER, "static let independentlyProvisionedSPKISHA256: String? = nil",
             'static let independentlyProvisionedSPKISHA256: String? = "FORGED"'),
            (INSTALLER, "static let liveInstallationEnabled = false",
             "static let liveInstallationEnabled = true"),
        ):
            with self.subTest(name=name):
                root = self.fixture()
                self.mutate(root, name, original, new)
                with self.assertRaises(DNRejected):
                    audit_upgrade_launch_safety(root)

    def test_missing_or_symlinked_source_is_rejected(self):
        root = self.fixture()
        file = root / APP
        original = file.with_suffix(".old")
        file.rename(original)
        file.symlink_to(original)
        with self.assertRaises(DNRejected):
            audit_upgrade_launch_safety(root)

    def test_report_does_not_execute_installer_or_network(self):
        source = (ROOT / "ci/build70_dn_startup_data_guard.py").read_text()
        tree = ast.parse(source)
        calls = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    calls.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    calls.add(node.func.attr)
        for forbidden in (
            "appinst", "installApplication", "posix_spawn",
            "system", "Popen", "request", "upload_artifact",
            "publish_release", "unlink", "remove", "write_bytes",
            "write_text", "rename", "make_archive", "ZipFile"
        ):
            self.assertNotIn(forbidden, calls)
        for negative in (
            '"ownerDistributionApprovalRecorded": False',
            '"readyToDistributePrivateIPA": False',
            '"installationAuthorized": False',
            '"installationPerformed": False',
            '"runtimeInvocationGraphProven": False',
        ):
            self.assertIn(negative, source)


if __name__ == "__main__":
    unittest.main()
