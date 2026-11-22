#!/usr/bin/env python3
"""Build61 persistent loopback PING protocol; host only, no appinst."""
from pathlib import Path
import os
import select
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "ci/webreader_chimera_persistent_ping.c"


class PersistentPingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.geteuid() == 0:
            raise unittest.SkipTest("Persistent ping service refuses root")
        cls.temp = tempfile.TemporaryDirectory(prefix="wr-ping61-")
        cls.executable = Path(cls.temp.name) / "server"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            cls.port = sock.getsockname()[1]
        compiler = shutil.which("clang") or shutil.which("cc")
        assert compiler, "CI compiler missing"
        result = subprocess.run([
            compiler, "-std=c11", "-Wall", "-Wextra", "-Werror",
            "-O2", "-DWRP_TEST_PORT=" + str(cls.port),
            str(SRC), "-o", str(cls.executable)
        ], capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, result.stdout + result.stderr
        assert b"/usr/bin/appinst" not in cls.executable.read_bytes()
        cls.start_server()

    @classmethod
    def start_server(cls):
        cls.server = subprocess.Popen(
            [str(cls.executable), "serve"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        # Attempt a connection until the listener is ready. Never block on
        # readline, which can hang if the process exits before logging.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if cls.server.poll() is not None:
                raise AssertionError("PING service exited early: " +
                                     cls.server.stderr.read())
            try:
                with socket.create_connection(("127.0.0.1", cls.port), 0.15):
                    return
            except OSError:
                time.sleep(0.025)
        raise AssertionError("PING service not ready on loopback")

    @classmethod
    def stop_server(cls):
        if cls.server.poll() is None:
            cls.server.terminate()
        try:
            cls.server.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            cls.server.kill()
            cls.server.communicate(timeout=5)

    @classmethod
    def tearDownClass(cls):
        cls.stop_server()
        cls.temp.cleanup()

    def exchange(self, request, fragments=False):
        with socket.create_connection(("127.0.0.1", self.port), 2) as client:
            client.settimeout(3)
            if fragments:
                for byte in request:
                    client.sendall(bytes([byte]))
                    time.sleep(0.005)
            else:
                client.sendall(request)
            try:
                return client.recv(64)
            except (ConnectionResetError, BrokenPipeError):
                return b""

    def test_many_pings_on_same_service(self):
        for i in range(15):
            with self.subTest(index=i):
                self.assertEqual(self.exchange(b"WRPING1\n"), b"WRPONG1\n")
        self.assertIsNone(self.server.poll())

    def test_fragmented_ping(self):
        self.assertEqual(
            self.exchange(b"WRPING1\n", fragments=True),
            b"WRPONG1\n"
        )

    def test_reject_installer_and_other_requests(self):
        for payload in [
            b"WRINST1\n", b"INSTALL\n", b"WRPAIR1\n",
            b"WRPING1\nextra", b"WRPING1", b"WRPING0\n",
            b"WRPING1\x00", b"../invalid", b"x" * 70
        ]:
            with self.subTest(payload=payload):
                self.assertEqual(self.exchange(payload), b"")
        self.assertEqual(self.exchange(b"WRPING1\n"), b"WRPONG1\n")

    def test_selftest_does_not_touch_network_or_install(self):
        result = subprocess.run(
            [str(self.executable), "selftest"],
            capture_output=True, text=True, timeout=4
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("NO_APPINST_NO_IPA_NO_INSTALL", result.stdout)
        for disallowed in ("install", "inspect", "serve-appinst"):
            with self.subTest(disallowed=disallowed):
                code = subprocess.run(
                    [str(self.executable), disallowed],
                    capture_output=True, text=True, timeout=4
                )
                self.assertNotEqual(code.returncode, 0)

    def test_restart_does_not_require_app_install(self):
        self.stop_server()
        self.start_server()
        self.assertEqual(self.exchange(b"WRPING1\n"), b"WRPONG1\n")


if __name__ == "__main__":
    unittest.main()
