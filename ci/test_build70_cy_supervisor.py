#!/usr/bin/env python3
"""CY: 16+ host adversarial checks for cooperative timeouts and bounded retry.

The native libraries are compiled only inside a synthetic CI test process.
These tests cannot validate real iOS12 helper identity, code signature,
installer operation, cancellation of an external worker, or real timing.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import ctypes
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
FRAME = b"WRCHK2\n"
MAX64 = (1 << 64) - 1

DENIED=0
STARTED=1
COALESCED=2
PENDING_FULL=3
COOLDOWN=4
COMPLETED=5
STOPPED=6
IDLE=7
STALE=8
TIMEOUT=9
WAITING_WORKER=10
ACK=11
BACKOFF=12
FAILURE=13
CANCELLED_PENDING=14


class Receipt(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("trusted_worker_ticket", ctypes.c_uint64),
        ("retry_after_ms", ctypes.c_uint64),
        ("pending_count", ctypes.c_uint8),
        ("failure_streak", ctypes.c_uint8),
        ("worker_may_still_be_running", ctypes.c_bool),
        ("cancel_requested", ctypes.c_bool),
        ("caller_authenticated", ctypes.c_bool),
        ("publisher_verified", ctypes.c_bool),
        ("ipa_bytes_authenticated", ctypes.c_bool),
        ("owner_consent_verified", ctypes.c_bool),
        ("installation_authorized", ctypes.c_bool),
        ("installation_performed", ctypes.c_bool)
    ]


class CYHostSupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="wr-cy-no-install-")
        compiler = shutil.which("clang") or shutil.which("cc")
        if not compiler:
            raise RuntimeError("C compiler required; tests cannot be skipped")
        path = Path(cls.folder.name) / ("cy.dylib" if sys.platform == "darwin" else "cy.so")
        subprocess.run(
            [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-pthread", "-fPIC", "-shared",
             str(ROOT / "build70_cx_bounded_scheduler.c"),
             str(ROOT / "build70_cy_supervisor.c"),
             "-o", str(path)],
            check=True, capture_output=True, text=True, timeout=30
        )
        cls.dll = ctypes.CDLL(str(path))
        cls.dll.wr_cy_new.restype = ctypes.c_void_p
        cls.dll.wr_cy_new.argtypes = ()
        for name, args in (
            ("wr_cy_offer", (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64)),
            ("wr_cy_poll", (ctypes.c_void_p, ctypes.c_uint64)),
            ("wr_cy_watchdog", (ctypes.c_void_p, ctypes.c_uint64)),
            ("wr_cy_complete", (ctypes.c_void_p, ctypes.c_uint64, ctypes.c_bool, ctypes.c_uint64)),
            ("wr_cy_ack_cancel", (ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64)),
            ("wr_cy_cancel_pending", (ctypes.c_void_p, ctypes.c_uint64)),
            ("wr_cy_shutdown", (ctypes.c_void_p,)),
        ):
            fn = getattr(cls.dll, name)
            fn.argtypes = args
            fn.restype = Receipt
        cls.dll.wr_cy_free.argtypes = (ctypes.c_void_p,)
        cls.dll.wr_cy_free.restype = None

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def create(self):
        s = self.dll.wr_cy_new()
        self.assertTrue(s)
        self.addCleanup(self.dll.wr_cy_free, s)
        return s

    def check(self, receipt, status=None, pending=None, active=None):
        if status is not None:
            self.assertEqual(receipt.status, status)
        if pending is not None:
            self.assertEqual(receipt.pending_count, pending)
        if active is not None:
            self.assertEqual(receipt.worker_may_still_be_running, active)
        self.assertLessEqual(receipt.pending_count, 1)
        self.assertLessEqual(receipt.failure_streak, 4)
        for attr in ("caller_authenticated", "publisher_verified",
                     "ipa_bytes_authenticated", "owner_consent_verified",
                     "installation_authorized", "installation_performed"):
            self.assertFalse(getattr(receipt, attr), attr)
        return receipt

    def offer(self, s, now, payload=FRAME):
        b = ctypes.create_string_buffer(payload)
        return self.check(self.dll.wr_cy_offer(s, b, len(payload), now))

    def poll(self, s, now):
        return self.check(self.dll.wr_cy_poll(s, now))

    def watchdog(self, s, now):
        return self.check(self.dll.wr_cy_watchdog(s, now))

    def complete(self, s, ticket, success, now):
        return self.check(self.dll.wr_cy_complete(s, ticket, success, now))

    def ack(self, s, ticket, now):
        return self.check(self.dll.wr_cy_ack_cancel(s, ticket, now))

    def test_clean_check_and_pending_recovery(self):
        s = self.create()
        first = self.check(self.offer(s, 0), STARTED, 0, True)
        self.assertEqual(first.trusted_worker_ticket, 1)
        self.check(self.offer(s, 1), COALESCED, 1, True)
        self.check(self.offer(s, 2), PENDING_FULL, 1, True)
        self.check(self.complete(s, 1, True, 100), COMPLETED, 1, False)
        self.check(self.poll(s, 59999), COOLDOWN, 1, False)
        second = self.check(self.poll(s, 60000), STARTED, 0, True)
        self.assertEqual(second.trusted_worker_ticket, 2)
        self.check(self.complete(s, 2, True, 60100), COMPLETED, 0, False)

    def test_watchdog_deadline_requires_worker_exit_ack(self):
        s = self.create()
        t = self.offer(s, 100000).trusted_worker_ticket
        self.check(self.watchdog(s, 114999), WAITING_WORKER, active=True)
        expired = self.check(self.watchdog(s, 115000), TIMEOUT, active=True)
        self.assertTrue(expired.cancel_requested)
        self.check(self.poll(s, 115001), TIMEOUT, active=True)
        self.check(self.offer(s, 115002), TIMEOUT, active=True)
        self.check(self.complete(s, t, True, 115003), TIMEOUT, active=True)
        self.check(self.ack(s, t+1, 115004), STALE, active=True)
        cleared = self.check(self.ack(s, t, 115005), ACK, 0, False)
        self.assertEqual(cleared.failure_streak, 1)
        self.assertEqual(cleared.retry_after_ms, 30000)
        self.check(self.ack(s, t, 115006), STALE, 0, False)
        self.check(self.offer(s, 115007), BACKOFF, 0, False)

    def test_clock_forward_without_watchdog_cannot_complete_overdue(self):
        s = self.create()
        t = self.offer(s, 0).trusted_worker_ticket
        r = self.check(self.complete(s, t, True, 15000), TIMEOUT, active=True)
        self.assertTrue(r.cancel_requested)
        self.check(self.ack(s, t, 15001), ACK, 0, False)

    def test_pending_cannot_start_when_cancel_request_unacknowledged(self):
        s = self.create()
        t = self.offer(s, 0).trusted_worker_ticket
        self.offer(s, 100)
        self.check(self.watchdog(s, 15000), TIMEOUT, 1, True)
        for now in (15001, 20000, 300000, 500000):
            self.check(self.poll(s, now), TIMEOUT, 1, True)
            self.check(self.offer(s, now), TIMEOUT, 1, True)
        self.check(self.ack(s, t, 500001), ACK, 0, False)
        self.check(self.poll(s, 900000), IDLE, 0, False)

    def test_early_success_clears_failure_streak(self):
        s = self.create()
        t = self.offer(s, 0).trusted_worker_ticket
        self.check(self.complete(s, t, False, 100), FAILURE, 0, False)
        self.check(self.offer(s, 101), BACKOFF)
        next_ticket = self.check(self.offer(s, 60000), STARTED).trusted_worker_ticket
        r = self.check(self.complete(s, next_ticket, True, 60100), COMPLETED)
        self.assertEqual(r.failure_streak, 0)
        self.assertEqual(r.retry_after_ms, 0)

    def test_backoff_exponentially_increases_and_caps(self):
        s = self.create()
        for i, expected in enumerate((30000, 60000, 120000, 240000, 240000)):
            start = i * 300000
            t = self.check(self.offer(s, start), STARTED).trusted_worker_ticket
            r = self.check(self.complete(s, t, False, start + 100), FAILURE, 0, False)
            self.assertEqual(r.retry_after_ms, expected)
            self.assertEqual(r.failure_streak, min(i+1, 4))
            self.check(self.offer(s, start+101), BACKOFF, 0, False)
        self.check(self.offer(s, 1500000), STARTED, 0, True)

    def test_failure_discards_preexisting_queued_check(self):
        s = self.create()
        t = self.offer(s, 0).trusted_worker_ticket
        self.offer(s, 100)
        self.check(self.complete(s, t, False, 101), FAILURE, 0, False)
        self.check(self.poll(s, 60000), IDLE, 0, False)

    def test_wrong_or_zero_ticket_rejected_without_changing_worker(self):
        s = self.create()
        t = self.offer(s, 10000).trusted_worker_ticket
        for ticket in (0, t+2, MAX64):
            self.check(self.complete(s, ticket, True, 10001), STALE, active=True)
            self.check(self.ack(s, ticket, 10001), STALE, active=True)
        self.check(self.complete(s, t, True, 10002), COMPLETED, 0, False)

    def test_invalid_payload_cannot_rewind_or_consume_clock(self):
        s = self.create()
        for bad in (b"", b"WRINST1\n", b"WRCHK2\r\n",
                    b"WRCHK2\nurl=https://evil.invalid/ipa",
                    b"WRCHK2\nI-CONFIRM-INSTALL", b"WRCHK2\n\x00",
                    FRAME+b"A"*200000):
            self.check(self.offer(s, MAX64, bad), DENIED, 0, False)
        self.check(self.offer(s, 0), STARTED, 0, True)

    def test_250_concurrent_requests_exactly_one_active_and_one_pending(self):
        s = self.create()
        with ThreadPoolExecutor(max_workers=28) as pool:
            results = list(pool.map(lambda _: self.offer(s, 100000), range(250)))
        self.assertEqual(sum(r.status == STARTED for r in results), 1)
        self.assertEqual(sum(r.status == COALESCED for r in results), 1)
        self.assertEqual(sum(r.status == PENDING_FULL for r in results), 248)
        self.assertTrue(all(r.pending_count <= 1 for r in results))

    def test_cancel_pending_leaves_active_worker_running(self):
        s = self.create()
        t = self.offer(s, 0).trusted_worker_ticket
        self.offer(s, 100)
        r = self.check(self.dll.wr_cy_cancel_pending(s, 101), CANCELLED_PENDING, 0, True)
        self.assertEqual(r.trusted_worker_ticket, t)
        self.check(self.complete(s, t, True, 102), COMPLETED, 0, False)

    def test_clock_rewind_denied_across_all_operations(self):
        s = self.create()
        t = self.offer(s, 100000).trusted_worker_ticket
        self.check(self.watchdog(s, 99999), STALE, active=True)
        self.check(self.poll(s, 99999), STALE, active=True)
        self.check(self.complete(s, t, True, 99999), STALE, active=True)
        self.check(self.ack(s, t, 99999), STALE, active=True)
        self.check(self.dll.wr_cy_cancel_pending(s, 99999), STALE, active=True)
        self.check(self.complete(s, t, True, 100010), COMPLETED, 0, False)

    def test_uint64_overflow_fails_closed(self):
        s = self.create()
        ticket = self.offer(s, MAX64-1).trusted_worker_ticket
        self.check(self.watchdog(s, MAX64), WAITING_WORKER, active=True)
        self.check(self.complete(s, ticket, True, MAX64), COMPLETED)
        self.check(self.offer(s, 0), STALE)

    def test_shutdown_does_not_pretend_active_worker_stopped(self):
        s = self.create()
        ticket = self.offer(s, 0).trusted_worker_ticket
        self.offer(s, 1)
        state = self.check(self.dll.wr_cy_shutdown(s), STOPPED, 0, True)
        self.assertTrue(state.worker_may_still_be_running)
        self.check(self.offer(s, 100000), STOPPED, 0, True)
        self.check(self.poll(s, 100000), STOPPED, 0, True)
        self.check(self.complete(s, ticket, True, 100000), STOPPED, 0, True)
        self.check(self.ack(s, ticket, 100000), STOPPED, 0, True)
        # Real worker join is caller-owned; no background activity in harness.

    def test_null_pointer_fails_closed(self):
        self.check(self.dll.wr_cy_offer(None, None, 0, 0), DENIED)
        self.check(self.dll.wr_cy_poll(None, 0), DENIED)
        self.check(self.dll.wr_cy_watchdog(None, 0), DENIED)
        self.check(self.dll.wr_cy_complete(None, 1, True, 0), DENIED)
        self.check(self.dll.wr_cy_ack_cancel(None, 1, 0), DENIED)
        self.check(self.dll.wr_cy_cancel_pending(None, 0), DENIED)
        self.check(self.dll.wr_cy_shutdown(None), DENIED)

    def test_separate_supervisors_do_not_prove_global_quota(self):
        a, b = self.create(), self.create()
        self.check(self.offer(a, 0), STARTED)
        self.check(self.offer(b, 0), STARTED)

    def test_real_host_thread_must_exit_before_trusted_ack(self):
        # A synthetic worker thread performs no network, install, or IO.
        # It does not stop just because the watchdog marks its lease expired.
        import threading
        started = threading.Event()
        release = threading.Event()
        exited = threading.Event()
        s = self.create()
        ticket = self.offer(s, 100_000).trusted_worker_ticket

        def worker():
            started.set()
            release.wait(timeout=5)
            exited.set()

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            self.assertTrue(started.wait(timeout=2))
            r = self.check(self.watchdog(s, 115_000), TIMEOUT, 0, True)
            self.assertTrue(r.cancel_requested)
            self.assertTrue(thread.is_alive())  # timeout did not interrupt worker
            self.check(self.offer(s, 300_000), TIMEOUT, 0, True)
            # Do NOT simulate ACK before worker actually stops.
        finally:
            release.set()
            thread.join(timeout=2)
        self.assertFalse(thread.is_alive())
        self.assertTrue(exited.is_set())
        self.check(self.ack(s, ticket, 300_001), ACK, 0, False)
        self.check(self.offer(s, 300_002), BACKOFF, 0, False)

    def test_no_network_install_process_or_file_api(self):
        source = (ROOT / "build70_cy_supervisor.c").read_text()
        for forbidden in ("posix_spawn(", "objc_msgSend(", "installApplication:",
                          "socket(", "connect(", "open(", "appinst(",
                          "curl ", "system(", "fork(", "execve("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
