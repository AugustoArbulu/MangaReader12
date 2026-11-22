#!/usr/bin/env python3
"""Phase CY: REAL macOS Swift -> standalone CX C transport, no installer.

All clients run as unprivileged macOS programs. The iOS application is
not installed; the helper is a disposable host executable. WRNOTE2 is
only an untrusted check notice, never a release or install permission.
"""
import contextlib
import os
from pathlib import Path
import re
import select
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CORE = ROOT / "MangaReader12/Core"
CX_C = HERE / "webreader_chimera_checkonly_service.c"
POLICY_C = HERE / "build70_cw_checkonly_core.c"
DISPATCH_C = HERE / "build70_cw_shared_dispatch.c"

SWIFT_HARNESS = r'''
import Foundation
@main struct CheckOnlyHarness {
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 2,
              let port = UInt16(args[1]),
              port > 0
        else { exit(90) }
        let outcome = WebReaderAppinstSocket.hostCheckOnlyProbe(port: port)
        print(outcome.text)
        switch outcome {
        case .noticeAccepted: exit(0)
        case .rateLimited: exit(2)
        case .denied: exit(3)
        case .unavailable: exit(4)
        case .protocolRejected: exit(5)
        case .transportFailure: exit(6)
        }
    }
}
'''


class NativeWebReaderCheckOnlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin":
            raise unittest.SkipTest("Swift/Darwin host integration requires macOS")
        if os.geteuid() == 0:
            raise unittest.SkipTest("Do not use a root runner for this laboratory")
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr-cy-swift-client-")
        cls.root = Path(cls.tmp.name)
        cls.client = cls.root / "swift-checkonly"
        cls.server = cls.root / "c-checkonly"
        main = cls.root / "main.swift"
        main.write_text(SWIFT_HARNESS, encoding="utf-8")

        build_commands = [
            ["xcrun", "swiftc", "-parse-as-library", "-D", "WEBREADER_HOST_TEST",
             str(CORE / "WebReaderHelperPingProbe.swift"),
             str(CORE / "WebReaderAppinstSocket.swift"),
             str(main), "-o", str(cls.client)],
            ["xcrun", "clang", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror",
             "-pthread", "-DWR_CX_HOST_TEST_PORT=0",
             str(CX_C), str(POLICY_C), str(DISPATCH_C), "-o", str(cls.server)],
        ]
        for cmd in build_commands:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if result.returncode != 0:
                raise AssertionError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.process = subprocess.Popen(
            [str(self.server), "serve"], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, bufsize=1,
        )
        readable, _, _ = select.select([self.process.stdout], [], [], 5)
        self.assertTrue(readable, "C service did not print a ready port")
        line = self.process.stdout.readline().strip()
        match = re.fullmatch(r"WR_CX_HOST_PORT=([1-9][0-9]{1,4})", line)
        self.assertIsNotNone(match, line)
        self.port = int(match.group(1))
        self.assertLessEqual(self.port, 65535)

    def tearDown(self):
        if self.process.poll() is None:
            self.process.terminate()
        try:
            self.process.communicate(timeout=4)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.communicate(timeout=4)

    def client_result(self, port):
        return subprocess.run([str(self.client), str(port)],
                              capture_output=True, text=True, timeout=8)

    def test_swift_to_real_c_notice_and_rate_limit(self):
        first = self.client_result(self.port)
        self.assertEqual(first.returncode, 0, first.stderr + first.stdout)
        self.assertIn("Aviso local aceito", first.stdout)
        self.assertIn("NÃO consultada", first.stdout)
        second = self.client_result(self.port)
        self.assertEqual(second.returncode, 2, second.stderr + second.stdout)
        self.assertIn("limitado", second.stdout)
        self.assertIsNone(self.process.poll())

    def test_missing_helper_is_reported_without_install_claim(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            spare_port = s.getsockname()[1]
        result = self.client_result(spare_port)
        self.assertEqual(result.returncode, 4, result.stderr + result.stdout)
        self.assertIn("indisponível", result.stdout)
        self.assertIn("nenhuma instalação", result.stdout)

    @contextlib.contextmanager
    def fake_server(self, reply):
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            port = listener.getsockname()[1]
            received = []
            def respond():
                with listener.accept()[0] as connection:
                    connection.settimeout(5)
                    chunks = b""
                    while True:
                        fragment = connection.recv(16)
                        if not fragment:
                            break
                        chunks += fragment
                    received.append(chunks)
                    if reply is not None:
                        connection.sendall(reply)
            thread = threading.Thread(target=respond, daemon=True)
            thread.start()
            try:
                yield port, received
            finally:
                thread.join(timeout=6)
                if thread.is_alive():
                    raise AssertionError("Fake server did not finish")

    def test_sent_frame_is_exact_and_has_halfclose(self):
        with self.fake_server(b"WRDENY2\n") as (port, received):
            result = self.client_result(port)
        self.assertEqual(received, [b"WRCHK2\n"])
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("rejeitou", result.stdout)

    def test_fake_or_extra_response_is_never_update_authority(self):
        for reply in (b"WRDONE1\n", b"WRNOTE2\nINSTALL",
                      b"WRNOTE2\nx", b"WRNOTE2", b"WRNOTE2\r\n", b"",
                      b"WRRATE2\nextra"):
            with self.subTest(reply=reply):
                with self.fake_server(reply) as (port, received):
                    result = self.client_result(port)
                self.assertEqual(received, [b"WRCHK2\n"])
                self.assertEqual(result.returncode, 5,
                                 result.stderr + result.stdout)
                self.assertIn("nenhuma instalação", result.stdout)

    def test_fake_valid_notice_has_explicit_no_install_semantics(self):
        with self.fake_server(b"WRNOTE2\n") as (port, received):
            result = self.client_result(port)
        self.assertEqual(received, [b"WRCHK2\n"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("IPA NÃO instalada", result.stdout)

    def test_static_production_boundaries(self):
        swift = (CORE / "WebReaderAppinstSocket.swift").read_text()
        self.assertIn("static let liveInstallationEnabled = false", swift)
        self.assertIn("static func checkOnlyConnection(", swift)
        self.assertIn("checkOnlyExchange(port: 38973)", swift)
        self.assertIn('Array("WRCHK2\\n".utf8)', swift)
        self.assertIn("Darwin.shutdown(fd, SHUT_WR)", swift)
        self.assertIn("private static func checkOnlyExchange", swift)
        self.assertIn("#if WEBREADER_HOST_TEST", swift)
        section = swift.split("private static func checkOnlyExchange", 1)[1].split(
            "// Build62 security gate:", 1)[0]
        for forbidden in ("posix_spawn(", "system(", "WRINST1", "appinst(",
                          "ipaURL", "expectedSHA256", "installApplication:"):
            self.assertNotIn(forbidden, section)


if __name__ == "__main__":
    unittest.main()
