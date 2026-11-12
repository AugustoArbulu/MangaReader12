#!/usr/bin/env python3
"""DM: source contract and disposable real Swift migration/offline fixture.

Never reads or modifies installed WebReader data. The host test demonstrates
the actual Swift source's in-place v1 SQLite *reopen*, not an iOS upgrade.
"""
import ast
from pathlib import Path
import shutil
import sys
import tempfile
import unittest

from build70_dm_real_swift_preservation_fixture import (
    BACKUP, DB, DOWNLOADS, INVENTORY, RECEIPT, STORAGE,
    DMRejected, SWIFT_TEST, audited_swift_sources, inspect_source_only
)

ROOT = Path(__file__).resolve().parent.parent


class DMSourceAndNoDeviceAuthorityTests(unittest.TestCase):
    def fixture(self):
        temporary = tempfile.TemporaryDirectory(prefix="wr-dm-test-src-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        for relative in (BACKUP, DB, DOWNLOADS, INVENTORY, RECEIPT, STORAGE):
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / relative, target)
        return root

    def change(self, root, relative, old, new):
        file = root / relative
        original = file.read_text(encoding="utf-8")
        self.assertIn(old, original)
        file.write_text(original.replace(old, new, 1), encoding="utf-8")

    def test_real_production_swift_extractions_have_expected_boundaries(self):
        parts = audited_swift_sources()
        self.assertEqual(len(parts), 4)
        self.assertIn("final class SQLiteDatabase {", parts[0])
        self.assertIn("enum SQLiteDatabaseError:", parts[0])
        self.assertIn("enum OfflineDownloadPath", parts[1])
        self.assertIn("enum WebReaderOfflinePageInventory", parts[2])
        self.assertIn("enum WebReaderOfflineCompletionReceipt", parts[3])

    def test_source_receipt_cannot_claim_install_or_physical_evidence(self):
        receipt = inspect_source_only()
        self.assertEqual(receipt["status"], "DM_SOURCE_SCHEMA_V1_AND_OFFLINE_INVARIANTS_ONLY")
        self.assertEqual(receipt["databaseSchema"], 1)
        self.assertEqual(receipt["sourceSectionCount"], 4)
        for name in (
            "realSQLiteDataContentsVerifiedOnPhysicalIPad",
            "appContainerAfterUpgradeRetainedProven",
            "offlineImageDecodingVerified", "realBuild71InstallationTested",
            "ownerApprovalForQARecorded", "readyToDistributeIPA",
            "readyToInstall", "installationAuthorized",
            "installationPerformed",
        ):
            self.assertIs(receipt[name], False, name)

    def test_database_current_schema_bump_requires_review(self):
        src = self.fixture()
        self.change(src, DB,
                    "static let currentSchemaVersion = 1",
                    "static let currentSchemaVersion = 2")
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_database_schema_removing_library_table_rejected(self):
        src = self.fixture()
        self.change(src, DB,
                    "CREATE TABLE IF NOT EXISTS library (",
                    "DROP TABLE IF EXISTS library;")
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_database_open_and_migrate_guard_must_remain(self):
        src = self.fixture()
        self.change(src, DB,
                    "guard version < Self.currentSchemaVersion else { return }",
                    "guard version <= Self.currentSchemaVersion else { return }")
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_database_future_schema_gate_refuses_unsupported_versions(self):
        root = self.fixture()
        self.change(root, DB,
                    "throw SQLiteDatabaseError.unsupportedSchemaVersion(foundVersion)",
                    "// future schema gate bypassed")
        with self.assertRaises(DMRejected):
            audited_swift_sources(root)
        root = self.fixture()
        self.change(root, DB,
                    "throw SQLiteDatabaseError.unsupportedSchemaVersion(version)",
                    "// future schema migration is incorrectly skipped")
        with self.assertRaises(DMRejected):
            audited_swift_sources(root)

    def test_native_swift_fixture_rejects_future_schema_without_data_loss(self):
        self.assertIn('PRAGMA user_version = 2;', SWIFT_TEST)
        self.assertIn('catch SQLiteDatabaseError.unsupportedSchemaVersion(let version)', SWIFT_TEST)
        self.assertIn('Array(preserved.dropFirst()) == Array(before.dropFirst())', SWIFT_TEST)
        self.assertIn('PRAGMA user_version = 1;', SWIFT_TEST)
        self.assertIn('future SQLite schema 2 accepted by v1 reader', SWIFT_TEST)

    def test_database_migration_must_remain_transactional(self):
        src = self.fixture()
        self.change(src, DB, 'try executeUnlocked("BEGIN IMMEDIATE TRANSACTION;")',
                    'try executeUnlocked("BEGIN DEFERRED;")')
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_current_container_download_root_must_be_stable(self):
        src = self.fixture()
        self.change(src, DOWNLOADS,
                    'appendingPathComponent("Downloads", isDirectory: true)',
                    'appendingPathComponent("Downloads-v2", isDirectory: true)')
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_offline_path_must_keep_safe_components(self):
        src = self.fixture()
        self.change(src, DOWNLOADS,
                    "safeComponent(chapterID)", "chapterID")
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_page_inventory_rejects_symlink_and_zero_length(self):
        src = self.fixture()
        self.change(src, INVENTORY,
                    "meta.isSymbolicLink != true", "meta.isSymbolicLink == true")
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_completion_receipt_must_check_actual_page_count(self):
        src = self.fixture()
        self.change(src, RECEIPT,
                    'text == prefix + String(actualPages) + "\\n"',
                    'text == "ALWAYS_TRUE"')
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_destructive_backup_restore_behavior_must_be_visible(self):
        src = self.fixture()
        self.change(src, BACKUP,
                    "try clearExcludedDownloadFiles()", "// removed")
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_storage_clear_downloads_method_cannot_move_silently(self):
        src = self.fixture()
        self.change(src, STORAGE,
                    "try downloadsRepository.clearAll()", "// no operation")
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_linked_swift_fixture_is_fictional_and_not_real_user_data(self):
        self.assertIn("Fictional title", SWIFT_TEST)
        self.assertIn("Synthetic chapter", SWIFT_TEST)
        self.assertIn("CURRENT temp Application Support", SWIFT_TEST)
        self.assertIn("WebReaderOfflinePageInventory.inspect", SWIFT_TEST)
        self.assertIn("WebReaderOfflineCompletionReceipt.verifyIfPresent", SWIFT_TEST)
        self.assertIn("old.close()", SWIFT_TEST)
        self.assertIn("reopened.openAndMigrate()", SWIFT_TEST)
        self.assertNotIn("appinst", SWIFT_TEST)
        self.assertNotIn("filza", SWIFT_TEST.lower())

    def test_missing_swift_source_file_is_rejected(self):
        src = self.fixture()
        (src / RECEIPT).unlink()
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_symlinked_download_resolver_source_is_rejected(self):
        src = self.fixture()
        f = src / DOWNLOADS
        shadow = f.with_suffix(".original")
        f.rename(shadow)
        f.symlink_to(shadow)
        with self.assertRaises(DMRejected):
            audited_swift_sources(src)

    def test_no_packaging_ipc_installer_or_release_calls_in_audit(self):
        source = (ROOT / "ci/build70_dm_real_swift_preservation_fixture.py").read_text()
        tree = ast.parse(source)
        calls = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                if isinstance(n.func, ast.Name):
                    calls.add(n.func.id)
                elif isinstance(n.func, ast.Attribute):
                    calls.add(n.func.attr)
        for banned in ("appinst", "installApplication", "socket", "connect",
                       "codesign", "publish_release", "upload_artifact",
                       "make_archive", "ZipFile", "unlink", "rmtree"):
            with self.subTest(banned=banned):
                self.assertNotIn(banned, calls)

    def test_native_fixture_must_not_claim_ipa_distribution(self):
        source = (ROOT / "ci/build70_dm_real_swift_preservation_fixture.py").read_text()
        for exact in (
            '"realDeviceIOS12ExecutionProven": False',
            '"realAppUpgradePreservationProven": False',
            '"actualUserLibraryVerified": False',
            '"realOfflineImageDecodingProven": False',
            '"publisherAuthenticated": False',
            '"ownerDistributionApprovalRecorded": False',
            '"readyToDistributeIPA": False',
            '"readyToInstall": False',
            '"installationAuthorized": False',
            '"installationPerformed": False',
        ):
            self.assertIn(exact, source)


if __name__ == "__main__":
    unittest.main()
