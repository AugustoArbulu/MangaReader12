#!/usr/bin/env python3
"""Synthetic-only Build66 archive admission regression tests."""
import hashlib
import io
import plistlib
import tempfile
import unittest
import zipfile
from pathlib import Path
from build66_ipa_preflight import inspect_ipa, AdmissionDenied


def make_ipa(entries=None, bundle="com.example.MangaReader12", build="66", minimum="12.0"):
    info = plistlib.dumps({"CFBundleIdentifier": bundle, "CFBundleVersion": build,
                            "MinimumOSVersion": minimum})
    contents = entries if entries is not None else [
        ("Payload/WebReader.app/Info.plist", info),
        ("Payload/WebReader.app/WebReader", b"synthetic-not-executable")]
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in contents:
            z.writestr(name, data)
    return stream.getvalue()


class TestBuild66Preflight(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "fixture.ipa"

    def check(self, data, sha=None, size=None, baseline=65):
        self.path.write_bytes(data)
        return inspect_ipa(self.path, sha or hashlib.sha256(data).hexdigest(),
                           len(data) if size is None else size, baseline)

    def test_valid_fixture(self):
        self.assertEqual(self.check(make_ipa())["build"], 66)

    def test_digest_mismatch(self):
        with self.assertRaises(AdmissionDenied):
            self.check(make_ipa(), sha="0" * 64)

    def test_size_mismatch(self):
        data = make_ipa()
        with self.assertRaises(AdmissionDenied):
            self.check(data, size=len(data) + 1)

    def test_wrong_bundle(self):
        with self.assertRaises(AdmissionDenied):
            self.check(make_ipa(bundle="com.attacker.app"))

    def test_downgrade(self):
        with self.assertRaises(AdmissionDenied):
            self.check(make_ipa(build="65"))

    def test_ios_incompatible(self):
        with self.assertRaises(AdmissionDenied):
            self.check(make_ipa(minimum="13.0"))

    def test_path_traversal(self):
        with self.assertRaises(AdmissionDenied):
            self.check(make_ipa(entries=[("../escape", b"x"),
                                         ("Payload/WebReader.app/Info.plist", b"x")]))

    def test_duplicate_entries(self):
        data = make_ipa(entries=[
            ("Payload/WebReader.app/Info.plist", b"a"),
            ("Payload/WebReader.app/Info.plist", b"b")])
        with self.assertRaises(AdmissionDenied):
            self.check(data)

    def test_symlink(self):
        data = make_ipa()
        target = Path(self.temp.name) / "actual.ipa"
        target.write_bytes(data)
        self.path.symlink_to(target)
        with self.assertRaises(AdmissionDenied):
            inspect_ipa(self.path, hashlib.sha256(data).hexdigest(), len(data), 65)

    def test_not_zip(self):
        with self.assertRaises(AdmissionDenied):
            self.check(b"not a ZIP")

    def test_invalid_baseline(self):
        with self.assertRaises(AdmissionDenied):
            self.check(make_ipa(), baseline=-1)


if __name__ == "__main__":
    unittest.main()
