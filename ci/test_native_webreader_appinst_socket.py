#!/usr/bin/env python3
"""Real macOS Swift -> native C appinst socket integration with FAKE installer.

This suite uses a synthetic/non-installable IPA and an executable fake appinst.
It exercises the exact Swift client used by the iOS12 app, never a jailbreak
service, real /usr/bin/appinst or an actual application installation.
"""
import hashlib
import os
import select
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
CORE = HERE.parent / "MangaReader12" / "Core"
BRIDGE_C = HERE / "webreader_appinst_bridge.c"
CONTAINER = "12345678-1234-4ABC-9DEF-1234567890AB"
LEAF = "WebReader-build57-12345678-1234-4ABC-9DEF-1234567890AB.ipa"
PAYLOAD = b"PK\x03\x04" + b"FAKE_NON_INSTALLABLE_IPA" * 7000
SWIFT_HARNESS = r'''
import Foundation
@main struct BridgeClientHarness {
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 3 || args.count == 5 else { exit(90) }
        let directory = URL(fileURLWithPath: args[2], isDirectory: true)
        let result: WebReaderAppinstSocket.Result
        if args[1] == "ping" && args.count == 3 {
            result = WebReaderAppinstSocket.hostProbe(directory: directory)
        } else if args[1] == "loopback" && args.count == 3 {
            result = WebReaderAppinstSocket.hostLoopbackProbe()
        } else if args[1] == "pair" && args.count == 3 {
            result = WebReaderAppinstSocket.hostPairProbe(code: args[2])
        } else if args[1] == "install" && args.count == 5 {
            result = WebReaderAppinstSocket.hostInstall(
                directory: directory,
                ipaURL: URL(fileURLWithPath: args[3]),
                sha256: args[4]
            )
        } else {
            exit(91)
        }
        print(result.text)
        switch result {
        case .diagnosticReady: exit(0)
        case .pairingAccepted: exit(0)
        case .pairingDenied: exit(6)
        case .completed: exit(0)
        case .unavailable: exit(3)
        case .rejected: exit(4)
        case .diagnosticFailure: exit(4)
        case .failed: exit(5)
        }
    }
}
'''


class NativeSocketIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if sys.platform != "darwin":
            raise unittest.SkipTest("macOS only: requires Darwin and CommonCrypto")
        if os.geteuid() == 0:
            raise unittest.SkipTest("mobile helper must never be root")
        cls.working = tempfile.TemporaryDirectory(prefix="wr-install-ipc-", dir="/tmp")
        cls.root = Path(cls.working.name).resolve()
        cls.server = cls.root / "appinst-bridge-fake"
        cls.loopback_helper = cls.root / "loopback-ping-only"
        cls.client = cls.root / "swift-client"
        cls.fake = cls.root / "fake-appinst.sh"
        cls.fake.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"$#\" \"$1\" > \"$WEBREADER_FAKE_INSTALL_LOG\"\n"
            "exit \"$WEBREADER_FAKE_INSTALL_STATUS\"\n"
        )
        cls.fake.chmod(0o700)
        harness = cls.root / "main.swift"
        harness.write_text(SWIFT_HARNESS)
        commands = [
            ["xcrun", "clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-Wno-deprecated-declarations",
             # Activate FAKE mode only in this synthetic macOS test binary.
             # The production server must continue to refuse WRINST1.
             "-DWEBREADER_FAKE_APPINST_QA",
             '-DWEBREADER_TEST_ROOT="' + str(cls.root) + '"',
             '-DWEBREADER_TEST_APPINST="' + str(cls.fake) + '"',
             str(BRIDGE_C), "-o", str(cls.server)],
            ["xcrun", "clang", "-std=c11", "-Wall", "-Wextra", "-Werror",
             "-Wno-deprecated-declarations", "-DWEBREADER_PING_ONLY",
             "-DSOCKET_WAIT_MS=3000", str(BRIDGE_C),
             "-o", str(cls.loopback_helper)],
            ["xcrun", "swiftc", "-parse-as-library",
             "-D", "WEBREADER_HOST_TEST",
             str(CORE / "WebReaderHelperPingProbe.swift"),
             str(CORE / "WebReaderAppinstSocket.swift"),
             str(harness), "-o", str(cls.client)]
        ]
        for cmd in commands:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=50)
            if result.returncode:
                raise AssertionError("Native IPC compile failure:\n" +
                                     " ".join(cmd) + "\n" + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.working.cleanup()

    def setUp(self):
        self.folder = self.root / CONTAINER
        self.socket_dir = self.folder / "WR"
        self.socket_dir.mkdir(parents=True, exist_ok=True)
        self.socket_dir.chmod(0o700)
        self.staging = self.folder / "Library" / "Application Support" / "WebReaderUpdates"
        self.staging.mkdir(parents=True, exist_ok=True)
        self.file = self.staging / LEAF
        self.file.write_bytes(PAYLOAD)
        self.file.chmod(0o600)
        self.sha = hashlib.sha256(PAYLOAD).hexdigest()
        self.marker = self.root / "invoked-appinst.txt"
        self.marker.unlink(missing_ok=True)
        self.addCleanup(lambda: self.file.unlink(missing_ok=True))

    def _environment(self, status="0"):
        env = os.environ.copy()
        env["WEBREADER_FAKE_INSTALL_LOG"] = str(self.marker)
        env["WEBREADER_FAKE_INSTALL_STATUS"] = status
        return env

    def _server(self, status="0"):
        proc = subprocess.Popen(
            [str(self.server), "serve-once", str(self.socket_dir)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            env=self._environment(status)
        )
        self.addCleanup(self._stop_server, proc)
        socket_path = self.socket_dir / "wri.sock"
        for _ in range(160):
            if socket_path.exists():
                self.assertIn(b"WRAPPINST_READY", proc.stdout.readline())
                return proc
            if proc.poll() is not None:
                self.fail("server exited before listening: " +
                          proc.communicate(timeout=1)[1].decode())
            time.sleep(0.01)
        self.fail("bridge never started UNIX socket")

    @staticmethod
    def _stop_server(proc):
        if proc.poll() is None:
            proc.kill()
            proc.communicate(timeout=3)

    def run_client(self, operation, *params):
        return subprocess.run(
            [str(self.client), operation, str(self.socket_dir), *map(str, params)],
            capture_output=True, text=True, timeout=15
        )

    def test_host_fake_mode_never_applies_to_real_ios_target(self):
        # The fake install branch is enabled only by this test compiler
        # invocation, never by an app build or iOS helper workflow.
        script = Path(__file__).read_text()
        self.assertIn('"-DWEBREADER_FAKE_APPINST_QA",', script)
        bridge = BRIDGE_C.read_text()
        self.assertIn("#ifndef WEBREADER_FAKE_APPINST_QA", bridge)
        self.assertIn("#ifdef WEBREADER_FAKE_APPINST_QA", bridge)
        self.assertIn("Fake appinst QA requires BOTH", bridge)
        project = (HERE.parent / "MangaReader12.xcodeproj" /
                   "project.pbxproj").read_text()
        self.assertNotIn("WEBREADER_FAKE_APPINST_QA", project)
        workflow = (HERE.parent / ".github/workflows" /
                    "chimera-mobile-ping.yml").read_text()
        self.assertNotIn("WEBREADER_FAKE_APPINST_QA", workflow)

    def test_swift_app_client_installs_only_fake_verified_archive(self):
        server = self._server()
        result = self.run_client("install", self.file, self.sha)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("sucesso", result.stdout)
        self.assertEqual(server.wait(timeout=4), 0)
        self.assertEqual(self.marker.read_text().splitlines(), ["1", str(self.file)])
        self.assertFalse((self.socket_dir / "wri.sock").exists())

    def test_read_only_swift_ping_never_invokes_appinst(self):
        server = self._server()
        result = self.run_client("ping")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PONG", result.stdout)
        self.assertEqual(server.wait(timeout=4), 0)
        self.assertFalse(self.marker.exists())

    def test_ping_rejects_non_socket_with_specific_stage(self):
        fake = self.socket_dir / "wri.sock"
        fake.write_text("not a socket")
        try:
            result = self.run_client("ping")
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertIn("wri.sock não é socket", result.stdout)
            self.assertFalse(self.marker.exists())
        finally:
            fake.unlink(missing_ok=True)

    def test_ping_rejects_unsafe_directory_with_specific_stage(self):
        self.socket_dir.chmod(0o777)
        try:
            result = self.run_client("ping")
            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertIn("permissões WR não são privadas", result.stdout)
            self.assertFalse(self.marker.exists())
        finally:
            self.socket_dir.chmod(0o700)

    def test_ping_without_server_preserves_unavailable(self):
        result = self.run_client("ping")
        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("não está em execução", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_swift_localhost_ping_never_uses_appinst(self):
        helper = subprocess.Popen(
            [str(self.loopback_helper), "serve-loopback-once"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.addCleanup(self._stop_server, helper)
        ready, _, _ = select.select([helper.stdout], [], [], 2)
        self.assertTrue(ready, "loopback helper did not start")
        self.assertIn(b"WRLOOPBACK_READY", helper.stdout.readline())
        result = self.run_client("loopback")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PONG", result.stdout)
        self.assertEqual(helper.wait(timeout=4), 0)
        self.assertFalse(self.marker.exists())

    def _start_pair_helper(self):
        helper = subprocess.Popen(
            [str(self.loopback_helper), "serve-pair-once"],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        self.addCleanup(self._stop_server, helper)
        ready, _, _ = select.select([helper.stdout], [], [], 2)
        self.assertTrue(ready, "pair helper did not start")
        self.assertIn(b"WRPAIR_READY", helper.stdout.readline())
        line = helper.stdout.readline().decode().strip()
        self.assertTrue(line.startswith("WRPAIR_CODE: "))
        code = line.split(": ", 1)[1]
        self.assertEqual(len(code), 16)
        self.assertTrue(all(c in "0123456789ABCDEF" for c in code))
        return helper, code

    def test_swift_pair_correct_code_and_mutual_proof(self):
        helper, code = self._start_pair_helper()
        result = subprocess.run(
            [str(self.client), "pair", code],
            capture_output=True, text=True, timeout=15
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("temporário validado", result.stdout)
        self.assertEqual(helper.wait(timeout=4), 0)
        self.assertFalse(self.marker.exists())

    def test_swift_pair_incorrect_code_consumes_one_shot(self):
        helper, code = self._start_pair_helper()
        incorrect = "0" * 16 if code != "0" * 16 else "F" * 16
        result = subprocess.run(
            [str(self.client), "pair", incorrect],
            capture_output=True, text=True, timeout=15
        )
        self.assertEqual(result.returncode, 6, result.stdout + result.stderr)
        self.assertIn("incorreto", result.stdout)
        self.assertNotEqual(helper.wait(timeout=4), 0)
        self.assertFalse(self.marker.exists())

    def test_pair_rejects_malformed_code_without_connection(self):
        result = subprocess.run(
            [str(self.client), "pair", "NOT-A-VALID-CODE"],
            capture_output=True, text=True, timeout=15
        )
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("16 caracteres", result.stdout)
        self.assertFalse(self.marker.exists())

    def test_bad_sha_fails_and_installer_not_called(self):
        server = self._server()
        result = self.run_client("install", self.file, "f" * 64)
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertEqual(server.wait(timeout=4), 1)
        self.assertFalse(self.marker.exists())

    def test_server_install_failure_reported_by_swift(self):
        server = self._server(status="13")
        result = self.run_client("install", self.file, self.sha)
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertIn("falha", result.stdout)
        self.assertEqual(server.wait(timeout=4), 1)
        self.assertTrue(self.marker.exists())

    def test_absent_server_fails_closed(self):
        result = self.run_client("install", self.file, self.sha)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_different_app_container_rejected(self):
        server = self._server()
        unrelated = self.root / "87654321-4321-4ABC-9DEF-1234567890AB"
        other = unrelated / "Library" / "Application Support" / "WebReaderUpdates"
        other.mkdir(parents=True, exist_ok=True)
        outside = other / LEAF
        outside.write_bytes(PAYLOAD)
        self.addCleanup(outside.unlink, missing_ok=True)
        result = self.run_client("install", outside, self.sha)
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertEqual(server.wait(timeout=4), 1)
        self.assertFalse(self.marker.exists())

    def test_invalid_path_hash_does_not_invoke_appinst(self):
        server = self._server()
        bad = self.staging / (LEAF + "-bad")
        bad.write_bytes(PAYLOAD)
        self.addCleanup(bad.unlink, missing_ok=True)
        result = self.run_client("install", bad, self.sha)
        self.assertEqual(result.returncode, 5, result.stdout + result.stderr)
        self.assertEqual(server.wait(timeout=4), 1)
        self.assertFalse(self.marker.exists())


if __name__ == "__main__":
    unittest.main()
