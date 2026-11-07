#!/usr/bin/env python3
"""Synthetic, offline regression tests for portable IPC field kit verification."""
import hashlib
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest
import zipfile

from verify_ipc_field_kit import (
    HELPER_NAME, IPA_NAME, KitRejected, verify_kit
)


def identity():
    return {
        "CFBundleIdentifier": "com.example.MangaReader12.ipcprobe",
        "CFBundleExecutable": "MangaReader12",
        "CFBundleVersion": "56",
        "CFBundleDisplayName": "WebReader IPC Test",
        "MinimumOSVersion": "12.0",
    }


class FieldKitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write_ipa()
        self.write_helper()

    def write_ipa(self, *, metadata=None, duplicate=False):
        path = self.root / IPA_NAME
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as out:
            data = plistlib.dumps(identity() if metadata is None else metadata)
            out.writestr("Payload/MangaReader12.app/Info.plist", data)
            if duplicate:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    out.writestr("Payload/MangaReader12.app/Info.plist", data)
            out.writestr("Payload/MangaReader12.app/MangaReader12", b"app stub")
        self.hash_for(IPA_NAME)

    def write_helper(self, *, cpu=0x0100000C, magic=0xFEEDFACF):
        header = struct.pack("<IIIIIIII", magic, cpu, 0, 2, 0, 0, 0, 0)
        (self.root / HELPER_NAME).write_bytes(header + b"synthetic only")
        self.hash_for(HELPER_NAME)

    def hash_for(self, name):
        value = hashlib.sha256((self.root / name).read_bytes()).hexdigest()
        (self.root / (name + ".sha256")).write_text(value + "  " + name + "\n")

    def test_valid_synthetic_layout_only_not_installable(self):
        result = verify_kit(self.root)
        self.assertEqual(result["status"], "PASS")
        self.assertFalse(result["installation_authorized"])
        self.assertFalse(result["signature_provenance_verified"])
        self.assertFalse(result["device_compatibility_proven"])
        self.assertEqual(result["helper_architecture"], "arm64")

    def test_ipa_corrupted_after_checksum_generation_rejected(self):
        with (self.root / IPA_NAME).open("ab") as f:
            f.write(b"unexpected data")
        with self.assertRaises(KitRejected):
            verify_kit(self.root)

    def test_helper_corrupted_after_checksum_generation_rejected(self):
        with (self.root / HELPER_NAME).open("ab") as f:
            f.write(b"unexpected data")
        with self.assertRaises(KitRejected):
            verify_kit(self.root)

    def test_wrong_bundle_and_background_fetch_rejected(self):
        for broken in [
            {"CFBundleIdentifier": "com.example.MangaReader12"},
            {"UIBackgroundModes": ["fetch"]},
            {"MinimumOSVersion": "13.0"},
            {"CFBundleDisplayName": "WebReader"},
            {"CFBundleVersion": "57"},
        ]:
            with self.subTest(broken=broken):
                info = identity()
                info.update(broken)
                self.write_ipa(metadata=info)
                with self.assertRaises(KitRejected):
                    verify_kit(self.root)

    def test_duplicate_archive_entry_rejected(self):
        self.write_ipa(duplicate=True)
        with self.assertRaises(KitRejected):
            verify_kit(self.root)

    def test_wrong_binary_architecture_rejected_even_when_hash_matches(self):
        for cpu, magic in [(7, 0xFEEDFACF), (0x0100000C, 0xCAFEBABE)]:
            with self.subTest(cpu=cpu, magic=magic):
                self.write_helper(cpu=cpu, magic=magic)
                with self.assertRaises(KitRejected):
                    verify_kit(self.root)

    def test_symlink_helper_rejected(self):
        original = self.root / HELPER_NAME
        different = self.root / "other-helper"
        original.replace(different)
        original.symlink_to(different)
        with self.assertRaises(KitRejected):
            verify_kit(self.root)

    def test_checksum_file_wrong_name_or_invalid_format_rejected(self):
        sha = self.root / (IPA_NAME + ".sha256")
        original = sha.read_text()
        for value in [
            original.replace(IPA_NAME, "other.ipa"),
            original.strip(),
            "BAD" + original,
            original + original,
        ]:
            with self.subTest(value=value[:20]):
                sha.write_text(value)
                with self.assertRaises(KitRejected):
                    verify_kit(self.root)

    def test_missing_ipa_or_helper_rejected(self):
        (self.root / HELPER_NAME).unlink()
        with self.assertRaises(KitRejected):
            verify_kit(self.root)

    def test_non_absolute_root_rejected(self):
        with self.assertRaises(KitRejected):
            verify_kit(Path("relative-kit-dir"))


if __name__ == "__main__":
    unittest.main()
