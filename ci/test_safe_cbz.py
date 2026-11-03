#!/usr/bin/env python3
"""Compile the actual Swift CBZ parser, then test good and adversarial ZIPs.

No network, no app files, no third-party Python packages. macOS Xcode runner.
"""
import binascii
import os
import pathlib
import stat
import struct
import subprocess
import tempfile
import unittest
import zipfile
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
BIN = None


def png(width=1, height=1):
    def chunk(name, data):
        crc = binascii.crc32(name + data) & 0xffffffff
        return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)
    body = b"\x00" + bytes([0xff, 0x20, 0x20]) * width
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(body * height, 9))
        + chunk(b"IEND", b"")
    )


class ArchiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.binary = pathlib.Path(cls.tmp.name) / "safe-cbz-test"
        subprocess.run(
            ["swiftc", "-O", str(ROOT / "MangaReader12/Core/SafeCBZArchive.swift"),
             str(ROOT / "ci/validate_cbz.swift"), "-o", str(cls.binary)],
            check=True, capture_output=True, text=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def run_import(self, content, should_pass=False, expected_count=None):
        with tempfile.TemporaryDirectory() as folder:
            archive = pathlib.Path(folder) / "candidate.cbz"
            archive.write_bytes(content)
            output = pathlib.Path(folder) / "pages"
            proc = subprocess.run(
                [str(self.binary), str(archive), str(output)],
                text=True, capture_output=True, timeout=35,
            )
            if should_pass:
                self.assertEqual(proc.returncode, 0, proc.stderr)
                if expected_count is not None:
                    self.assertIn(f"OK:{expected_count}", proc.stdout)
                    self.assertEqual(
                        len(list(output.glob("page-*"))), expected_count
                    )
            else:
                self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertFalse((pathlib.Path(folder) / "escape.png").exists())
            return proc

    def archive(self, entries, mode=zipfile.ZIP_DEFLATED, comment=b""):
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", compression=mode) as archive:
            for name, data in entries:
                archive.writestr(name, data)
            archive.comment = comment
        return buf.getvalue()

    def test_stored_png_sorted_numerically(self):
        content = self.archive(
            [("chapter/10.png", png()), ("chapter/2.png", png())],
            zipfile.ZIP_STORED
        )
        proc = self.run_import(content, True, 2)
        self.assertIn("page-00001.png", proc.stdout)
        self.assertIn("page-00002.png", proc.stdout)

    def test_deflate_png_and_zip_comment(self):
        content = self.archive(
            [("001.png", png()), ("002.png", png())],
            zipfile.ZIP_DEFLATED, b"comic comment"
        )
        self.run_import(content, True, 2)

    def test_path_traversal_rejected(self):
        self.run_import(self.archive([("../escape.png", png())]))

    def test_windows_path_separator_rejected(self):
        self.run_import(self.archive([("bad\\path.png", png())]))

    def test_absolute_paths_rejected(self):
        self.run_import(self.archive([("/tmp/escape.png", png())]))

    def test_duplicate_members_rejected(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            content = self.archive([("001.png", png()), ("001.png", png())])
        self.run_import(content)

    def test_symlink_rejected(self):
        import io
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            symlink = zipfile.ZipInfo("link.png")
            symlink.create_system = 3
            symlink.external_attr = (stat.S_IFLNK | 0o777) << 16
            archive.writestr(symlink, b"target.png")
        self.run_import(buf.getvalue())

    def test_no_compatible_images_rejected(self):
        self.run_import(self.archive([("readme.txt", b"No images here")]))

    def test_bad_crc_rejected(self):
        data = bytearray(self.archive([("1.png", png())], zipfile.ZIP_STORED))
        signature = data.find(b"PK\x03\x04")
        self.assertGreaterEqual(signature, 0)
        name_length = struct.unpack_from("<H", data, signature + 26)[0]
        extra_length = struct.unpack_from("<H", data, signature + 28)[0]
        start = signature + 30 + name_length + extra_length
        data[start + 8] ^= 1
        self.run_import(data)

    def test_password_encryption_flag_rejected(self):
        data = bytearray(self.archive([("1.png", png())], zipfile.ZIP_STORED))
        local = data.find(b"PK\x03\x04")
        central = data.find(b"PK\x01\x02")
        self.assertGreaterEqual(central, 0)
        struct.pack_into("<H", data, local + 6, 1)
        struct.pack_into("<H", data, central + 8, 1)
        self.run_import(data)

    def test_truncated_zip_rejected(self):
        self.run_import(self.archive([("1.png", png())])[:-12])

    def test_unsupported_file_and_valid_png(self):
        self.run_import(
            self.archive([("notes/README.txt", b"okay"), ("one.png", png())]),
            True, 1
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
