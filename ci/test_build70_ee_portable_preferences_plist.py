#!/usr/bin/env python3
"""EE synthetic preference-export and binary-plist safety tests."""
import base64
import json
from pathlib import Path
import plistlib
import unittest

import test_build70_ed_portable_vs_external_library as ed_fixture
from build70_ee_portable_preferences_plist import (
    EERejected, KEYS, compare_preferences, review_external_preferences,
)

class EEPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.fixture = ed_fixture.EDPortableLibraryTests(
            "test_exact_library_rows_equal_but_not_attested")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.export = json.loads(self.fixture.backup)
        self.prefs = {
            "app.theme": "dark",
            "reader.keepScreenOn": True,
            "reader.webtoonGap": 2.5,
            "library.pinned.sources.v1": ["asura", "weebcentral"],
            "reader.tapZones": b"\x00\x01\x02",
            "reader.showPageNumber": 1,
        }
        self.encoded = {
            "app.theme": {"kind": "string", "stringValue": "dark"},
            "reader.keepScreenOn": {"kind": "bool", "boolValue": True},
            "reader.webtoonGap": {"kind": "double", "doubleValue": 2.5},
            "library.pinned.sources.v1": {
                "kind": "stringArray", "stringArrayValue": ["asura", "weebcentral"]},
            "reader.tapZones": {
                "kind": "data", "dataBase64": base64.b64encode(b"\x00\x01\x02").decode()},
            "reader.showPageNumber": {"kind": "int", "integerValue": 1},
        }
        self.dir = self.root / "Library" / "Preferences"
        self.dir.mkdir()
        self.file = self.dir / "com.example.MangaReader12.plist"
        self.file.write_bytes(plistlib.dumps(self.prefs, fmt=plistlib.FMT_BINARY))

    def backup(self, exported=None):
        self.export["preferences"] = self.encoded if exported is None else exported
        return json.dumps(self.export, sort_keys=True).encode()

    def review(self, exported=None):
        return review_external_preferences(
            self.root, self.backup(exported))

    def assert_denied(self, report):
        for name in (
            "bothInputsProvenToComeFromSameDevice",
            "inputsCapturedAtSameMomentProven",
            "physicalUserDefaultsValuesAttested",
            "offlineChapterImagesVerified",
            "completeDataContainerBackupProven",
            "readyToDistributeIPA", "readyToInstallIPA",
            "installationAuthorized", "restorationAuthorized",
            "automaticUpdaterEnabled",
        ):
            self.assertIs(report[name], False, name)

    def test_match_binary_plist_and_json_export(self):
        r = self.review()
        self.assertEqual(r["status"], "EE_EXPORTED_PREFERENCES_EQUAL_NOT_ATTESTED")
        self.assertEqual(r["preferenceKeysInPortable"], 6)
        self.assertEqual(r["preferenceKeysOnExternalPlist"], 6)
        self.assert_denied(r)

    def test_source_swift_allowlist_exact_match(self):
        source = (Path(__file__).resolve().parent.parent / "MangaReader12" /
                  "Core" / "BackupManager.swift").read_text()
        start = source.index("private let preferenceKeys = [")
        end = source.index("]", start)
        import re
        listed = re.findall(r'"([^"]+)"', source[start:end])
        self.assertEqual(tuple(listed), KEYS)

    def test_theme_change_with_same_key_count_detected(self):
        self.prefs["app.theme"] = "light"
        self.file.write_bytes(plistlib.dumps(self.prefs))
        r = self.review()
        self.assertEqual(r["status"], "EE_STOP_EXPORTED_PREFERENCES_DIFFER")
        self.assertEqual(r["differingKnownPreferenceKeys"], ["app.theme"])
        self.assert_denied(r)

    def test_same_size_data_mutation_detected(self):
        self.prefs["reader.tapZones"] = b"\x00\x01\x03"
        r = compare_preferences(self.backup(), plistlib.dumps(self.prefs))
        self.assertEqual(r["differingKnownPreferenceKeys"], ["reader.tapZones"])

    def test_boolean_must_not_match_integer(self):
        self.prefs["reader.keepScreenOn"] = 1
        r = compare_preferences(self.backup(), plistlib.dumps(self.prefs))
        self.assertEqual(r["differingKnownPreferenceKeys"], ["reader.keepScreenOn"])

    def test_string_array_order_detected(self):
        self.prefs["library.pinned.sources.v1"].reverse()
        r = compare_preferences(self.backup(), plistlib.dumps(self.prefs))
        self.assertEqual(r["differingKnownPreferenceKeys"],
                         ["library.pinned.sources.v1"])

    def test_missing_key_is_different(self):
        del self.prefs["app.theme"]
        r = compare_preferences(self.backup(), plistlib.dumps(self.prefs))
        self.assertEqual(r["differingKnownPreferenceKeys"], ["app.theme"])

    def test_unbacked_up_user_defaults_are_not_compared(self):
        self.prefs["unrelated.private.key"] = "secret-unused-value"
        r = compare_preferences(self.backup(), plistlib.dumps(self.prefs))
        self.assertEqual(r["status"], "EE_EXPORTED_PREFERENCES_EQUAL_NOT_ATTESTED")
        self.assertTrue(r["unbackedUpOtherUserDefaultsKeysNotCompared"])
        self.assertNotIn("secret-unused-value", str(r))

    def test_unknown_exported_key_rejected(self):
        exported = dict(self.encoded)
        exported["admin.forceInstall"] = {"kind": "bool", "boolValue": True}
        with self.assertRaises(EERejected) as caught:
            self.review(exported)
        self.assertEqual(caught.exception.code, "EE_STOP_UNKNOWN_EXPORTED_PREFERENCE")

    def test_malformed_base64_rejected(self):
        exported = dict(self.encoded)
        exported["reader.tapZones"] = {"kind": "data", "dataBase64": "!"}
        with self.assertRaises(EERejected) as caught:
            self.review(exported)
        self.assertEqual(caught.exception.code, "EE_STOP_INVALID_PREFERENCE_VALUE")

    def test_ambiguous_encoded_types_rejected(self):
        exported = dict(self.encoded)
        exported["app.theme"] = {
            "kind": "string", "stringValue": "dark", "boolValue": True}
        with self.assertRaises(EERejected) as caught:
            self.review(exported)
        self.assertEqual(caught.exception.code, "EE_STOP_AMBIGUOUS_PREFERENCE_VALUE")

    def test_missing_plist_does_not_prove_missing_preferences(self):
        self.file.unlink()
        with self.assertRaises(EERejected) as caught:
            self.review()
        self.assertEqual(caught.exception.code,
                         "EE_STOP_EXTRACTED_PREFERENCES_UNAVAILABLE")

    def test_symlinked_preferences_directory_rejected(self):
        renamed = self.dir.with_name("Preferences-real")
        self.dir.rename(renamed)
        self.dir.symlink_to("Preferences-real", target_is_directory=True)
        with self.assertRaises(EERejected) as caught:
            self.review()
        self.assertEqual(caught.exception.code,
                         "EE_STOP_EXTRACTED_PREFERENCES_UNAVAILABLE")

    def test_symlinked_plist_file_rejected(self):
        original = self.file.with_name("real.plist")
        self.file.rename(original)
        self.file.symlink_to(original.name)
        with self.assertRaises(EERejected) as caught:
            self.review()
        self.assertEqual(caught.exception.code,
                         "EE_STOP_EXTRACTED_PREFERENCES_UNAVAILABLE")

    def test_corrupt_plist_rejected(self):
        with self.assertRaises(EERejected):
            compare_preferences(self.backup(), b"invalid")
        self.file.write_bytes(b"invalid")
        with self.assertRaises(EERejected):
            self.review()

    def test_no_write_or_install_in_source(self):
        code = (Path(__file__).resolve().parent /
                "build70_ee_portable_preferences_plist.py").read_text()
        for token in ('"installationAuthorized": False',
                      '"restorationAuthorized": False',
                      '"readyToDistributeIPA": False',
                      '"automaticUpdaterEnabled": False'):
            self.assertIn(token, code)
        for forbidden in ("appinst", ".unlink(", ".write_bytes(",
                          "subprocess.run(", "shutil.rmtree", "sqlite3.connect("):
            self.assertNotIn(forbidden, code)

if __name__ == "__main__":
    unittest.main()
