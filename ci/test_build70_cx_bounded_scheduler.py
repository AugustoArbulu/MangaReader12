#!/usr/bin/env python3
"""Phase CX adversarial host tests for a bounded, nonprivileged C state machine.

Only synthetic queue lifecycle; NO socket, device, appinst or update fetch.
"""
from concurrent.futures import ThreadPoolExecutor
import ctypes
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

FRAME = b"WRCHK2\n"
MAX = (1 << 64) - 1
ROOT = Path(__file__).resolve().parent


class Receipt(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("local_worker_ticket", ctypes.c_uint64),
        ("pending_count", ctypes.c_uint8),
        ("check_inflight", ctypes.c_bool),
        ("caller_authenticated", ctypes.c_bool),
        ("publisher_verified", ctypes.c_bool),
        ("client_can_choose_artifact", ctypes.c_bool),
        ("immutable_installer_input_proven", ctypes.c_bool),
        ("owner_consent_verified", ctypes.c_bool),
        ("installation_authorized", ctypes.c_bool),
        ("installation_performed", ctypes.c_bool),
    ]


class CXBoundedSchedulerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="wr-cx-host-")
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            raise RuntimeError("C compiler is required; no skipped tests")
        library = Path(cls.temp.name) / (
            "libcx.dylib" if sys.platform == "darwin" else "libcx.so"
        )
        subprocess.run(
            [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-pthread", "-fPIC", "-shared",
             str(ROOT / "build70_cx_bounded_scheduler.c"),
             "-o", str(library)],
            check=True, capture_output=True, text=True, timeout=30
        )
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.wr_cx_new.argtypes = ()
        cls.lib.wr_cx_new.restype = ctypes.c_void_p
        for name, args in {
            "wr_cx_offer": (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64),
            "wr_cx_poll": (ctypes.c_void_p, ctypes.c_uint64),
            "wr_cx_finish": (ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64),
            "wr_cx_cancel_pending": (ctypes.c_void_p, ctypes.c_uint64),
            "wr_cx_cancel_active": (ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64),
            "wr_cx_shutdown": (ctypes.c_void_p,),
        }.items():
            fn = getattr(cls.lib, name)
            fn.argtypes = args
            fn.restype = Receipt
        cls.lib.wr_cx_free.argtypes = (ctypes.c_void_p,)
        cls.lib.wr_cx_free.restype = None

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def make(self):
        pointer = self.lib.wr_cx_new()
        self.assertTrue(pointer)
        self.addCleanup(self.lib.wr_cx_free, pointer)
        return pointer

    def safe(self, r, status=None, pending=None):
        if status is not None:
            self.assertEqual(r.status, status)
        if pending is not None:
            self.assertEqual(r.pending_count, pending)
        self.assertLessEqual(r.pending_count, 1)
        for name in ("caller_authenticated", "publisher_verified",
                     "client_can_choose_artifact", "immutable_installer_input_proven",
                     "owner_consent_verified", "installation_authorized",
                     "installation_performed"):
            self.assertFalse(getattr(r, name), name)
        return r

    def offer(self, s, now, frame=FRAME):
        b = ctypes.create_string_buffer(frame)
        return self.safe(self.lib.wr_cx_offer(s, b, len(frame), now))

    def poll(self, s, now):
        return self.safe(self.lib.wr_cx_poll(s, now))

    def finish(self, s, ticket, now):
        return self.safe(self.lib.wr_cx_finish(s, ticket, now))

    def test_basic_single_active_and_one_coalesced_pending(self):
        s = self.make()
        first = self.safe(self.offer(s, 100_000), 1, 0)
        self.assertTrue(first.check_inflight)
        self.assertEqual(first.local_worker_ticket, 1)
        self.safe(self.offer(s, 100_000), 2, 1)
        self.safe(self.offer(s, 100_000), 3, 1)
        self.safe(self.poll(s, 100_100), 10, 1)
        self.safe(self.finish(s, first.local_worker_ticket, 100_200), 5, 1)
        self.safe(self.poll(s, 159_999), 4, 1)
        next_one = self.safe(self.poll(s, 160_000), 1, 0)
        self.assertEqual(next_one.local_worker_ticket, 2)
        self.safe(self.finish(s, 2, 160_100), 5, 0)
        self.safe(self.poll(s, 220_000), 7, 0)

    def test_concurrent_512_frames_single_active_one_pending(self):
        s = self.make()
        with ThreadPoolExecutor(max_workers=32) as pool:
            answers = list(pool.map(lambda _: self.offer(s, 1_000_000), range(512)))
        counts = {value: sum(1 for r in answers if r.status == value)
                  for value in (1, 2, 3)}
        self.assertEqual(counts, {1: 1, 2: 1, 3: 510})
        self.assertEqual(sum(r.status == 0 for r in answers), 0)
        self.assertEqual(sum(r.pending_count > 1 for r in answers), 0)

    def test_hostile_frames_do_not_affect_queue_or_clock(self):
        s = self.make()
        for payload in (b"", b"WRCHK2", b"WRINST1\n", b"WRCHK2\nURI=https://x.invalid",
                        b"WRCHK2\nI-CONFIRM-INSTALL", b"WRCHK2\n\x00", b"wrchk2\n",
                        b"WRCHK2\r\n", FRAME + b"X" * 131072):
            with self.subTest(payload=payload[:15]):
                self.safe(self.offer(s, MAX, payload), 0, 0)
        self.safe(self.offer(s, 0), 1, 0)
        self.safe(self.offer(s, 0), 2, 1)

    def test_cooling_without_active_still_queues_once(self):
        s = self.make()
        ticket = self.offer(s, 1000).local_worker_ticket
        self.safe(self.finish(s, ticket, 2000), 5)
        self.safe(self.offer(s, 3000), 2, 1)
        self.safe(self.offer(s, 3000), 3, 1)
        self.safe(self.poll(s, 60999), 4, 1)
        self.safe(self.poll(s, 61000), 1, 0)

    def test_stale_worker_ticket_cannot_complete_new_check(self):
        s = self.make()
        first = self.offer(s, 100_000).local_worker_ticket
        self.offer(s, 100_001)
        self.safe(self.finish(s, first, 100_100), 5)
        second = self.poll(s, 160_000).local_worker_ticket
        self.assertNotEqual(first, second)
        r = self.safe(self.finish(s, first, 160_010), 8)
        self.assertTrue(r.check_inflight)
        self.assertEqual(r.local_worker_ticket, second)
        self.safe(self.finish(s, second, 160_011), 5)

    def test_cancel_pending_does_not_cancel_active(self):
        s = self.make()
        first = self.offer(s, 10_000).local_worker_ticket
        self.offer(s, 10_100)
        r = self.safe(self.lib.wr_cx_cancel_pending(s, 10_200), 6, 0)
        self.assertTrue(r.check_inflight)
        self.assertEqual(r.local_worker_ticket, first)
        self.safe(self.finish(s, first, 10_300), 5, 0)
        self.safe(self.poll(s, 90_000), 7, 0)

    def test_cancel_active_clears_pending_and_invalidates_ticket(self):
        s = self.make()
        t = self.offer(s, 100_000).local_worker_ticket
        self.offer(s, 100_000)
        r = self.safe(self.lib.wr_cx_cancel_active(s, t, 100_100), 6, 0)
        self.assertFalse(r.check_inflight)
        self.assertEqual(r.local_worker_ticket, 0)
        self.safe(self.finish(s, t, 100_101), 8, 0)
        self.safe(self.poll(s, 200_000), 7, 0)

    def test_wrong_ticket_does_not_cancel_valid_worker(self):
        s = self.make()
        t = self.offer(s, 100_000).local_worker_ticket
        self.offer(s, 100_100)
        r = self.safe(self.lib.wr_cx_cancel_active(s, t + 999, 100_200), 8, 1)
        self.assertTrue(r.check_inflight)
        self.safe(self.finish(s, t, 100_201), 5, 1)

    def test_clock_rewind_fails_without_queue_mutation(self):
        s = self.make()
        first = self.offer(s, 500_000).local_worker_ticket
        self.safe(self.offer(s, 499_999), 8, 0)
        self.safe(self.poll(s, 499_999), 8, 0)
        self.safe(self.finish(s, first, 499_999), 8, 0)
        self.safe(self.lib.wr_cx_cancel_active(s, first, 499_999), 8, 0)
        self.safe(self.offer(s, 500_001), 2, 1)

    def test_max_uint64_timestamp_no_overflow(self):
        s = self.make()
        t = self.offer(s, MAX - 5).local_worker_ticket
        self.safe(self.finish(s, t, MAX - 4), 5)
        self.safe(self.offer(s, MAX - 1), 2, 1)
        self.safe(self.poll(s, MAX), 4, 1)
        self.safe(self.poll(s, 0), 8, 1)

    def test_empty_cancel_pending_is_idle(self):
        s = self.make()
        self.safe(self.lib.wr_cx_cancel_pending(s, 20), 7, 0)
        self.safe(self.poll(s, 20), 7, 0)

    def test_shutdown_clears_queue_and_denies_future_work(self):
        s = self.make()
        t = self.offer(s, 100_000).local_worker_ticket
        self.offer(s, 100_100)
        r = self.safe(self.lib.wr_cx_shutdown(s), 9, 0)
        self.assertFalse(r.check_inflight)
        self.safe(self.offer(s, 300_000), 9, 0)
        self.safe(self.poll(s, 300_000), 9, 0)
        self.safe(self.finish(s, t, 300_000), 9, 0)
        self.safe(self.lib.wr_cx_cancel_pending(s, 300_000), 9, 0)
        self.safe(self.lib.wr_cx_cancel_active(s, t, 300_000), 9, 0)

    def test_two_process_models_still_have_separate_quotas(self):
        a, b = self.make(), self.make()
        self.safe(self.offer(a, 0), 1)
        self.safe(self.offer(b, 0), 1)
        # Does NOT prove cross-process global control or durability.

    def test_null_scheduler_and_null_frame_fail_closed(self):
        self.safe(self.lib.wr_cx_offer(None, None, 0, 0), 0)
        self.safe(self.lib.wr_cx_poll(None, 0), 0)
        self.safe(self.lib.wr_cx_finish(None, 1, 0), 0)
        self.safe(self.lib.wr_cx_cancel_pending(None, 0), 0)
        self.safe(self.lib.wr_cx_cancel_active(None, 1, 0), 0)
        self.safe(self.lib.wr_cx_shutdown(None), 0)
        s = self.make()
        self.safe(self.lib.wr_cx_offer(s, None, 7, 0), 0)

    def test_no_io_ipc_or_installer_symbols_in_c(self):
        src = (ROOT / "build70_cx_bounded_scheduler.c").read_text()
        for forbidden in ("posix_spawn(", "objc_msgSend(", "installApplication:",
                          "socket(", "connect(", "open(", "appinst(",
                          "curl ", "system(", "fork(", "execve("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
