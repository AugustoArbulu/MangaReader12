#!/usr/bin/env python3
"""Build69 BB Linux/offline admission policy, no IPA and no macOS codesign."""
from pathlib import Path
import unittest

from build69_bb_private_qa_ipa_preflight import (
    QA_FILE_NAME, PrivateQAPreflightRejected,
    parse_independent_checksum, preflight_private_qa_ipa
)

ROOT = Path(__file__).resolve().parent.parent


class PrivateQAAdmissionContract(unittest.TestCase):
    def test_strict_checksum_parsing(self):
        checksum = ("a" * 64 + "  " + QA_FILE_NAME + "\n").encode("ascii")
        self.assertEqual(parse_independent_checksum(checksum), "a" * 64)
        for invalid in (
            b"", b"\x00", b"abc",
            b"A" * 64 + b" " + QA_FILE_NAME.encode(),
            b"a" * 64 + b" ../" + QA_FILE_NAME.encode(),
            b"a" * 64 + b" other.ipa",
            b"a" * 64 + b" " + QA_FILE_NAME.encode() + b"\nignored",
            b"a" * 64 + b" " + QA_FILE_NAME.encode() + b"\x00",
            b"a" * 64 + b" " + QA_FILE_NAME.encode() + b" " + b"z",
        ):
            with self.subTest(text=invalid[:40]):
                with self.assertRaises(PrivateQAPreflightRejected):
                    parse_independent_checksum(invalid)

    def test_preflight_does_not_accept_nonexistent_ipa_or_wrong_baseline(self):
        checksum = ("a" * 64 + "  " + QA_FILE_NAME).encode()
        imaginary = Path("/definitely-absent") / QA_FILE_NAME
        with self.assertRaises(PrivateQAPreflightRejected):
            preflight_private_qa_ipa(imaginary, checksum_data=checksum)
        with self.assertRaises(PrivateQAPreflightRejected):
            preflight_private_qa_ipa(imaginary, checksum_data=checksum, baseline=67)

    def test_preflight_contains_no_publisher_claim_or_install_action(self):
        source = (ROOT / "ci/build69_bb_private_qa_ipa_preflight.py").read_text()
        self.assertIn("require_exact_identity=True, return_snapshot=True", source)
        self.assertIn("audit_code_signature_snapshot(", source)
        self.assertIn("_macho_ios_minimum(", source)
        self.assertIn("installedApplicationIdentifierMatch", source)
        self.assertIn('"readyForDistribution": False', source)
        self.assertIn('"installationAuthorized": False', source)
        self.assertIn('"installationPerformed": False', source)
        self.assertIn('"publisherAuthenticatedByCodeSignature": False', source)
        for denied in ("posix_spawn(", "appinst(", "requests.get(",
                       "URLSession(", "upload-artifact", "codesign --sign"):
            self.assertNotIn(denied, source)


if __name__ == "__main__":
    unittest.main()
