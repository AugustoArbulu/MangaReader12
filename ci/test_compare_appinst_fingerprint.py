#!/usr/bin/env python3
"""Pure offline regression tests; fake DEB/binary, no real system installer."""
import hashlib
import unittest

from audit_appinst_deb import audit_bytes
from compare_appinst_fingerprint import FingerprintRejected, compare_fingerprint
from test_audit_appinst_deb import package


class AppinstFingerprintTests(unittest.TestCase):
    def setUp(self):
        self.audit = audit_bytes(package())
        self.expected = hashlib.sha256(b"FAKE-MACHO-NO-EXECUTION").hexdigest()

    def test_matching_device_report_does_not_grant_trust(self):
        result = compare_fingerprint(self.audit, self.expected)
        self.assertTrue(result["reported_device_matches_supplied_deb_payload"])
        self.assertFalse(result["original_publisher_provenance_verified"])
        self.assertFalse(result["device_binary_independently_attested"])
        self.assertFalse(result["privileged_installer_authorized"])
        self.assertFalse(result["installer_executed"])

    def test_hash_uses_executable_bytes_not_deb_hash(self):
        self.assertNotEqual(self.audit["sha256"], self.expected)
        result = compare_fingerprint(self.audit, self.audit["sha256"])
        self.assertFalse(result["reported_device_matches_supplied_deb_payload"])

    def test_mismatch_does_not_grant_trust(self):
        result = compare_fingerprint(self.audit, "f" * 64)
        self.assertFalse(result["reported_device_matches_supplied_deb_payload"])
        self.assertFalse(result["privileged_installer_authorized"])

    def test_uppercase_hex_is_normalized(self):
        result = compare_fingerprint(self.audit, self.expected.upper())
        self.assertTrue(result["reported_device_matches_supplied_deb_payload"])
        self.assertEqual(result["reported_device_executable_sha256"], self.expected)

    def test_invalid_user_hash_rejected(self):
        for invalid in ["", "0" * 63, "0" * 65, "g" * 64, self.expected + "\n", "../usr/bin/appinst"]:
            with self.subTest(invalid=invalid), self.assertRaises(FingerprintRejected):
                compare_fingerprint(self.audit, invalid)

    def test_missing_package_fingerprint_rejected(self):
        audit = dict(self.audit)
        del audit["appinst_executable_sha256"]
        with self.assertRaises(FingerprintRejected):
            compare_fingerprint(audit, self.expected)


if __name__ == "__main__":
    unittest.main()
