#!/usr/bin/env python3
"""Offline hostile-input tests for draft helper IPC semantics. No helper run."""
import json
import unittest

from webreader_helper_request_contract import (
    BUNDLE_ID, MAX_REQUEST_BYTES, HelperRequestRejected,
    parse_review_request, redact_request_for_log
)


def valid_envelope():
    return {
        "schemaVersion": 1,
        "operation": "request-install-review",
        "bundleId": BUNDLE_ID,
        "build": 57,
        "manifestSHA256": "a" * 64,
        "nonce": "b" * 64,
    }


def encode(obj):
    return json.dumps(obj, ensure_ascii=True, separators=(",", ":")).encode()


class HelperRequestContractTests(unittest.TestCase):
    def test_valid_review_request_is_data_not_install_permission(self):
        request = parse_review_request(encode(valid_envelope()))
        self.assertEqual(request.build, 57)
        public_log = redact_request_for_log(request)
        self.assertEqual(public_log["authorization_status"],
                         "never-authorized-by-request-parser")
        self.assertNotIn("nonce", public_log)
        self.assertNotIn("manifestSHA256", public_log)
        self.assertNotIn("installPath", public_log)

    def test_unknown_fields_rejected_including_commands_and_paths(self):
        for key, value in [
            ("path", "/var/mobile/ipa"), ("argv", ["appinst"]),
            ("command", "appinst"), ("url", "https://host/payload.ipa"),
            ("root", True), ("install", True), ("shell", "/bin/sh"),
            ("environment", {"PATH": "/usr/bin"}),
        ]:
            with self.subTest(key=key):
                data = valid_envelope()
                data[key] = value
                with self.assertRaises(HelperRequestRejected):
                    parse_review_request(encode(data))

    def test_missing_fields_rejected(self):
        for field in valid_envelope():
            with self.subTest(field=field):
                data = valid_envelope()
                del data[field]
                with self.assertRaises(HelperRequestRejected):
                    parse_review_request(encode(data))

    def test_wrong_identity_operation_version_and_build_rejected(self):
        for field, bad in [
            ("schemaVersion", True), ("schemaVersion", 2),
            ("operation", "install"), ("operation", "run-command"),
            ("bundleId", "com.example.MangaReader12.httpsprobe"),
            ("build", True), ("build", 0), ("build", -1),
            ("build", 2147483648), ("build", 57.5), ("build", "57"),
        ]:
            with self.subTest(field=field, bad=bad):
                data = valid_envelope()
                data[field] = bad
                with self.assertRaises(HelperRequestRejected):
                    parse_review_request(encode(data))

    def test_digest_and_nonce_must_be_canonical_lowercase(self):
        for field in ["manifestSHA256", "nonce"]:
            for invalid in ["f" * 63, "f" * 65, "G" * 64, "A" * 64,
                            "../ipa", 0, None, ["a" * 64]]:
                with self.subTest(field=field, invalid=invalid):
                    data = valid_envelope()
                    data[field] = invalid
                    with self.assertRaises(HelperRequestRejected):
                        parse_review_request(encode(data))

    def test_digest_cannot_be_used_as_nonce(self):
        data = valid_envelope()
        data["nonce"] = data["manifestSHA256"]
        with self.assertRaises(HelperRequestRejected):
            parse_review_request(encode(data))

    def test_duplicate_json_keys_rejected_even_if_unicode_escaped(self):
        good = encode(valid_envelope()).decode()
        for extra in [',"build":58', ',"b\\u0075ild":58']:
            with self.subTest(extra=extra), self.assertRaises(HelperRequestRejected):
                parse_review_request((good[:-1] + extra + "}").encode())

    def test_root_type_and_nonfinite_numeric_rejected(self):
        for raw in [b"[]", b"1", b"null", b"NaN", b"Infinity",
                    b"{}", b"{", b"\xff", b"\xef\xbb\xbf{}"]:
            with self.subTest(raw=raw), self.assertRaises(HelperRequestRejected):
                parse_review_request(raw)

    def test_size_bounds_and_no_implicit_string_decoding(self):
        for value in [b"", b" " * (MAX_REQUEST_BYTES + 1),
                      encode(valid_envelope()).decode()]:
            with self.subTest(value_type=type(value)):
                with self.assertRaises(HelperRequestRejected):
                    parse_review_request(value)

    def test_valid_tokens_do_not_grant_actual_permission(self):
        data = valid_envelope()
        data["build"] = 2147483647
        parsed = parse_review_request(encode(data))
        self.assertEqual(parsed.build, 2147483647)
        self.assertNotIn("approved", redact_request_for_log(parsed))
        self.assertEqual(
            redact_request_for_log(parsed)["authorization_status"],
            "never-authorized-by-request-parser"
        )


if __name__ == "__main__":
    unittest.main()
