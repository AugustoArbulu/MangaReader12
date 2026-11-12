#!/usr/bin/env python3
"""EF tests: synthetic copied offline pages; signature checks are NOT decoding."""
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import unittest
from unittest import mock
import test_build70_ed_portable_vs_external_library as fixtures
from build70_ef_offline_payload_triage import (
    EFRejected, classify_page_bytes, inspect_one_page, review_offline_payloads,
    PNG, PNG_IEND,
)

def fake_png():
    return PNG + b"\x00" * 48 + PNG_IEND

def fake_jpeg():
    return b"\xff\xd8\xff" + b"\x00" * 40 + b"\xff\xd9"

def fake_gif():
    return b"GIF89a" + b"\x00" * 20 + b"\x3b"

def fake_webp():
    # FourCC and RIFF-length are checked; the VP8 bitstream is NOT decoded.
    body = b"WEBPVP8 " + b"\x00" * 12
    return b"RIFF" + len(body).to_bytes(4, "little") + body


class EFPayloadTriageTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EDPortableLibraryTests(
            "test_exact_library_rows_equal_but_not_attested")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.root
        self.folder = (self.fixture.app / "Downloads" /
                       "asura" / "fiction1" / "chap1")
        self.first = self.folder / "page-00000.bin"
        self.second = self.folder / "page-00001.bin"
        self.first.write_bytes(fake_png())
        self.second.write_bytes(fake_jpeg())

    def assert_no_authority(self, result):
        for key in ("fullImageDecodeAttempted", "iOS12ImageDecodeVerified",
                    "sourceDeviceAttested", "originalImageBytesComparedWithIPad",
                    "allUserFilesBackedUpProven", "readyToDistributeIPA",
                    "readyToInstallIPA", "installationAuthorized",
                    "restorationAuthorized", "automaticUpdaterEnabled"):
            self.assertIs(result[key], False, key)

    def test_plausible_signatures_do_not_claim_decoding(self):
        report = review_offline_payloads(self.root)
        self.assertEqual(
            report["status"], "EF_KNOWN_IMAGE_SIGNATURES_PLAUSIBLE_NOT_DECODED")
        self.assertEqual(report["pageFileHeadersAndTrailersRead"], 2)
        self.assertEqual((report["plausiblePNG"], report["plausibleJPEG"]), (1,1))
        self.assert_no_authority(report)

    def test_png_with_missing_iend_is_rejected(self):
        self.first.write_bytes(PNG + b"\x00" * 50)
        report = review_offline_payloads(self.root)
        self.assertEqual(report["status"], "EF_STOP_HTML_OR_TRUNCATED_OFFLINE_FILES")
        self.assertEqual(report["truncatedOrBrokenSignatures"], 1)
        self.assert_no_authority(report)

    def test_jpeg_missing_eoi_is_rejected(self):
        self.second.write_bytes(b"\xff\xd8\xff" + b"\x01" * 64)
        report = review_offline_payloads(self.root)
        self.assertEqual(report["truncatedOrBrokenSignatures"], 1)
        self.assert_no_authority(report)

    def test_fake_html_200_is_detected(self):
        self.first.write_bytes(b"<!DOCTYPE html><html>access denied</html>")
        report = review_offline_payloads(self.root)
        self.assertEqual(report["htmlJsonOrTextResponses"], 1)
        self.assertEqual(report["status"], "EF_STOP_HTML_OR_TRUNCATED_OFFLINE_FILES")

    def test_json_200_is_detected(self):
        self.first.write_bytes(b'{"error":"forbidden"}')
        self.assertEqual(review_offline_payloads(self.root)["htmlJsonOrTextResponses"], 1)

    def test_gif_trailer_is_checked(self):
        self.first.write_bytes(fake_gif())
        report = review_offline_payloads(self.root)
        self.assertEqual(report["plausibleGIF"], 1)
        self.first.write_bytes(fake_gif()[:-1])
        self.assertEqual(review_offline_payloads(self.root)["truncatedOrBrokenSignatures"], 1)

    def test_webp_riff_size_is_checked_without_decode(self):
        self.first.write_bytes(fake_webp())
        report = review_offline_payloads(self.root)
        self.assertEqual(report["plausibleWebP"], 1)
        self.assert_no_authority(report)
        broken = bytearray(fake_webp())
        broken[4] ^= 1
        self.first.write_bytes(broken)
        self.assertEqual(review_offline_payloads(self.root)["truncatedOrBrokenSignatures"], 1)

    def test_webp_unsupported_fourcc_rejected(self):
        broken = bytearray(fake_webp())
        broken[12:16] = b"FAIL"
        self.first.write_bytes(broken)
        self.assertEqual(review_offline_payloads(self.root)["truncatedOrBrokenSignatures"], 1)

    def test_unknown_format_requires_real_device_reading(self):
        self.first.write_bytes(b"HEIF?\x00\x01x" * 6)
        report = review_offline_payloads(self.root)
        self.assertEqual(report["status"], "EF_UNKNOWN_FORMATS_REQUIRE_REAL_IOS12_READ")
        self.assertEqual(report["unknownFormats"], 1)
        self.assert_no_authority(report)

    def test_empty_file_remains_invalid_in_ea(self):
        self.first.write_bytes(b"")
        with self.assertRaises(EFRejected) as raised:
            review_offline_payloads(self.root)
        self.assertEqual(raised.exception.code, "EF_STOP_EXTERNAL_COPY_INVALID")

    def test_page_symlink_remains_invalid_in_ea(self):
        self.first.unlink()
        self.first.symlink_to(self.second)
        with self.assertRaises(EFRejected) as raised:
            review_offline_payloads(self.root)
        self.assertEqual(raised.exception.code, "EF_STOP_EXTERNAL_COPY_INVALID")

    def test_nonempty_wal_blocks_without_checkpoint(self):
        path = self.fixture.app / "library.sqlite-wal"
        path.write_bytes(b"pending journal data")
        with self.assertRaises(EFRejected) as raised:
            review_offline_payloads(self.root)
        self.assertEqual(raised.exception.code, "EF_STOP_EXTERNAL_COPY_INVALID")
        self.assertEqual(path.read_bytes(), b"pending journal data")

    def test_host_file_swap_between_stat_and_open_is_rejected(self):
        actual_open = os.open
        exchanged = [False]
        saved = self.folder / "page-saved.bin"
        def swapping(path, flags, *a, **kw):
            if str(path) == str(self.first) and not exchanged[0]:
                exchanged[0] = True
                self.first.rename(saved)
                self.first.write_bytes(fake_png())
            return actual_open(path, flags, *a, **kw)
        with mock.patch("build70_ef_offline_payload_triage.os.open",
                        side_effect=swapping):
            with self.assertRaises(EFRejected) as raised:
                inspect_one_page(self.first)
        self.assertTrue(exchanged[0])
        self.assertEqual(raised.exception.code, "EF_STOP_FILE_CHANGED")

    def test_modified_page_bytes_do_not_change_format_class(self):
        valid = fake_png()
        self.first.write_bytes(valid)
        first = review_offline_payloads(self.root)
        self.first.write_bytes(PNG + b"B" * 48 + PNG_IEND)
        second = review_offline_payloads(self.root)
        self.assertEqual(first["status"], second["status"])
        self.assert_no_authority(second)

    def test_trailer_markers_do_not_prove_real_images(self):
        self.assertEqual(classify_page_bytes(
            fake_png()[:96], fake_png()[-96:], len(fake_png())),
            "pngPlausible")
        self.assertEqual(classify_page_bytes(
            fake_jpeg()[:96], fake_jpeg()[-96:], len(fake_jpeg())),
            "jpegPlausible")

    def test_cli_does_not_expose_private_data_on_error(self):
        self.first.write_bytes(b"<!DOCTYPE html><html>blocked</html>")
        script = Path(__file__).resolve().parent / "build70_ef_offline_payload_triage.py"
        result = subprocess.run(
            [sys.executable, str(script), "--snapshot", str(self.root)],
            check=False, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(json.loads(result.stdout)["status"], "EF_STOP_HTML_OR_TRUNCATED_OFFLINE_FILES")
        self.assertNotIn(str(self.root), result.stdout)
        self.assertNotIn("fiction1", result.stdout)
        self.assertFalse(json.loads(result.stdout)["installationAuthorized"])

    def test_static_no_write_or_install_and_source_contract(self):
        code = (Path(__file__).resolve().parent /
                "build70_ef_offline_payload_triage.py").read_text()
        swift = (Path(__file__).resolve().parent.parent / "MangaReader12" /
                 "Downloads" / "ChapterDownloadManager.swift").read_text()
        for token in ("b'\\x00\\x00", "page-", "canStore("):
            if token == "canStore(":
                self.assertIn(token, swift)
        for forbidden in ("appinst", ".unlink(", "subprocess.run(",
                          ".write_bytes(", ".write_text(", "shutil.rmtree"):
            self.assertNotIn(forbidden, code)
        for token in ('"installationAuthorized": False',
                      '"restorationAuthorized": False',
                      '"fullImageDecodeAttempted": False'):
            self.assertIn(token, code)

if __name__ == "__main__":
    unittest.main()
