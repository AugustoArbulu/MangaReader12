#!/usr/bin/env python3
"""Offline adversarial fixtures for WebReader IPA identity / ZIP checks."""
import hashlib
import io
from pathlib import Path
import plistlib
import stat
import tempfile
import unittest
import zipfile

from validate_webreader_ipa import IPARejected, validate_ipa


PREFIX = "Payload/MangaReader12.app/"

def make_ipa(directory, *,
             bundle="com.example.MangaReader12", build="56", minimum="12.0",
             extra=None, binary=True, display="WebReader"):
    content = plistlib.dumps({
        "CFBundleIdentifier": bundle,
        "CFBundleExecutable": "MangaReader12",
        "CFBundleVersion": build,
        "CFBundleDisplayName": display,
        "MinimumOSVersion": minimum,
    })
    path = Path(directory) / "test.ipa"
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(PREFIX + "Info.plist", content)
        if binary:
            z.writestr(PREFIX + "MangaReader12", b"MACHO-FAKE-ONLY")
        for name, payload in extra or []:
            z.writestr(name, payload)
    return path, hashlib.sha256(path.read_bytes()).hexdigest()

class IPAAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="webreader-ipa-fixture-")
        self.addCleanup(self.temp.cleanup)

    def test_valid_fixture_only_structurally_valid(self):
        path, digest = make_ipa(self.temp.name)
        result = validate_ipa(path, digest)
        self.assertEqual(result["build"], 56)
        self.assertFalse(result["signature_or_origin_verified"])
        self.assertFalse(result["installation_performed"])

    def test_wrong_hash(self):
        path, _ = make_ipa(self.temp.name)
        with self.assertRaises(IPARejected):
            validate_ipa(path, "0" * 64)

    def test_wrong_bundle(self):
        path, digest = make_ipa(self.temp.name, bundle="com.example.WebReader")
        with self.assertRaises(IPARejected):
            validate_ipa(path, digest)

    def test_not_newer(self):
        path, digest = make_ipa(self.temp.name, build="55")
        with self.assertRaises(IPARejected):
            validate_ipa(path, digest)

    def test_requires_ios13(self):
        path, digest = make_ipa(self.temp.name, minimum="13.0")
        with self.assertRaises(IPARejected):
            validate_ipa(path, digest)

    def test_wrong_name(self):
        path, digest = make_ipa(self.temp.name, display="Other")
        with self.assertRaises(IPARejected):
            validate_ipa(path, digest)

    def test_missing_binary(self):
        path, digest = make_ipa(self.temp.name, binary=False)
        with self.assertRaises(IPARejected):
            validate_ipa(path, digest)

    def test_traversal(self):
        path, digest = make_ipa(self.temp.name, extra=[(
            PREFIX + "../../escape", b"evil"
        )])
        with self.assertRaises(IPARejected):
            validate_ipa(path, digest)

    def test_symlink(self):
        path, digest = make_ipa(self.temp.name)
        with zipfile.ZipFile(path, "a") as z:
            meta = zipfile.ZipInfo(PREFIX + "ResourcesLink")
            meta.create_system = 3
            meta.external_attr = ((stat.S_IFLNK | 0o777) << 16)
            z.writestr(meta, "/etc/passwd")
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(IPARejected):
            validate_ipa(path, digest)

    def test_second_app_bundle(self):
        path, digest = make_ipa(self.temp.name, extra=[(
            "Payload/Other.app/Info.plist", b"spoof"
        )])
        with self.assertRaises(IPARejected):
            validate_ipa(path, digest)

    def test_not_zip(self):
        path = Path(self.temp.name) / "bad.ipa"
        path.write_bytes(b"Not an IPA")
        with self.assertRaises(IPARejected):
            validate_ipa(path, hashlib.sha256(path.read_bytes()).hexdigest())

if __name__ == "__main__":
    unittest.main()
