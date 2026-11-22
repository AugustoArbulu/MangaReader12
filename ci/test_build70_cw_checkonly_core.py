#!/usr/bin/env python3
"""CW native C CHECK_ONLY parser, hostile payloads and Python-C equivalence.

Builds an ephemeral test library locally. Not an app, service, updater,
installer, privilege test, IPA or DEB. The real CN Python module is used.
"""
from __future__ import annotations
import ctypes
from pathlib import Path
import random
import shutil
import subprocess
import sys
import tempfile
import unittest

from build70_cn_untrusted_check_only_gate import CheckOnlyGate, CheckOnlyRejected

ROOT = Path(__file__).resolve().parent
FRAME = b"WRCHK2\n"
MAX64 = (1 << 64) - 1


class Gate(ctypes.Structure):
    _fields_ = [("seen", ctypes.c_bool), ("last_accepted_ms", ctypes.c_uint64)]


class Decision(ctypes.Structure):
    _fields_ = [("status", ctypes.c_int), ("caller_authenticated", ctypes.c_bool),
                ("publisher_verified", ctypes.c_bool),
                ("artifact_selected_by_client", ctypes.c_bool),
                ("installer_authorized", ctypes.c_bool),
                ("installation_performed", ctypes.c_bool)]


class CWNativeCheckOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix="wr-cw-native-only-")
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            raise RuntimeError("C compiler unavailable; cannot fake pass")
        out = Path(cls.folder.name) / (
            "libcw.dylib" if sys.platform == "darwin" else "libcw.so"
        )
        args = [cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
                "-fPIC", "-shared", str(ROOT / "build70_cw_checkonly_core.c"),
                "-o", str(out)]
        subprocess.run(args, check=True, capture_output=True, text=True, timeout=30)
        cls.lib = ctypes.CDLL(str(out))
        cls.lib.wr_cw_offer.argtypes = (ctypes.POINTER(Gate), ctypes.c_void_p,
                                       ctypes.c_size_t, ctypes.c_uint64)
        cls.lib.wr_cw_offer.restype = Decision

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def call(self, gate, payload, ms):
        if payload is None:
            return self.lib.wr_cw_offer(ctypes.byref(gate), None, 0, ms)
        b = ctypes.create_string_buffer(payload)
        return self.lib.wr_cw_offer(ctypes.byref(gate), b, len(payload), ms)

    def safe(self, result, expected):
        self.assertEqual(result.status, expected)
        for name in ("caller_authenticated", "publisher_verified",
                     "artifact_selected_by_client", "installer_authorized",
                     "installation_performed"):
            self.assertFalse(getattr(result, name), name)

    def test_one_notice_only_no_install(self):
        g = Gate()
        self.safe(self.call(g, FRAME, 100_000), 1)
        self.safe(self.call(g, FRAME, 100_000), 2)
        self.safe(self.call(g, FRAME, 159_999), 2)
        self.safe(self.call(g, FRAME, 160_000), 1)
        self.safe(self.call(g, FRAME, 1_000), 2)

    def test_bad_bytes_are_rejected_without_consuming_budget(self):
        g = Gate()
        for bad in (b"", b"WRCHK2", b"WRCHK2\r\n", b"WRINST1\n", b"WRCHK2\n\x00",
                    b"WRCHK2\nURL=https://evil.invalid/a.ipa",
                    b"WRCHK2\nI-CONFIRM-INSTALL",
                    b"WRCHK2\n" + b"A" * 65536, b"wrchk2\n", b"WRCHK1\n", None):
            with self.subTest(bad=repr(bad)[:25]):
                self.safe(self.call(g, bad, 0), 0)
                self.assertFalse(g.seen)
        self.safe(self.call(g, FRAME, 0), 1)

    def test_uint64_near_max_does_not_wrap(self):
        g = Gate()
        self.safe(self.call(g, FRAME, MAX64 - 1000), 1)
        self.safe(self.call(g, FRAME, MAX64), 2)
        self.safe(self.call(g, FRAME, 0), 2)

    def test_odd_gate_state_is_fail_closed_on_clock_rewind(self):
        g = Gate(True, 500_000)
        self.safe(self.call(g, FRAME, 499_999), 2)
        self.safe(self.call(g, FRAME, 560_000), 1)

    def test_ctypes_native_and_existing_python_cn_gate_agree(self):
        rnd = random.Random(777)
        native = Gate()
        python = CheckOnlyGate()
        now = 0
        for _ in range(1300):
            now = max(0, now + rnd.choice([-30, 0, 0, 5, 20, 60, 61, 120]))
            payload = rnd.choice([FRAME, FRAME, FRAME, b"WRINST1\n",
                                  b"WRCHK2\nURL=bad", b"X"])
            cresult = self.call(native, payload, now * 1000)
            if payload != FRAME:
                with self.assertRaises(CheckOnlyRejected):
                    python.offer(payload, monotonic_seconds=now)
                self.safe(cresult, 0)
            else:
                py = python.offer(payload, monotonic_seconds=now)
                self.safe(cresult, 1 if py.check_notice_accepted else 2)

    def test_null_gate_never_succeeds(self):
        data = ctypes.create_string_buffer(FRAME)
        result = self.lib.wr_cw_offer(None, data, len(FRAME), 0)
        self.safe(result, 0)

    def test_two_independent_gates_are_not_a_global_rate_limiter(self):
        first = Gate()
        second = Gate()
        self.safe(self.call(first, FRAME, 0), 1)
        self.safe(self.call(second, FRAME, 0), 1)
        # This is a LIMITATION: future helper must implement global quota.

    def test_absence_of_privileged_apis_in_native_source(self):
        source = (ROOT / "build70_cw_checkonly_core.c").read_text()
        for forbidden in ("posix_spawn(", "fork(", "exec(", "system(",
                          "open(", "socket(", "connect(", "getpeereid(",
                          "appinst(", "objc_msgSend(", "installApplication:"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
