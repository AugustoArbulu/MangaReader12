#!/usr/bin/env python3
"""Phase CX: end-to-end unprivileged localhost transport tests.

A receiving WRNOTE2 is NEVER a release check, update/installation
authorization, or evidence of successful AppInst invocation. CI uses
temporary executables; no iOS device or user files are touched.
"""
from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import re
import select
import shutil
import socket
import subprocess
import tempfile
import time
import unittest

SRC = Path(__file__).resolve().parent
SERVER = SRC / "webreader_chimera_checkonly_service.c"
CORE = SRC / "build70_cw_checkonly_core.c"
DISPATCH = SRC / "build70_cw_shared_dispatch.c"
FRAME = b"WRCHK2\n"
ACK = b"WRNOTE2\n"
RATE = b"WRRATE2\n"
DENY = b"WRDENY2\n"


class ChimeraCheckOnlyServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.geteuid() == 0:
            raise unittest.SkipTest("Lab intentionally refuses root, including in tests")
        cls.temp = tempfile.TemporaryDirectory(prefix="wr-cx-checkonly-")
        cls.binary = Path(cls.temp.name) / "checkonly-service"
        cc = shutil.which("clang") or shutil.which("cc")
        if cc is None:
            raise RuntimeError("C compiler not available")
        result = subprocess.run([
            cc, "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
            "-pthread", "-DWR_CX_HOST_TEST_PORT=0",
            str(SERVER), str(CORE), str(DISPATCH),
            "-o", str(cls.binary),
        ], capture_output=True, text=True, timeout=30)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        result = subprocess.run([str(cls.binary), "selftest"],
                                capture_output=True, text=True, timeout=4)
        if result.returncode or "WR_CX_NO_IPA_NO_APPINST_NO_INSTALL" not in result.stdout:
            raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.server = subprocess.Popen(
            [str(self.binary), "serve"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        readable, _, _ = select.select([self.server.stdout], [], [], 5)
        if not readable or self.server.poll() is not None:
            self.server.kill()
            self.server.communicate(timeout=5)
            self.fail("Check-only service failed to start")
        first = self.server.stdout.readline().strip()
        match = re.fullmatch(r"WR_CX_HOST_PORT=([1-9][0-9]{1,4})", first)
        self.assertIsNotNone(match, first)
        self.port = int(match.group(1))
        self.assertLessEqual(self.port, 65535)

    def tearDown(self):
        if self.server.poll() is None:
            self.server.terminate()
        try:
            self.server.communicate(timeout=4)
        except subprocess.TimeoutExpired:
            self.server.kill()
            self.server.communicate(timeout=4)

    def exchange(self, frame, fragments=False, close_write=True):
        with socket.create_connection(("127.0.0.1", self.port), 2) as client:
            client.settimeout(3.5)
            if fragments:
                for b in frame:
                    client.sendall(bytes([b]))
                    time.sleep(0.003)
            else:
                client.sendall(frame)
            if close_write:
                client.shutdown(socket.SHUT_WR)
            data = b""
            while len(data) < 8:
                try:
                    block = client.recv(8 - len(data))
                except (ConnectionResetError, BrokenPipeError, socket.timeout):
                    break
                if not block:
                    break
                data += block
            return data

    def test_only_one_notice_per_running_helper(self):
        self.assertEqual(self.exchange(FRAME), ACK)
        for _ in range(12):
            self.assertEqual(self.exchange(FRAME), RATE)
        self.assertIsNone(self.server.poll())

    def test_fragmentation_and_eof_are_supported(self):
        self.assertEqual(self.exchange(FRAME, fragments=True), ACK)
        self.assertEqual(self.exchange(FRAME, fragments=True), RATE)

    def test_valid_prefix_then_more_bytes_rejected_without_spending_quota(self):
        for payload in (FRAME + b"x", FRAME + b"INSTALL",
                        FRAME + b"\x00", FRAME + b"../", FRAME * 2):
            with self.subTest(payload=payload):
                self.assertEqual(self.exchange(payload), DENY)
        self.assertEqual(self.exchange(FRAME), ACK)

    def test_attacker_commands_never_trigger_notice_or_install(self):
        for payload in (b"WRINST1\n", b"WRPING1\n", b"WRPAIR1\n",
                        b"WRCHK2", b"WRCHK3\n", b"\x00" + FRAME,
                        b"INSTALL\n", b"/tmp/ipa", b"WRCHK2\r\n",
                        b" " * 4096, b""):
            with self.subTest(payload=payload):
                self.assertEqual(self.exchange(payload), DENY)
        self.assertEqual(self.exchange(FRAME), ACK)

    def test_many_untrusted_clients_share_one_global_process_gate(self):
        with ThreadPoolExecutor(max_workers=16) as pool:
            responses = list(pool.map(self.exchange, [FRAME] * 32))
        self.assertEqual(responses.count(ACK), 1)
        self.assertEqual(responses.count(RATE), 31)
        self.assertEqual(responses.count(DENY), 0)

    def test_half_close_required_before_accepting_frame(self):
        with socket.create_connection(("127.0.0.1", self.port), 2) as client:
            client.settimeout(.15)
            client.sendall(FRAME)
            with self.assertRaises(socket.timeout):
                client.recv(8)
            client.shutdown(socket.SHUT_WR)
            self.assertEqual(client.recv(8), ACK)

    def test_idle_client_bounded_by_timeout(self):
        # A client that sends a valid prefix but never half-closes must not
        # be rewarded with a notice. The service remains usable afterwards.
        self.assertEqual(self.exchange(FRAME, close_write=False), b"")
        self.assertEqual(self.exchange(FRAME), ACK)

    def test_restarted_helper_has_no_persistent_install_permission(self):
        self.assertEqual(self.exchange(FRAME), ACK)
        # RunAtLoad/daemon persistence is NOT tested here; this is only
        # a restarted host process with an in-memory quota.
        self.tearDown()
        self.setUp()
        self.assertEqual(self.exchange(FRAME), ACK)

    def test_static_security_gate(self):
        source = SERVER.read_text()
        assert "htonl(INADDR_LOOPBACK)" in source
        assert 'WR_CX_PORT 38973' in source
        assert "geteuid() == 0" in source
        assert "getuid() == 501 && geteuid() == 501" in source
        assert "WR_CW_FRAME_BYTES + 1" in source
        assert "if (got == 0)" in source
        assert "WR_CW_CHECK_NOTICE_ACCEPTED" in source
        assert "caller_authenticated" in source
        assert "installer_authorized" in source
        assert "installation_performed" in source
        assert "WRNOTE2\\n" in source
        assert "WRRATE2\\n" in source
        assert "WRDENY2\\n" in source
        for forbidden in (
            "posix_spawn(", "fork(", "execve(", "system(", "popen(",
            "installApplication:", "objc_msgSend(", "chmod(", "chown(",
            "unlink(", "remove(", "rename(", "open(", "fopen(",
            "curl ", "https://", "appinst(", "WRINST1\\n\"",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)
        # Still explicitly fails closed in the actual iOS update client.
        wr = (SRC.parent / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
        self.assertIn("static let liveInstallationEnabled = false", wr)
        self.assertIn("DispatchQueue.main.async { completion(.rejected) }", wr)


if __name__ == "__main__":
    unittest.main()
