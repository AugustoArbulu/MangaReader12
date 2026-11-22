#!/usr/bin/env python3
"""CZ: synthetic worker CY integration / hostile concurrency and recovery tests.

Compile a disposable C host library, execute Python worker threads and verify
ACK-after-exit. No device, real network, appinst, IPA, release or privilege.
"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import ctypes
import shutil
import subprocess
import sys
import tempfile
import unittest

from build70_cz_synthetic_worker_runtime import (
    ACK, BACKOFF, COMPLETED, FAILURE, FRAME, STARTED, TIMEOUT,
    SyntheticCheckRuntime, SyntheticServiceRejected
)

ROOT = Path(__file__).resolve().parent


class CZHostWorkerIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr-cz-native-host-only-")
        compiler = shutil.which("clang") or shutil.which("cc")
        if compiler is None:
            raise RuntimeError("native compiler required; no fallback pass")
        output = Path(cls.tmp.name) / (
            "libcz.dylib" if sys.platform == "darwin" else "libcz.so"
        )
        subprocess.run(
            [compiler, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-pthread", "-shared", "-fPIC",
             str(ROOT / "build70_cx_bounded_scheduler.c"),
             str(ROOT / "build70_cy_supervisor.c"),
             "-o", str(output)],
            check=True, capture_output=True, text=True, timeout=30
        )
        cls.native = ctypes.CDLL(str(output))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def create(self, **kwargs):
        runtime = SyntheticCheckRuntime(self.native, **kwargs)
        self.addCleanup(runtime.close)
        return runtime

    def finished(self, runtime):
        self.assertIsNotNone(runtime.worker)
        self.assertTrue(runtime.worker.finished.wait(2))
        receipt = runtime.reap_finished_worker()
        self.assertIsNotNone(receipt)
        return receipt

    def test_normal_completion_then_coalesced_followup(self):
        s = self.create()
        first = s.offer_untrusted(FRAME)
        self.assertEqual(first.status, STARTED)
        self.assertTrue(s.worker.started.wait(2))
        self.assertEqual(s.offer_untrusted(FRAME).status, 2)
        self.assertEqual(s.offer_untrusted(FRAME).status, 3)
        s.release_synthetic_worker(success=True)
        result = self.finished(s)
        self.assertEqual(result.status, COMPLETED)
        self.assertEqual(s.started_count, 1)
        self.assertEqual(s.poll_host_queue().status, 4)
        s.advance_host_clock(59999)
        self.assertEqual(s.poll_host_queue().status, 4)
        s.advance_host_clock(1)
        self.assertEqual(s.poll_host_queue().status, STARTED)
        s.release_synthetic_worker(success=True)
        self.assertEqual(self.finished(s).status, COMPLETED)
        self.assertEqual(s.started_count, 2)
        self.assertEqual(s.completed_count, 2)

    def test_stuck_worker_timeout_never_creates_replacement(self):
        s = self.create(block_worker=True)
        receipt = s.offer_untrusted(FRAME)
        self.assertEqual(receipt.status, STARTED)
        self.assertTrue(s.worker.started.wait(2))
        s.offer_untrusted(FRAME)
        s.advance_host_clock(15000)
        self.assertTrue(s.worker.cancelled.is_set())
        self.assertTrue(s.worker.thread.is_alive())
        self.assertIsNone(s.reap_finished_worker())
        self.assertEqual(s.poll_host_queue().status, TIMEOUT)
        s.advance_host_clock(700000)
        self.assertEqual(s.offer_untrusted(FRAME).status, TIMEOUT)
        self.assertEqual(s.started_count, 1)
        self.assertIsNone(s.reap_finished_worker())
        s.release_synthetic_worker()
        done = self.finished(s)
        self.assertEqual(done.status, ACK)
        self.assertEqual(s.acked_count, 1)
        self.assertEqual(s.started_count, 1)

    def test_responsive_worker_exits_on_cooperative_timeout(self):
        s = self.create()
        s.offer_untrusted(FRAME)
        self.assertTrue(s.worker.started.wait(2))
        s.advance_host_clock(15000)
        self.assertTrue(s.worker.cancelled.is_set())
        self.assertEqual(self.finished(s).status, ACK)
        self.assertIsNone(s.worker)
        self.assertEqual(s.offer_untrusted(FRAME).status, BACKOFF)
        s.advance_host_clock(30000)
        self.assertEqual(s.offer_untrusted(FRAME).status, 2)  # cooldown since initial start
        self.assertEqual(s.started_count, 1)

    def test_late_success_cannot_override_timeout(self):
        s = self.create()
        s.offer_untrusted(FRAME)
        s.release_synthetic_worker(success=True)
        self.assertTrue(s.worker.finished.wait(2))
        s.advance_host_clock(15000)
        self.assertEqual(s.reap_finished_worker().status, ACK)
        self.assertEqual(s.completed_count, 0)

    def test_synthetic_worker_failure_triggers_backoff_without_pending(self):
        s = self.create()
        s.offer_untrusted(FRAME)
        s.offer_untrusted(FRAME)
        s.release_synthetic_worker(success=False)
        out = self.finished(s)
        self.assertEqual(out.status, FAILURE)
        self.assertEqual(out.retry_after_ms, 30000)
        self.assertEqual(out.pending_count, 0)
        self.assertEqual(s.offer_untrusted(FRAME).status, BACKOFF)
        s.advance_host_clock(60000)
        self.assertEqual(s.offer_untrusted(FRAME).status, STARTED)
        s.release_synthetic_worker(success=True)
        self.assertEqual(self.finished(s).status, COMPLETED)
        self.assertEqual(s.worker, None)

    def test_256_untrusted_concurrent_frames_only_one_worker(self):
        s = self.create()
        with ThreadPoolExecutor(max_workers=24) as pool:
            results = list(pool.map(lambda _: s.offer_untrusted(FRAME).status,
                                    range(256)))
        self.assertEqual(results.count(STARTED), 1)
        self.assertEqual(results.count(2), 1)
        self.assertEqual(results.count(3), 254)
        self.assertEqual(s.started_count, 1)
        self.assertEqual(s.worker.ticket, 1)
        s.release_synthetic_worker()
        self.assertEqual(self.finished(s).status, COMPLETED)

    def test_invalid_install_frames_cannot_select_payload_or_work(self):
        s = self.create()
        for frame in (b"", b"WRINST1\n", b"WRCHK2", b"WRCHK2\nPATH=foo",
                      b"WRCHK2\nurl=https://evil.invalid/asset.ipa",
                      b"WRCHK2\nI-CONFIRM-INSTALL", b"WRCHK2\x00",
                      b"WRCHK2\n" + b"A"*100_000):
            self.assertEqual(s.offer_untrusted(frame).status, 0)
        self.assertEqual(s.started_count, 0)
        self.assertEqual(s.offer_untrusted(FRAME).status, STARTED)

    def test_untrusted_client_cannot_set_clock_or_recovery_flag(self):
        s = self.create()
        for bad in (None, "WRCHK2\n", bytearray(FRAME), True):
            with self.assertRaises(SyntheticServiceRejected):
                s.offer_untrusted(bad)
        with self.assertRaises(TypeError):
            s.offer_untrusted(FRAME, now_ms=1000000)
        with self.assertRaises(TypeError):
            s.offer_untrusted(FRAME, owner_consent=True)
        self.assertEqual(s.now_ms, 0)
        self.assertEqual(s.started_count, 0)

    def test_unknown_crash_quarantine_requires_explicit_host_reconciliation(self):
        s = self.create(recovery_required=True)
        with self.assertRaises(SyntheticServiceRejected):
            s.offer_untrusted(FRAME)
        with self.assertRaises(SyntheticServiceRejected):
            s.poll_host_queue()
        self.assertEqual(s.started_count, 0)
        s.reconcile_quarantine_host_only()
        self.assertEqual(s.offer_untrusted(FRAME).status, STARTED)
        # This is NOT proof of a durable journal, protected process ID, or
        # actual crash detection. The recovery flag was injected by tests.

    def test_recovered_instance_is_not_durable_without_external_state(self):
        original = self.create()
        original.offer_untrusted(FRAME)
        second = self.create()
        self.assertEqual(second.offer_untrusted(FRAME).status, STARTED)
        self.assertEqual(original.started_count, 1)
        self.assertEqual(second.started_count, 1)
        # Demonstrates the unsolved cross-process/restart gap: the future
        # helper must have protected durable monotonic state.

    def test_close_must_join_worker_and_refuse_future_triggers(self):
        s = self.create(block_worker=True)
        s.offer_untrusted(FRAME)
        self.assertTrue(s.worker.started.wait(2))
        s.close()
        self.assertTrue(s.closed)
        self.assertIsNone(s.worker)
        with self.assertRaises(SyntheticServiceRejected):
            s.offer_untrusted(FRAME)
        with self.assertRaises(SyntheticServiceRejected):
            s.advance_host_clock(1)

    def test_overflow_and_invalid_host_clock_rejected(self):
        s = self.create()
        for bad in (None, -1, True, 1.5, "15000"):
            with self.assertRaises(SyntheticServiceRejected):
                s.advance_host_clock(bad)
        s.advance_host_clock((1 << 64)-1)
        with self.assertRaises(SyntheticServiceRejected):
            s.advance_host_clock(1)
        self.assertEqual(s.started_count, 0)

    def test_supervisor_never_claims_editor_identity_or_install_authority(self):
        s = self.create()
        receipts = [s.offer_untrusted(FRAME), s.advance_host_clock(15000)]
        for r in receipts:
            for field in ("caller_authenticated", "publisher_verified",
                          "ipa_bytes_authenticated", "owner_consent_verified",
                          "installation_authorized", "installation_performed"):
                self.assertFalse(getattr(r, field), field)

    def test_no_network_external_process_or_install_calls_in_worker(self):
        text = (ROOT / "build70_cz_synthetic_worker_runtime.py").read_text()
        for forbidden in ("subprocess", "requests.", "urllib", "socket.",
                          "posix_spawn", "os.system(", "appinst(", "installApplication:",
                          "git clone", "WRINST1\n"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
