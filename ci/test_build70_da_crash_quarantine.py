#!/usr/bin/env python3
"""DA: hostile host-only durable quarantine tests. NEVER install/download.

Synthetic marker means a possibly unfinished read-only check. Every restart
with that marker is quarantined, including clean host process closure. The
tests intentionally demonstrate same-UID deletion defeats the protection.
"""
from concurrent.futures import ThreadPoolExecutor
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
FRAME = b"WRCHK2\n"
DENIED, READY, MARKED, QUARANTINED, BUSY = 0, 1, 2, 3, 4
MARKER = "wr-da-check.pending"
LOCK = "wr-da-review.lock"


class Receipt(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("crash_evidence_is_present", ctypes.c_bool),
        ("caller_authenticated", ctypes.c_bool),
        ("publisher_verified", ctypes.c_bool),
        ("editor_pin_provisioned", ctypes.c_bool),
        ("ipad_uid_isolation_proven", ctypes.c_bool),
        ("protected_against_same_uid_tamper", ctypes.c_bool),
        ("can_reconcile_pending_install", ctypes.c_bool),
        ("installation_authorized", ctypes.c_bool),
        ("installation_performed", ctypes.c_bool),
    ]


class DACrashQuarantineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="wr-da-compile-only-")
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            raise RuntimeError("C compiler required")
        cls.library_path = Path(cls.folder.name) / (
            "libda.dylib" if sys.platform == "darwin" else "libda.so"
        )
        subprocess.run([
            cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-pthread", "-fPIC", "-shared",
            str(ROOT / "build70_da_crash_quarantine.c"),
            "-o", str(cls.library_path),
        ], check=True, capture_output=True, text=True, timeout=30)
        cls.lib = ctypes.CDLL(str(cls.library_path))
        cls.lib.wr_da_open.argtypes = (ctypes.c_char_p, ctypes.POINTER(Receipt))
        cls.lib.wr_da_open.restype = ctypes.c_void_p
        cls.lib.wr_da_offer.argtypes = (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t)
        cls.lib.wr_da_offer.restype = Receipt
        cls.lib.wr_da_observe.argtypes = (ctypes.c_void_p,)
        cls.lib.wr_da_observe.restype = Receipt
        cls.lib.wr_da_close.argtypes = (ctypes.c_void_p,)
        cls.lib.wr_da_close.restype = None

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def setUp(self):
        self.folder_test = tempfile.TemporaryDirectory(prefix="wr-da-host-")
        self.addCleanup(self.folder_test.cleanup)
        self.directory = Path(self.folder_test.name) / "private"
        self.directory.mkdir(mode=0o700)
        self.directory.chmod(0o700)
        self.path = str(self.directory).encode("utf-8")
        self._handles = []
        self.addCleanup(self._close_all)

    def _close_all(self):
        for handle in reversed(self._handles):
            if handle:
                self.lib.wr_da_close(handle)
        self._handles.clear()

    def open(self, path=None):
        result = Receipt()
        value = self.lib.wr_da_open(self.path if path is None else path,
                                    ctypes.byref(result))
        if value:
            self._handles.append(value)
        self.safe(result)
        return value, result

    def safe(self, result, status=None):
        if status is not None:
            self.assertEqual(result.status, status)
        for field in (
            "caller_authenticated", "publisher_verified", "editor_pin_provisioned",
            "ipad_uid_isolation_proven", "protected_against_same_uid_tamper",
            "can_reconcile_pending_install", "installation_authorized",
            "installation_performed",
        ):
            self.assertFalse(getattr(result, field), field)
        return result

    def offer(self, handle, payload=FRAME):
        if payload is None:
            return self.safe(self.lib.wr_da_offer(handle, None, 0))
        data = ctypes.create_string_buffer(payload)
        return self.safe(self.lib.wr_da_offer(handle, data, len(payload)))

    def close(self, handle):
        self._handles.remove(handle)
        self.lib.wr_da_close(handle)

    def test_ready_first_notice_is_written_before_return(self):
        h, result = self.open()
        self.safe(result, READY)
        self.assertFalse(result.crash_evidence_is_present)
        marked = self.safe(self.offer(h), MARKED)
        self.assertTrue(marked.crash_evidence_is_present)
        marker = self.directory / MARKER
        self.assertEqual(marker.read_bytes(), b"PENDING-READ-ONLY-CHECK\n")
        self.assertEqual(marker.stat().st_mode & 0o777, 0o600)
        self.safe(self.lib.wr_da_observe(h), QUARANTINED)

    def test_exact_one_shot_in_same_process(self):
        h, _ = self.open()
        self.safe(self.offer(h), MARKED)
        for _ in range(10):
            self.safe(self.offer(h), QUARANTINED)
        self.assertEqual(len(list(self.directory.iterdir())), 2)

    def test_restart_after_clean_close_is_also_quarantined(self):
        h, _ = self.open()
        self.safe(self.offer(h), MARKED)
        self.close(h)
        second, report = self.open()
        self.safe(report, QUARANTINED)
        self.assertTrue(report.crash_evidence_is_present)
        self.safe(self.offer(second), QUARANTINED)

    def test_child_process_crash_retains_pending_marker(self):
        snippet = r'''
import ctypes, os, sys
class R(ctypes.Structure):
    _fields_ = [("status",ctypes.c_int)] + [
        (name,ctypes.c_bool) for name in (
            "crash_evidence_is_present","caller_authenticated","publisher_verified",
            "editor_pin_provisioned","ipad_uid_isolation_proven",
            "protected_against_same_uid_tamper","can_reconcile_pending_install",
            "installation_authorized","installation_performed")]
lib = ctypes.CDLL(sys.argv[1])
lib.wr_da_open.argtypes = (ctypes.c_char_p,ctypes.POINTER(R))
lib.wr_da_open.restype = ctypes.c_void_p
lib.wr_da_offer.argtypes = (ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t)
lib.wr_da_offer.restype = R
o = R()
h = lib.wr_da_open(os.fsencode(sys.argv[2]),ctypes.byref(o))
assert h and o.status == 1
packet = ctypes.create_string_buffer(b"WRCHK2\n")
r = lib.wr_da_offer(h,packet,7)
assert r.status == 2
os._exit(0)  # deliberately bypass normal teardown, no user files involved
'''
        child = subprocess.run([sys.executable, "-c", snippet,
                                str(self.library_path), str(self.directory)],
                               check=False, capture_output=True, timeout=15)
        self.assertEqual(child.returncode, 0, child.stderr.decode(errors="replace"))
        self.assertTrue((self.directory / MARKER).exists())
        h, r = self.open()
        self.safe(r, QUARANTINED)
        self.safe(self.offer(h), QUARANTINED)

    def test_second_process_handle_denied_by_lock(self):
        h, r = self.open()
        self.safe(r, READY)
        second, busy = self.open()
        self.assertFalse(second)
        self.safe(busy, BUSY)
        self.close(h)
        h2, ready = self.open()
        self.assertTrue(h2)
        self.safe(ready, READY)

    def test_128_threads_cannot_create_parallel_markers(self):
        h, r = self.open()
        self.safe(r, READY)
        with ThreadPoolExecutor(max_workers=24) as pool:
            observations = list(pool.map(lambda _: self.offer(h), range(128)))
        self.assertEqual(sum(x.status == MARKED for x in observations), 1)
        self.assertEqual(sum(x.status == QUARANTINED for x in observations), 127)
        self.assertEqual(len(list(self.directory.glob("*.pending"))), 1)

    def test_malformed_frames_do_not_consume_journal(self):
        h, _ = self.open()
        payloads = (
            b"", b"WRCHK2", b"WRCHK2\r\n", b"WRINST1\n",
            b"WRCHK2\nhttps://evil.invalid", b"WRCHK2\nowner_consents",
            b"WRCHK2\nI-CONFIRM-INSTALL", b"WRCHK2\x00", FRAME + b"A" * 100000,
            None,
        )
        for packet in payloads:
            with self.subTest(payload=repr(packet)[:24]):
                self.safe(self.offer(h, packet), DENIED)
        self.assertFalse((self.directory / MARKER).exists())
        self.safe(self.offer(h), MARKED)

    def test_invalid_directory_permissions_denied(self):
        self.directory.chmod(0o777)
        h, r = self.open()
        self.assertFalse(h)
        self.safe(r, DENIED)

    def test_readable_directory_denied(self):
        self.directory.chmod(0o755)
        h, r = self.open()
        self.assertFalse(h)
        self.safe(r, DENIED)

    def test_symlinked_directory_leaf_rejected(self):
        alias = Path(self.folder_test.name) / "alias"
        alias.symlink_to(self.directory, target_is_directory=True)
        h, r = self.open(str(alias).encode())
        self.assertFalse(h)
        self.safe(r, DENIED)

    def test_relative_dotdot_and_trailing_slash_denied(self):
        for bad in (
            b"relative", b"/", b"/tmp/../tmp/something",
            (str(self.directory) + "/").encode(),
            (str(self.directory) + "/./foo").encode()
        ):
            with self.subTest(bad=bad):
                h, result = self.open(bad)
                self.assertFalse(h)
                self.safe(result, DENIED)

    def test_symlink_lock_denied(self):
        outside = Path(self.folder_test.name) / "outside"
        outside.write_bytes(b"")
        (self.directory / LOCK).symlink_to(outside)
        h, r = self.open()
        self.assertFalse(h)
        self.safe(r, DENIED)
        self.assertEqual(outside.read_bytes(), b"")

    def test_hardlink_lock_denied(self):
        other = self.directory / "other"
        other.write_bytes(b"")
        (self.directory / LOCK).hardlink_to(other)
        h, r = self.open()
        self.assertFalse(h)
        self.safe(r, DENIED)

    def test_group_writable_lock_denied(self):
        lock = self.directory / LOCK
        lock.write_bytes(b"")
        lock.chmod(0o660)
        h, r = self.open()
        self.assertFalse(h)
        self.safe(r, DENIED)

    def test_unexpected_existing_lock_content_denied(self):
        (self.directory / LOCK).write_bytes(b"FORGED")
        h, r = self.open()
        self.assertFalse(h)
        self.safe(r, DENIED)

    def test_symlink_pending_marker_means_quarantine(self):
        target = Path(self.folder_test.name) / "unrelated"
        target.write_bytes(b"SECRET-UNAFFECTED")
        (self.directory / MARKER).symlink_to(target)
        h, r = self.open()
        self.assertTrue(h)
        self.safe(r, QUARANTINED)
        self.safe(self.offer(h), QUARANTINED)
        self.assertEqual(target.read_bytes(), b"SECRET-UNAFFECTED")

    def test_partial_or_empty_marker_means_quarantine(self):
        for content in (b"", b"PE", b"CORRUPTED"):
            with self.subTest(content=content):
                path = self.directory / MARKER
                path.write_bytes(content)
                h, r = self.open()
                self.safe(r, QUARANTINED)
                self.safe(self.offer(h), QUARANTINED)
                self.close(h)
                path.unlink()

    def test_marker_directory_also_means_quarantine(self):
        (self.directory / MARKER).mkdir()
        h, r = self.open()
        self.safe(r, QUARANTINED)
        self.safe(self.offer(h), QUARANTINED)

    def test_null_handles_reject(self):
        self.safe(self.lib.wr_da_observe(None), DENIED)
        self.safe(self.lib.wr_da_offer(None, None, 0), DENIED)

    def test_same_uid_can_delete_marker_this_is_not_tamper_proof(self):
        h, _ = self.open()
        self.safe(self.offer(h), MARKED)
        self.close(h)
        (self.directory / MARKER).unlink()
        # Same-owner tampering or root can erase "durable" evidence. The
        # current laboratory IS NOT a trustworthy helper security boundary.
        again, result = self.open()
        self.safe(result, READY)
        self.assertTrue(again)
        self.assertFalse(result.protected_against_same_uid_tamper)

    def test_api_has_no_install_clear_or_authorization_method(self):
        source = (ROOT / "build70_da_crash_quarantine.c").read_text()
        header = (ROOT / "build70_da_crash_quarantine.h").read_text()
        for forbidden in (
            "posix_spawn(", "objc_msgSend(", "installApplication:",
            "socket(", "connect(", "appinst(", "fork(", "execve(",
            "unlinkat(", "unlink(", "rename(", "ftruncate(",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        self.assertIn("WR_DA_FRAME_BYTES 7u", header)
        self.assertIn("WR_DA_QUARANTINED", header)
        self.assertIn("bool protected_against_same_uid_tamper;", header)
        self.assertIn("bool installation_authorized;", header)


if __name__ == "__main__":
    unittest.main()
