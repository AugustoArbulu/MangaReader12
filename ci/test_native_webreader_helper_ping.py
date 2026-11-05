#!/usr/bin/env python3
"""Exercise the REAL WebReader Swift IPC probe against a separate C process.

Runs on a non-root macOS host with Darwin/Foundation, no phone or jailbreak.
No command execution via IPC, no IPA download, no installer or privileged work.
The normal Xcode project build compiles the same Swift code for iOS 12.
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

HERE = Path(__file__).resolve().parent
SWIFT_SOURCE = HERE.parent / "MangaReader12/Core/WebReaderHelperPingProbe.swift"
C_SOURCE = HERE / "webreader_helper_probe.c"

HARNESS = r'''
import Foundation
import Darwin
@main struct PingHarness {
    static func main() {
        guard CommandLine.arguments.count == 2 else { exit(99) }
        let directory = URL(
            fileURLWithPath: CommandLine.arguments[1], isDirectory: true
        )
        let result = WebReaderHelperPingProbe.inspect(directory: directory)
        print(result.report)
        switch result {
        case .responded: exit(0)
        case .unavailable: exit(3)
        case .unsafePath: exit(4)
        case .rejected: exit(5)
        }
    }
}
'''

class SwiftAgainstNativeHelperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin":
            raise unittest.SkipTest("This test compiles Darwin Swift on macOS CI")
        cls.binary_dir = tempfile.TemporaryDirectory(prefix="wr-swift-", dir="/tmp")
        directory = Path(cls.binary_dir.name)
        cls.cpp = directory / "wr-helper"
        cls.swift = directory / "wr-native-client"
        harness = directory / "main.swift"
        harness.write_text(HARNESS)
        for command in [
            ["xcrun", "clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
             str(C_SOURCE), "-o", str(cls.cpp)],
            ["xcrun", "swiftc", "-parse-as-library", str(SWIFT_SOURCE),
             str(harness), "-o", str(cls.swift)],
        ]:
            result = subprocess.run(command, text=True, capture_output=True, timeout=45)
            if result.returncode:
                raise AssertionError(
                    "Native ping test failed to compile:\n"
                    + " ".join(command) + "\n" + result.stderr
                )

    @classmethod
    def tearDownClass(cls):
        cls.binary_dir.cleanup()

    def setUp(self):
        if os.geteuid() == 0:
            self.skipTest("diagnostic helper is intentionally never root")
        self.temp = tempfile.TemporaryDirectory(prefix="wr-peer-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.sock = self.folder / "wrp.sock"

    def test_absent_helper_fails_closed(self):
        r = subprocess.run([str(self.swift), str(self.folder)],
                           capture_output=True, text=True, timeout=8)
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)
        self.assertIn("não encontrado", r.stdout)
        self.assertFalse(self.sock.exists())

    def test_swift_client_really_talks_to_separate_native_helper(self):
        server = subprocess.Popen(
            [str(self.cpp), "serve", str(self.folder)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            for _ in range(150):
                if self.sock.exists(): break
                if server.poll() is not None:
                    self.fail("C helper exited early: " + server.communicate()[1].decode())
                time.sleep(0.01)
            else:
                self.fail("C helper never opened socket")
            self.assertEqual(self.sock.stat().st_mode & 0o777, 0o600)
            result = subprocess.run([str(self.swift), str(self.folder)],
                                    capture_output=True, text=True, timeout=8)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("PONG recebido", result.stdout)
            self.assertIn("NÃO autenticado", result.stdout)
            self.assertEqual(server.wait(timeout=4), 0)
            self.assertFalse(self.sock.exists())
        finally:
            if server.poll() is None:
                server.kill()
                server.communicate(timeout=3)

    def test_non_socket_rejected_without_execution(self):
        self.sock.write_bytes(b"NOT-HELPER")
        r = subprocess.run([str(self.swift), str(self.folder)],
                           capture_output=True, text=True, timeout=8)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertEqual(self.sock.read_bytes(), b"NOT-HELPER")


if __name__ == "__main__":
    unittest.main()
