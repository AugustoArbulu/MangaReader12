#!/usr/bin/env python3
"""Build62: enforce fail-closed live iOS appinst path before peer authentication.

Mac-only native Swift compilation. CI uses NO real appinst, IPA, or iPhone.
The host FAKE-appinst harness is separately compiled with its explicit macro.
"""
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "MangaReader12/Core"
VIEW = ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift"

PRODUCTION_RUNNER = r'''
import Foundation

@main
struct Build62DenyRunner {
    static func main() {
        let forbiddenTarget = URL(fileURLWithPath:
            "/var/mobile/Documents/WebReader-build999-test.ipa")
        let digest = String(repeating: "a", count: 64)
        var called = false
        WebReaderAppinstSocket.install(
            ipaURL: forbiddenTarget, expectedSHA256: digest
        ) { result in
            called = true
            switch result {
            case .rejected:
                print("BUIL62_LIVE_INSTALL_DENIED")
            default:
                print("BUILD62_UNSAFE_INSTALL_RESULT")
                exit(41)
            }
        }
        // Drain the main DispatchQueue without blocking it.
        let deadline = Date(timeIntervalSinceNow: 3)
        while !called && Date() < deadline {
            RunLoop.current.run(mode: .default,
                                before: Date(timeIntervalSinceNow: 0.05))
        }
        if !called { print("BUILD62_NO_CALLBACK"); exit(42) }
    }
}
'''

FORBIDDEN_HOST_ACCESS = r'''
import Foundation

@main
struct HostOnlyAccess {
    static func main() {
        let sample = URL(fileURLWithPath: "/tmp/nonexistent.ipa")
        _ = WebReaderAppinstSocket.hostInstall(
            directory: sample, ipaURL: sample,
            sha256: String(repeating: "a", count: 64)
        )
    }
}
'''


def compile_swift(source, folder, name):
    harness = Path(folder) / (name + ".swift")
    output = Path(folder) / name
    harness.write_text(source)
    cmd = [
        "xcrun", "swiftc", "-parse-as-library",
        str(CORE / "WebReaderHelperPingProbe.swift"),
        str(CORE / "WebReaderAppinstSocket.swift"),
        str(harness), "-o", str(output)
    ]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=95
    )
    return result, output


def main():
    client = (CORE / "WebReaderAppinstSocket.swift").read_text()
    screen = VIEW.read_text()

    assert "static let liveInstallationEnabled = false" in client
    assert "DispatchQueue.main.async { completion(.rejected) }" in client
    assert "private static func performInstall(" in client
    assert "#if WEBREADER_HOST_TEST" in client
    assert "static func hostInstall(" in client
    assert "WebReaderAppinstSocket.install(" not in screen
    assert "confirmAppinstInstallation()" not in screen
    assert "requestAppinstInstallation(" not in screen
    assert "Instalação pelo Chimera bloqueada" in screen
    assert "Aguardando política independente de autorização e chave editorial" in screen
    assert "copyManualAppinstCommand(" not in screen
    assert 'UIPasteboard.general.string = "appinst "' not in screen
    # Current updater wraps the initializer across lines for its progress callback.
    # Verify the same contract without depending on whitespace formatting.
    assert "WebReaderIPAStager(" in screen
    assert "verifiedUpdate: update" in screen
    assert "UIActivityViewController(activityItems: [url]" in screen
    assert "WebReaderNativeIPAAuditor.inspect(" in screen
    assert "showFilzaInstructions()" in screen
    assert '"Como instalar pelo Filza"' in screen

    if platform.system() != "Darwin":
        raise RuntimeError("this native security test requires macOS runner")

    with tempfile.TemporaryDirectory(prefix="build62-noinst-") as folder:
        run_build, runner = compile_swift(PRODUCTION_RUNNER, folder, "deny-runner")
        assert run_build.returncode == 0, run_build.stdout + run_build.stderr
        outcome = subprocess.run(
            [str(runner)], capture_output=True, text=True, timeout=12
        )
        assert outcome.returncode == 0, outcome.stdout + outcome.stderr
        assert "BUIL62_LIVE_INSTALL_DENIED" in outcome.stdout

        binary = runner.read_bytes()
        assert b"WRINST1\n" not in binary, (
            "real iOS Swift client still embeds an install request header"
        )
        assert b"I-CONFIRM-INSTALL" not in binary

        host_build, _ = compile_swift(
            FORBIDDEN_HOST_ACCESS, folder, "forbidden-host-runner"
        )
        assert host_build.returncode != 0, (
            "macOS-only hostInstall was exposed in production compilation"
        )
        assert "hostInstall" in host_build.stderr

    print("PASS Build62: live Swift install call always rejects (native macOS)")
    print("PASS Build62: production binary omits WRINST1/install consent")
    print("PASS Build62: host fake-installer API is compile-time unavailable")
    print("PASS Build62: UI exports verified IPA without install or CLI commands")


if __name__ == "__main__":
    main()
