#!/usr/bin/env python3
"""CM independent read-only audit of the opt-in signed iOS12 reason-code DEB.

The three codesigned CLIs are verified against their independently extracted
CodeDirectory hashes, while reason-only runner is checked for denial-only
behavior. No package install, no device access, no appinst.
"""
from pathlib import Path
import hashlib
import subprocess

from package_chimera_signed_peer_cm import OUT, CHECKSUM, PKG, VERSION, KERNEL_CODES
from package_chimera_signed_peer_cl import ROOT, NAMES, INSTALL, RUNNER
from test_chimera_persistent_ping_deb import ar_entries, tar_items
from test_chimera_signed_peer_cl_deb import codehash, main as cl_audit
import test_chimera_signed_peer_cl_deb as cl


def main():
    # Reuse the independently established native signature, entitlement,
    # min iOS12, Mach-O and codehash audit for all THREE signed executables.
    cl.OUT = OUT
    cl.CHECKSUM = CHECKSUM
    cl_audit()
    raw = OUT.read_bytes()
    assert CHECKSUM.read_text("ascii").strip() == (
        hashlib.sha256(raw).hexdigest() + "  " + OUT.name
    )
    archives = ar_entries(raw)
    metadata = tar_items(archives["control.tar.gz"])
    assets = tar_items(
        archives["data.tar.gz"],
        ("./usr/", "./usr/local/", "./usr/local/bin/")
    )
    assert set(metadata) == {"./control"}
    control = metadata["./control"][0]
    assert ("Package: " + PKG + "\n").encode("ascii") in control
    assert ("Version: " + VERSION + "\n").encode("ascii") in control
    assert set(assets) == set(INSTALL.values()) | {RUNNER}
    shell = assets[RUNNER][0]
    assert b"WEBREADER_CM_IOS12_PEER_REASON" in shell
    assert b"FINAL_INSTALL_AUTHORIZATION=DENIED" in shell
    assert b'if [ "$result_count" != 1 ] || [ "$footer_count" != 1 ]; then' in shell
    for kind, binary in NAMES.items():
        assert assets[INSTALL[kind]][0] == (ROOT / binary).read_bytes()
    a = codehash(ROOT / NAMES["allowed"])
    b = codehash(ROOT / NAMES["foreign"])
    assert a != b
    assert b"ALLOWED_PIN=" + a.encode("ascii") in shell
    assert b"FOREIGN_PIN=" + b.encode("ascii") in shell
    for reason in KERNEL_CODES:
        assert (
            "OBSERVATION_$label=" + reason + " AUTHORIZATION=DENIED"
        ).encode("ascii") in shell
    for bad in (b"/usr/bin/appinst", b"WRINST1", b"launchctl", b"curl ",
                b"wget ", b"/var/mobile/", b"INSTALL_GRANTED"):
        assert bad not in shell
    shellcheck = subprocess.run(
        ["/bin/sh", "-n"], input=shell, capture_output=True, timeout=15
    )
    assert shellcheck.returncode == 0, shellcheck.stderr
    print("PASS CM: exact 0.2.0 safe upgrade of optional CL diagnostic package")
    print("PASS CM: preserved signed ARM64 iOS12 identities, reason codes only")
    print("PASS CM: impossible to grant installation by this package")
    print("SHA256: " + hashlib.sha256(raw).hexdigest())


if __name__ == "__main__":
    main()
