#!/usr/bin/env python3
"""DA: executable host tests of the EXACT C client linked into the UIKit IPA.

Host override for ephemeral port is compile-time forbidden on iOS.
No physical installation, no AppInst, no WebReader data, no internet.
"""
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
import unittest

ROOT = Path(__file__).resolve().parent
DIR = ROOT / "chimera_cx_app_probe"
CLIENT_C = DIR / "cx_client.c"
HOST_C = DIR / "host_main.c"
CX_C = ROOT / "webreader_chimera_checkonly_service.c"
CORE_C = ROOT / "build70_cw_checkonly_core.c"
DISPATCH_C = ROOT / "build70_cw_shared_dispatch.c"


class DASandboxClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.geteuid() == 0:
            raise unittest.SkipTest("DA testing must not grant root privileges")
        cc = shutil.which("clang") or shutil.which("cc")
        if not cc:
            raise RuntimeError("C compiler unavailable")
        cls.tmp = tempfile.TemporaryDirectory(prefix="wr-da-client-")
        cls.client = Path(cls.tmp.name) / "da-client"
        cls.service = Path(cls.tmp.name) / "cx-service"
        for command in (
            [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
             "-DWR_DA_HOST_TEST=1", str(CLIENT_C), str(HOST_C),
             "-o", str(cls.client)],
            [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2", "-pthread",
             "-DWR_CX_HOST_TEST_PORT=0", str(CX_C), str(CORE_C),
             str(DISPATCH_C), "-o", str(cls.service)],
        ):
            r = subprocess.run(command, capture_output=True, text=True, timeout=30)
            if r.returncode:
                raise AssertionError(r.stdout + r.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def check(self, port):
        r = subprocess.run([str(self.client), str(port)],
                           capture_output=True, text=True, timeout=9)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        match = re.fullmatch(r"WR_DA_HOST_RESULT=([0-5])\n", r.stdout)
        self.assertIsNotNone(match, r.stdout)
        return int(match.group(1))

    def test_real_cx_service_note_then_rate(self):
        proc = subprocess.Popen([str(self.service), "serve"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, bufsize=1)
        try:
            ready, _, _ = select.select([proc.stdout], [], [], 5)
            self.assertTrue(ready)
            line = proc.stdout.readline().strip()
            m = re.fullmatch(r"WR_CX_HOST_PORT=(\d+)", line)
            self.assertIsNotNone(m, line)
            port = int(m.group(1))
            self.assertEqual(self.check(port), 1)
            self.assertEqual(self.check(port), 2)
        finally:
            proc.terminate()
            try:
                proc.communicate(timeout=4)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate(timeout=4)

    def test_no_listener_is_unavailable(self):
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            port = s.getsockname()[1]
        self.assertEqual(self.check(port), 0)

    def fake(self, answer):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        received = []
        failures = []
        def worker():
            try:
                with listener.accept()[0] as conn:
                    conn.settimeout(5)
                    data = b""
                    while True:
                        part = conn.recv(24)
                        if not part:
                            break
                        data += part
                    received.append(data)
                    if answer:
                        conn.sendall(answer)
            except Exception as e:
                failures.append(str(e))
            finally:
                listener.close()
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        result = self.check(port)
        thread.join(timeout=6)
        self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(received, [b"WRCHK2\n"])
        return result

    def test_valid_response_is_notice_without_authority(self):
        self.assertEqual(self.fake(b"WRNOTE2\n"), 1)
        self.assertEqual(self.fake(b"WRRATE2\n"), 2)
        self.assertEqual(self.fake(b"WRDENY2\n"), 3)

    def test_malicious_responses_rejected(self):
        for answer in (b"WRDONE1\n", b"WRINST1\n", b"WRNOTE2\nBAD",
                       b"WRNOTE2\n\x00", b"WRNOTE2", b"WRRATE2\nx",
                       b"WRNOTE2\r\n", b""):
            with self.subTest(reply=answer):
                self.assertEqual(self.fake(answer), 4)

    def test_host_port_rejects_invalid(self):
        for text in ("0", "65536", "-1", "bad", "12extra", ""):
            p = subprocess.run([str(self.client), text],
                               capture_output=True, text=True, timeout=4)
            self.assertEqual(p.returncode, 90)

    def test_static_client_never_install_or_browse(self):
        code = CLIENT_C.read_text()
        ui = (DIR / "main.m").read_text()
        hdr = (DIR / "cx_client.h").read_text()
        assert 'WR_DA_PORT 38973u' in code
        assert 'TARGET_OS_IPHONE && defined(WR_DA_HOST_TEST)' in code
        assert "WR_DA_HOST_TEST" in hdr
        assert "shutdown(fd, SHUT_WR)" in code
        assert "INADDR_LOOPBACK" in code
        assert "memcmp(response, \"WRNOTE2\\n\", 8)" in code
        assert 'initWithRootViewController:[[WRDACtrl alloc] init]' in ui
        assert "@selector(startProbe)" in ui
        assert "@selector(copyReport)" in ui
        assert "QOS_CLASS_UTILITY" in ui
        for s in ("posix_spawn(", "fork(", "execve(", "system(",
                  "dlopen(", "fopen(", "open(", "installApplication:",
                  "URLSession", "NSURLSession", "AppInst", "appinst("):
            # Both UI and transport are standalone; no exec/update surfaces.
            self.assertNotIn(s, code)
            if s != "AppInst":  # benign explanatory comment in UI
                self.assertNotIn(s, ui)
        self.assertNotIn("WebReaderUpdateChecker", ui)


if __name__ == "__main__":
    unittest.main()
