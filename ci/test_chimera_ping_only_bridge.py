#!/usr/bin/env python3
"""Standalone external-mobile PING bridge tests; NEVER compile install routines.

Host exercises the exact C one-shot socket protocol without any appinst call.
The built iPhone QA binary uses the same WEBREADER_PING_ONLY mode.
"""
import hmac
import hashlib
import os
import select
from pathlib import Path
import socket
import re
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(__file__).with_name("webreader_appinst_bridge.c")
SOCKET_NAME = "wri.sock"


class PingOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin":
            raise unittest.SkipTest("Darwin UNIX sockets")
        if os.geteuid() == 0:
            raise unittest.SkipTest("Nonroot mobile process only")
        cls.tmp = tempfile.TemporaryDirectory(prefix="wrp-", dir="/tmp")
        cls.root = Path(cls.tmp.name).resolve()
        cls.directory = cls.root / "WR"
        cls.directory.mkdir(mode=0o700)
        cls.binary = cls.root / "ping-only"
        compile_result = subprocess.run(
            ["xcrun", "clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-Wno-deprecated-declarations", "-DWEBREADER_PING_ONLY",
             "-DSOCKET_WAIT_MS=1500",
             str(SOURCE), "-o", str(cls.binary)],
            capture_output=True, text=True, timeout=35
        )
        if compile_result.returncode:
            raise AssertionError("PING-only bridge C compile failed:\n" +
                                 compile_result.stderr)
        # The PING-only executable does not even link to posix_spawn.
        symbols = subprocess.run(["nm", "-u", str(cls.binary)],
                                 capture_output=True, text=True, check=True)
        if "posix_spawn" in symbols.stdout:
            raise AssertionError("PING-only binary must never invoke appinst")
        if b"/usr/bin/appinst" in cls.binary.read_bytes():
            raise AssertionError("PING-only binary contains installer path")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.sock = self.directory / SOCKET_NAME

    def start(self):
        process = subprocess.Popen(
            [str(self.binary), "serve-once", str(self.directory)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop, process)
        for _ in range(100):
            if self.sock.exists():
                return process
            if process.poll() is not None:
                self.fail("Server did not start: " +
                          process.communicate(timeout=2)[1].decode())
            time.sleep(0.02)
        self.fail("No socket created")

    @staticmethod
    def stop(process):
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=2)

    def send(self, payload):
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(3)
            client.connect(str(self.sock))
            client.sendall(payload)
            return client.recv(8)

    def test_read_only_ping_and_socket_removed(self):
        process = self.start()
        self.assertEqual(self.send(b"WRPING1\n"), b"WRPONG1\n")
        self.assertEqual(process.wait(timeout=3), 0)
        stdout, stderr = process.communicate(timeout=2)
        self.assertIn(b"WRAPPINST_READY", stdout)
        self.assertIn(b"WRDIAG: ACCEPTED_CONNECTION", stderr)
        self.assertIn(b"WRDIAG: PEER_ACCEPTED: same UID", stderr)
        self.assertIn(b"WRDIAG: PING matched; PONG send OK", stderr)
        self.assertIn(b"WRDIAG: REQUEST_FINISHED: result=0", stderr)
        self.assertFalse(self.sock.exists())

    def test_install_request_rejected_without_executing_anything(self):
        process = self.start()
        self.assertEqual(self.send(b"WRINST1\n"), b"WRFAIL1\n")
        self.assertNotEqual(process.wait(timeout=3), 0)
        _, stderr = process.communicate(timeout=2)
        self.assertIn(b"WRDIAG: request header not PING", stderr)
        self.assertFalse(self.sock.exists())

    def test_no_connection_times_out_with_unambiguous_log(self):
        process = self.start()
        self.assertNotEqual(process.wait(timeout=4), 0)
        _, stderr = process.communicate(timeout=2)
        self.assertIn(b"WRDIAG: NO_CONNECTION", stderr)
        self.assertFalse(self.sock.exists())

    def start_loopback(self):
        process = subprocess.Popen(
            [str(self.binary), "serve-loopback-once"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop, process)
        readable, _, _ = select.select([process.stdout], [], [], 2)
        if not readable:
            self.fail("Loopback helper never reported READY")
        ready = process.stdout.readline()
        self.assertIn(b"WRLOOPBACK_READY", ready)
        return process

    def test_loopback_ping_only_listens_on_127_0_0_1(self):
        process = self.start_loopback()
        with socket.create_connection(("127.0.0.1", 38971), timeout=2) as client:
            self.assertEqual(client.getpeername()[0], "127.0.0.1")
            client.sendall(b"WRPING1\n")
            self.assertEqual(client.recv(8), b"WRPONG1\n")
        self.assertEqual(process.wait(timeout=3), 0)
        _, stderr = process.communicate(timeout=2)
        self.assertIn(b"WRDIAG: LOOPBACK_ACCEPTED_127_0_0_1", stderr)
        self.assertIn(b"WRDIAG: PING matched; PONG send OK", stderr)
        self.assertIn(b"WRDIAG: LOOPBACK_REQUEST_FINISHED result=0", stderr)

    def test_loopback_refuses_install_header(self):
        process = self.start_loopback()
        with socket.create_connection(("127.0.0.1", 38971), timeout=2) as client:
            client.sendall(b"WRINST1\n")
            self.assertEqual(client.recv(8), b"WRFAIL1\n")
        self.assertNotEqual(process.wait(timeout=3), 0)
        _, stderr = process.communicate(timeout=2)
        self.assertIn(b"WRDIAG: request header not PING", stderr)

    def start_pair(self):
        process = subprocess.Popen(
            [str(self.binary), "serve-pair-once"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.addCleanup(self.stop, process)
        readable, _, _ = select.select([process.stdout], [], [], 2)
        self.assertTrue(readable, "Pair helper did not start")
        self.assertIn(b"WRPAIR_READY", process.stdout.readline())
        line = process.stdout.readline()
        self.assertTrue(re.fullmatch(rb"WRPAIR_CODE: [0-9A-F]{16}\\n", line))
        return process, line.split(b": ", 1)[1].strip()

    def pair_request(self, code, use_wrong_key=False):
        with socket.create_connection(("127.0.0.1", 38972), timeout=2) as client:
            client.settimeout(3)
            client.sendall(b"WRPAIR1\\n")
            challenge = self.recv_exact(client, 24)
            self.assertEqual(challenge[:8], b"WRCHAL1\\n")
            nonce = challenge[8:]
            key = b"AAAAAAAAAAAAAAAA" if use_wrong_key else code
            proof = hmac.new(key, b"WR-PAIR-CLIENT-V1" + nonce,
                             hashlib.sha256).digest()
            client.sendall(b"WRAUTH1\\n" + proof)
            response = self.recv_exact(client, 8)
            if response == b"WROKAY1\\n":
                signed = self.recv_exact(client, 32)
                expected = hmac.new(key, b"WR-PAIR-SERVER-V1" + nonce,
                                    hashlib.sha256).digest()
                self.assertEqual(signed, expected)
            return response

    @staticmethod
    def recv_exact(sock, length):
        buf = b""
        while len(buf) < length:
            more = sock.recv(length - len(buf))
            if not more:
                raise AssertionError("Unexpected server shutdown")
            buf += more
        return buf

    def test_pair_code_proof_and_server_proof_one_time(self):
        process, code = self.start_pair()
        self.assertEqual(self.pair_request(code), b"WROKAY1\\n")
        self.assertEqual(process.wait(timeout=3), 0)
        self.assertFalse(b"/usr/bin/appinst" in self.binary.read_bytes())
        _, stderr = process.communicate(timeout=2)
        self.assertIn(b"PAIR_PROOF_ACCEPTED", stderr)
        with self.assertRaises(OSError):
            socket.create_connection(("127.0.0.1", 38972), timeout=1)

    def test_wrong_pair_code_denied_and_consumed(self):
        process, code = self.start_pair()
        self.assertEqual(self.pair_request(code, use_wrong_key=True),
                         b"WRDENY1\\n")
        self.assertNotEqual(process.wait(timeout=3), 0)
        _, stderr = process.communicate(timeout=2)
        self.assertIn(b"PAIR_DENIED", stderr)

    def test_install_opcode_rejected_on_pairing_port(self):
        process, _ = self.start_pair()
        with socket.create_connection(("127.0.0.1", 38972), timeout=2) as client:
            client.sendall(b"WRINST1\\n")
        self.assertNotEqual(process.wait(timeout=3), 0)
        _, stderr = process.communicate(timeout=2)
        self.assertIn(b"PAIR_REJECTED_BAD_REQUEST", stderr)

    def test_cli_cannot_install_even_with_install_confirmed_flag(self):
        process = subprocess.run(
            [str(self.binary), "install-confirmed",
             "/does/not/exist.ipa", "0" * 64, "I-CONFIRM-INSTALL"],
            capture_output=True, text=True, timeout=3
        )
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("PING only", process.stderr)

    def test_selftest_without_appinst_lookup(self):
        process = subprocess.run(
            [str(self.binary), "selftest"],
            capture_output=True, text=True, timeout=3
        )
        self.assertEqual(process.returncode, 0)
        self.assertIn("WEBREADER_PING_ONLY", process.stdout)
        self.assertNotIn("APPINST_PATH_PRESENT", process.stdout)


if __name__ == "__main__":
    unittest.main()
