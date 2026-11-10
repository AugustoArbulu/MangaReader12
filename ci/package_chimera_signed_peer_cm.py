#!/usr/bin/env python3
"""Phase CM: optional iOS12 diagnostic that preserves bounded kernel failure states.

Replaces ONLY the CL peer diagnostic package (same package identifier, v0.2.0).
The three signed ARM64 test-only CLIs are rebuilt and re-audited as before.
No root helper, appinst, IPA, installation or private data in reports.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import struct

from package_chimera_persistent_ping_deb import pack_tar, ar_member
from package_chimera_signed_peer_cl import (
    ROOT, NAMES, INSTALL, RUNNER, report_shell
)

OUT = ROOT / "WebReader-Chimera-PhaseCM-PeerReason-iOS12.deb"
CHECKSUM = ROOT / (OUT.name + ".sha256")
PKG = "com.example.webreader.peercl"
VERSION = "0.2.0"
CONTROL = """Package: com.example.webreader.peercl
Name: WebReader iOS12 Signed Peer Diagnostic — Reason Codes
Version: 0.2.0
Architecture: iphoneos-arm
Section: Development
Priority: optional
Maintainer: Personal WebReader QA
Description: Read-only peer token/CDHash reason codes, no IPA, appinst, daemon or root helper.
"""
# These statuses originate ONLY from the fixed C server's local classifier.
# No user-input status is interpolated into output. Unknown raw diagnostics
# become INCONCLUSIVE, and all output still marks AUTHORIZATION=DENIED.
KERNEL_CODES = (
    "TOKEN_UNAVAILABLE",
    "CSOPS_MISSING",
    "CDHASH_UNAVAILABLE",
    "TOKEN_MUTATION_UNSAFE",
    "CROSS_PID_UNSAFE",
    "PROTOCOL_REJECTED",
    "TRANSPORT_FAILED",
)

def reason_shell(allowed: str, foreign: str) -> bytes:
    shell = report_shell(allowed, foreign).decode("ascii")
    old = '''  result="$(grep '^RESULT ' "$WORK/$label.out" | tail -n 1 || true)"
  case "$result" in
    'RESULT MATCH_ONLY_NO_AUTH AUTHORIZATION=DENIED')
      echo "OBSERVATION_$label=MATCH_ONLY_NO_AUTH AUTHORIZATION=DENIED" ;;
    'RESULT MISMATCH_REJECTED AUTHORIZATION=DENIED')
      echo "OBSERVATION_$label=MISMATCH_REJECTED AUTHORIZATION=DENIED" ;;
    *)
      echo "OBSERVATION_$label=INCONCLUSIVE AUTHORIZATION=DENIED" ;;
  esac'''
    # Enforce exactly one RESULT line, and a DENIED footer, before outputting
    # even an observation. The text report is never OS-authoritative evidence.
    new = '''  result="$(grep '^RESULT ' "$WORK/$label.out" || true)"
  footer_count="$(grep -Fxc 'FINAL_INSTALL_AUTHORIZATION=DENIED' "$WORK/$label.out" || true)"
  result_count="$(grep -c '^RESULT ' "$WORK/$label.out" || true)"
  if [ "$result_count" != 1 ] || [ "$footer_count" != 1 ]; then
    echo "OBSERVATION_$label=INCONCLUSIVE AUTHORIZATION=DENIED"
    return 0
  fi
  case "$result" in
    'RESULT MATCH_ONLY_NO_AUTH AUTHORIZATION=DENIED')
      echo "OBSERVATION_$label=MATCH_ONLY_NO_AUTH AUTHORIZATION=DENIED" ;;
    'RESULT MISMATCH_REJECTED AUTHORIZATION=DENIED')
      echo "OBSERVATION_$label=MISMATCH_REJECTED AUTHORIZATION=DENIED" ;;
'''
    for name in KERNEL_CODES:
        new += f'''    'RESULT {name} AUTHORIZATION=DENIED')
      echo "OBSERVATION_$label={name} AUTHORIZATION=DENIED" ;;
'''
    new += '''    *)
      echo "OBSERVATION_$label=INCONCLUSIVE AUTHORIZATION=DENIED" ;;
  esac'''
    if shell.count(old) != 1:
        raise ValueError("CL runner changed; exact reason-only patch denied")
    shell = shell.replace(old, new)
    # Different header identifies the revised report; all immutable policy
    # claims remain negative. Never print raw log, path, token, PID, UID, hash.
    shell = shell.replace(
        "WEBREADER_CL_IOS12_SIGNED_PEER: NONROOT READ_ONLY",
        "WEBREADER_CM_IOS12_PEER_REASON: NONROOT READ_ONLY"
    )
    shell = shell.replace(
        "IOS12_RUNTIME_CODE_IDENTITY_SUPPORT=UNPROVEN_BY_THIS_REPORT",
        "IOS12_RUNTIME_CODE_IDENTITY_SUPPORT=UNPROVEN_BY_THIS_REPORT"
    )
    for forbidden in ("appinst", "WRINST1", "launchctl", "sudo ", "curl ", "wget "):
        if forbidden in shell:
            raise ValueError("forbidden privileged or network marker")
    return shell.encode("ascii")


def package(allowed: str, foreign: str) -> tuple[bytes, str]:
    if OUT.exists() or CHECKSUM.exists():
        raise ValueError("refusing to overwrite prior CM artifact")
    body = reason_shell(allowed, foreign)
    files = []
    for kind, name in NAMES.items():
        raw = (ROOT / name).read_bytes()
        if (not 1500 < len(raw) < 350_000
                or raw[:4] != b"\xcf\xfa\xed\xfe"
                or struct.unpack_from("<I", raw, 4)[0] != 0x0100000C):
            raise ValueError("signed ARM64 Mach-O missing or malformed")
        for marker in (
            b"FINAL_INSTALL_AUTHORIZATION=DENIED", b"csops_audittoken",
            b"TOKEN_UNAVAILABLE", b"MATCH_ONLY_NO_AUTH"
        ):
            if marker not in raw:
                raise ValueError("incomplete read-only lab executable")
        for forbidden in (
            b"/usr/bin/appinst", b"WRINST1", b"I-CONFIRM-INSTALL",
            b"launchctl", b"/var/mobile/Documents"
        ):
            if forbidden in raw:
                raise ValueError("privileged or private path marker")
        files.append((INSTALL[kind], raw, 0o755))
    binary_package = (
        b"!<arch>\n" +
        ar_member("debian-binary", b"2.0\n") +
        ar_member("control.tar.gz", pack_tar([
            ("./control", CONTROL.encode("ascii"), 0o644)
        ])) +
        ar_member("data.tar.gz", pack_tar([
            ("./usr/", None, 0o755),
            ("./usr/local/", None, 0o755),
            ("./usr/local/bin/", None, 0o755),
            *files,
            (RUNNER, body, 0o755)
        ]))
    )
    if not 4000 < len(binary_package) < 1_000_000:
        raise ValueError("unexpected CM DEB bound")
    return binary_package, hashlib.sha256(binary_package).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--allowed-cdhash", required=True)
    parser.add_argument("--foreign-cdhash", required=True)
    args = parser.parse_args()
    contents, digest = package(args.allowed_cdhash, args.foreign_cdhash)
    OUT.write_bytes(contents)
    CHECKSUM.write_text(digest + "  " + OUT.name + "\n", encoding="ascii")
    print("PASS CM: optional iOS12 read-only peer reason diagnostics built")
    print("NO APPINST / NO IPA / NO POSTINST / NO ROOT / NO AUTOINSTALL")
    print("SHA256: " + digest)

if __name__ == "__main__":
    main()
