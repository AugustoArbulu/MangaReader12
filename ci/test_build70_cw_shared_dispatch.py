#!/usr/bin/env python3
"""CW single-process native mutex dispatcher under hostile concurrent load.

No network, files of the user, helper daemon, elevated privileges or install.
"""
from concurrent.futures import ThreadPoolExecutor
import ctypes
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from test_build70_cw_checkonly_core import FRAME, Decision

ROOT = Path(__file__).resolve().parent


class CWSharedDispatcherTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="wr-cw-dispatch-")
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            raise RuntimeError("C compiler unavailable; cannot fake pass")
        out = Path(cls.folder.name) / (
            "libcwdispatch.dylib" if sys.platform == "darwin" else "libcwdispatch.so"
        )
        subprocess.run(
            [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-fPIC", "-shared", "-pthread",
             str(ROOT / "build70_cw_checkonly_core.c"),
             str(ROOT / "build70_cw_shared_dispatch.c"),
             "-o", str(out)],
            check=True, capture_output=True, text=True, timeout=30)
        cls.lib = ctypes.CDLL(str(out))
        cls.lib.wr_cw_dispatch_new.argtypes = ()
        cls.lib.wr_cw_dispatch_new.restype = ctypes.c_void_p
        cls.lib.wr_cw_dispatch_offer.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p,
            ctypes.c_size_t, ctypes.c_uint64)
        cls.lib.wr_cw_dispatch_offer.restype = Decision
        cls.lib.wr_cw_dispatch_free.argtypes = (ctypes.c_void_p,)
        cls.lib.wr_cw_dispatch_free.restype = None

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def new(self):
        handle = self.lib.wr_cw_dispatch_new()
        self.assertTrue(handle)
        self.addCleanup(self.lib.wr_cw_dispatch_free, handle)
        return handle

    def offer(self, handle, message=FRAME, ms=0):
        buf = ctypes.create_string_buffer(message)
        outcome = self.lib.wr_cw_dispatch_offer(handle, buf, len(message), ms)
        for name in (
            "caller_authenticated", "publisher_verified",
            "artifact_selected_by_client", "installer_authorized",
            "installation_performed"
        ):
            self.assertFalse(getattr(outcome, name), name)
        return outcome.status

    def test_concurrent_client_burst_gets_one_notice_per_shared_process(self):
        handle = self.new()
        with ThreadPoolExecutor(max_workers=32) as pool:
            results = list(pool.map(
                lambda _: self.offer(handle, ms=300_000), range(128)))
        self.assertEqual(results.count(1), 1)
        self.assertEqual(results.count(2), 127)

    def test_invalid_flood_never_uses_interval(self):
        handle = self.new()
        with ThreadPoolExecutor(max_workers=16) as pool:
            results = list(pool.map(
                lambda _: self.offer(handle, b"WRINST1\n", 500), range(80)))
        self.assertEqual(results.count(0), 80)
        self.assertEqual(self.offer(handle, FRAME, 500), 1)
        self.assertEqual(self.offer(handle, FRAME, 500), 2)

    def test_null_dispatcher_rejected(self):
        self.assertEqual(self.offer(None, FRAME, 0), 0)

    def test_two_independent_process_models_are_not_cross_process_limit(self):
        first = self.new()
        second = self.new()
        self.assertEqual(self.offer(first, FRAME, 0), 1)
        self.assertEqual(self.offer(second, FRAME, 0), 1)
        # Other processes could still bypass this per-process quota.

    def test_clock_rewind_with_shared_gate_denied(self):
        handle = self.new()
        self.assertEqual(self.offer(handle, FRAME, 60_000), 1)
        self.assertEqual(self.offer(handle, FRAME, 0), 2)
        self.assertEqual(self.offer(handle, FRAME, 119_999), 2)
        self.assertEqual(self.offer(handle, FRAME, 120_000), 1)

    def test_no_privileged_api_in_dispatcher_source(self):
        source = (ROOT / "build70_cw_shared_dispatch.c").read_text()
        for forbidden in ("posix_spawn(", "fork(", "execve(", "system(",
                          "open(", "socket(", "connect(", "appinst(",
                          "installApplication:"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
