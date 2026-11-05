#!/usr/bin/env python3
"""Compile and exercise REAL nonprivileged UNIX socket IPC, two OS processes.

No appinst, IPA, shell invocation from IPC, root helper or device install.
Host CI runtime uses a short private /tmp path to fit sockaddr_un on macOS.
"""
import os
from pathlib import Path
import socket
import stat
import subprocess
import sys
import tempfile
import time
import unittest

SOURCE = Path(__file__).with_name("webreader_helper_probe.c")
SOCKET = "webreader-helper-probe-v1.sock"


class HelperPingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix="wrping-build-", dir="/tmp")
        cls.binary = Path(cls.build.name) / "webreader-helper-probe"
        result = subprocess.run(
            ["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(SOURCE), "-o", str(cls.binary)],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise AssertionError("Host native helper C compiler failed:\n" + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.build.cleanup()

    def setUp(self):
        if os.geteuid() == 0:
            self.skipTest("non-root helper intentionally refuses root: run CI as non-root")
        self.private = tempfile.TemporaryDirectory(prefix="wrping-", dir="/tmp")
        self.addCleanup(self.private.cleanup)
        self.dir = Path(self.private.name)
        self.socket = self.dir / SOCKET

    def cmd(self, operation, directory=None, **kwargs):
        return subprocess.run(
            [str(self.binary), operation, str(directory or self.dir)],
            capture_output=True, text=True, timeout=8, **kwargs
        )

    def server(self):
        process = subprocess.Popen(
            [str(self.binary), "serve", str(self.dir)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.addCleanup(self._kill_if_needed, process)
        for _ in range(150):
            if self.socket.exists():
                return process
            if process.poll() is not None:
                out, err = process.communicate(timeout=1)
                self.fail("probe server terminated before listening: " + err.decode())
            time.sleep(0.01)
        self.fail("server never created private socket")

    @staticmethod
    def _kill_if_needed(process):
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=3)

    def test_real_roundtrip_two_processes_and_single_use(self):
        server = self.server()
        self.assertTrue(stat.S_ISSOCK(self.socket.stat().st_mode))
        self.assertEqual(self.socket.stat().st_mode & 0o777, 0o600)
        p = self.cmd("probe")
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("WEBREADER_PING_OK", p.stdout)
        self.assertIn("NOT authenticated for installation", p.stdout)
        self.assertEqual(server.wait(timeout=4), 0)
        self.assertFalse(self.socket.exists())
        self.assertNotEqual(self.cmd("probe").returncode, 0)

    def test_malformed_request_cannot_become_command(self):
        server = self.server()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2)
            client.connect(str(self.socket))
            client.sendall(b"INSTALL\n")
            client.shutdown(socket.SHUT_WR)
            answer = client.recv(128)
        self.assertEqual(answer, b"")
        self.assertNotEqual(server.wait(timeout=4), 0)
        self.assertFalse(self.socket.exists())

    def test_preexisting_socket_filename_not_removed(self):
        self.socket.write_bytes(b"KEEP ORIGINAL")
        process = self.cmd("serve")
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(self.socket.read_bytes(), b"KEEP ORIGINAL")

    def test_arbitrary_operations_disallowed(self):
        for operation in ["install", "execute", "--shell", "release", "status"]:
            with self.subTest(operation=operation):
                self.assertNotEqual(self.cmd(operation).returncode, 0)

    def test_untrusted_socket_directories_rejected(self):
        self.dir.chmod(0o755)
        self.assertNotEqual(self.cmd("serve").returncode, 0)
        self.assertFalse(self.socket.exists())

    def test_symlink_directory_rejected(self):
        link = self.dir.parent / (self.dir.name + "-link")
        self.addCleanup(lambda: link.unlink(missing_ok=True))
        link.symlink_to(self.dir, target_is_directory=True)
        self.assertNotEqual(self.cmd("serve", directory=link).returncode, 0)
        self.assertFalse(self.socket.exists())

    def test_non_absolute_or_parent_traversal_rejected(self):
        for directory in ["relative/path", "/tmp/../tmp", "/tmp/./foo", "/"]:
            with self.subTest(directory=directory):
                self.assertEqual(self.cmd("serve", directory=directory).returncode, 2)

    def test_client_rejects_spoofed_socket_file(self):
        self.socket.write_bytes(b"not a socket")
        self.assertNotEqual(self.cmd("probe").returncode, 0)

    def test_empty_requests_do_not_get_pong(self):
        server = self.server()
        with socket.socket(socket.AF_UNIX) as client:
            client.settimeout(2)
            client.connect(str(self.socket))
            client.shutdown(socket.SHUT_WR)
            answer = client.recv(128)
            self.assertEqual(answer, b"")
        self.assertNotEqual(server.wait(timeout=4), 0)

    def test_no_appinst_or_shell_command_in_native_helper(self):
        source = SOURCE.read_text()
        for forbidden in ("system(", "execve(", "posix_spawn(", "popen(",
                          "fork(", "LSApplicationWorkspace", "appinst("):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
