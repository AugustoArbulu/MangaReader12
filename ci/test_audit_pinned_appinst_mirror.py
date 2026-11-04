#!/usr/bin/env python3
"""No-network tests of publisher-index matching and bounded decoding."""
import bz2
import gzip
import unittest

from audit_pinned_appinst_mirror import (
    VerificationError, matching_official_entry, package_stanzas, unpack_index
)
TEXT = """Package: other.app
Version: 9
Architecture: iphoneos-arm
SHA256: unused

Package: ai.akemi.appinst
Version: 2.1.1
Architecture: iphoneos-arm
Filename: debs/appinst-2.1.1.deb
Size: 59716
SHA256: 5997771183c39eb8b5e13fc2bb511b1dfcb7eb39d3f10c9092ab088ec34aae09

Package: ai.akemi.appinst
Version: 2.1.1
Architecture: iphoneos-arm64
SHA256: another
"""

class IndexPolicyTests(unittest.TestCase):
    def test_plain_index(self):
        entry = matching_official_entry(TEXT)
        self.assertEqual(entry["sha256"],
            "5997771183c39eb8b5e13fc2bb511b1dfcb7eb39d3f10c9092ab088ec34aae09")
        self.assertEqual(entry["size"], "59716")

    def test_gzip_index(self):
        self.assertEqual(unpack_index(gzip.compress(TEXT.encode()), "Packages.gz"), TEXT)

    def test_bzip2_index(self):
        self.assertEqual(unpack_index(bz2.compress(TEXT.encode()), "Packages.bz2"), TEXT)

    def test_invalid_index_rejected(self):
        with self.assertRaises(VerificationError):
            unpack_index(b"broken", "Packages.gz")

    def test_no_wrong_architecture_attribution(self):
        self.assertIsNone(matching_official_entry(
            "Package: ai.akemi.appinst\nVersion: 2.1.1\n"
            "Architecture: iphoneos-arm64\nSHA256: untrusted\n"
        ))

    def test_no_wrong_version_attribution(self):
        self.assertIsNone(matching_official_entry(
            "Package: ai.akemi.appinst\nVersion: 2.1.0\n"
            "Architecture: iphoneos-arm\nSHA256: untrusted\n"
        ))

if __name__ == "__main__":
    unittest.main()
