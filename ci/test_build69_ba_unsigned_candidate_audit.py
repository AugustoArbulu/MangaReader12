#!/usr/bin/env python3
"""Build69 BA negative fixtures: actual read-only candidate .app audit code.

Uses tiny synthetic Mach-O + Info.plist generated only in a temporary folder.
Tests are NOT proof of a native iOS12 build or Apple code signature.
"""
from pathlib import Path
import plistlib
import struct
import tempfile
import unittest

from build69_ba_unsigned_candidate_audit import (
    UnsignedCandidateRejected, inspect_unsigned_candidate,
    _macho_ios_minimum, ROOT
)


def small_macho(*, cputype=0x0100000C, platform=2, minos=12 << 16,
                filetype=2, command=0x32):
    command_data = (struct.pack("<IIIIII", 0x32, 24, platform, minos,
                                17 << 16, 0)
                    if command == 0x32 else
                    struct.pack("<IIII", 0x25, 16, minos, 17 << 16))
    header = struct.pack(
        "<IiiIIIII", 0xfeedfacf, cputype, 0, filetype, 1,
        len(command_data), 0, 0
    )
    return header + command_data


class IsolatedUnsignedPreviewAudit(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(prefix="wr69-ba-unsigned-audit-")
        self.addCleanup(self.folder.cleanup)
        self.app = Path(self.folder.name) / "MangaReader12.app"
        self.app.mkdir()
        self.info = {
            "CFBundleVersion": "69", "CFBundleIdentifier": "com.example.MangaReader12",
            "CFBundleExecutable": "MangaReader12",
            "CFBundleDisplayName": "WebReader", "CFBundleName": "WebReader",
            "MinimumOSVersion": "12.0", "CFBundlePackageType": "APPL",
            "CFBundleIcons": {"CFBundlePrimaryIcon": {"CFBundleIconName": "AppIcon"}}
        }
        self.write_plist()
        (self.app / "Assets.car").write_bytes(b"synthetic-icon-fixture")
        (self.app / "MangaReader12").write_bytes(small_macho())

    def write_plist(self):
        (self.app / "Info.plist").write_bytes(plistlib.dumps(self.info))

    def test_good_fixture_is_not_an_installation_approval(self):
        receipt = inspect_unsigned_candidate(self.app)
        self.assertEqual(receipt["status"], "ISOLATED_UNSIGNED_APP_PREVIEW_ONLY")
        self.assertEqual(receipt["sourceProjectBuild"], 56)
        self.assertEqual(receipt["observedAppBuild"], 69)
        self.assertEqual(receipt["bundleIdentifier"], "com.example.MangaReader12")
        self.assertEqual(receipt["binaryArchitecture"], "arm64")
        self.assertEqual(receipt["binaryMinimumIOS"], "12.0")
        self.assertEqual(len(receipt["binarySHA256"]), 64)
        for name in (
            "productionTrustProvisioned", "chimeraInstallationEnabled",
            "installableIPAProduced", "appAdHocCodeSignatureVerified",
            "installedApplicationIdentifierVerified", "onDeviceLibraryPreserved",
            "onDeviceOfflineChaptersPreserved", "physicalQAPassed",
            "ownerDistributionApprovalRecorded", "githubReleasePublished",
            "mainModified", "installationAuthorized", "installationPerformed"
        ):
            with self.subTest(name=name):
                self.assertFalse(receipt[name])

    def test_wrong_source_version_or_bundle_identity_rejected(self):
        for key, incorrect in (
            ("CFBundleVersion", "56"),
            ("CFBundleVersion", "068"),
            ("CFBundleIdentifier", "com.example.MangaReader12.ipcprobe"),
            ("CFBundleExecutable", "../appinst"),
            ("CFBundleDisplayName", "MangaReader12"),
            ("CFBundleName", "MangaReader12"),
            ("MinimumOSVersion", "13.0"),
            ("CFBundlePackageType", "BNDL"),
            ("CFBundleIcons", "invalid"),
        ):
            with self.subTest(key=key, incorrect=incorrect):
                old = self.info[key]
                self.info[key] = incorrect
                self.write_plist()
                with self.assertRaises(UnsignedCandidateRejected):
                    inspect_unsigned_candidate(self.app)
                self.info[key] = old
                self.write_plist()

    def test_macho_platform_cpu_deployment_and_filetype_rejected(self):
        executable = self.app / "MangaReader12"
        for body in (
            small_macho(cputype=0x01000007),
            small_macho(platform=1),
            small_macho(minos=13 << 16),
            small_macho(minos=(12 << 16) | 1),
            small_macho(filetype=6),
            b"not-mach-o",
            small_macho()[:-3],
            small_macho() + b"trailing",
            small_macho(command=0x25, minos=11 << 16),
        ):
            with self.subTest(prefix=body[:16]):
                executable.write_bytes(body)
                if body.endswith(b"trailing"):
                    self.assertEqual(_macho_ios_minimum(body), "12.0")
                else:
                    with self.assertRaises(UnsignedCandidateRejected):
                        inspect_unsigned_candidate(self.app)
        executable.write_bytes(small_macho(command=0x25))
        self.assertEqual(inspect_unsigned_candidate(self.app)["binaryMinimumIOS"], "12.0")

    def test_bad_paths_and_symlinks_rejected(self):
        original = self.app / "Info.plist"
        copied = self.app / "Info-copy.plist"
        original.rename(copied)
        original.symlink_to(copied)
        with self.assertRaises(UnsignedCandidateRejected):
            inspect_unsigned_candidate(self.app)
        original.unlink()
        copied.rename(original)
        (self.app / "Assets.car").unlink()
        with self.assertRaises(UnsignedCandidateRejected):
            inspect_unsigned_candidate(self.app)
        with self.assertRaises(UnsignedCandidateRejected):
            inspect_unsigned_candidate(Path(self.folder.name) / "Other.app")


if __name__ == "__main__":
    unittest.main()
