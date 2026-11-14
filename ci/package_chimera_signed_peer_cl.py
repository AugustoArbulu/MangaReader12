#!/usr/bin/env python3
"""Phase CL: optional iOS12 physical AF_UNIX signed-peer capability lab.

Package three independently ad-hoc-signed iOS12 ARM64 CLI executables built
from the vetted Phase G source, plus a one-command, non-root, one-shot POSIX
shell runner. No appinst, IPA, daemon, launchd, postinst, network, private key,
root service or access to the WebReader app/container.

The baked CDHashes are test references only; this is NOT app publisher
authentication and CANNOT authorize installing a WebReader release.
"""
import argparse
import hashlib
from pathlib import Path
import re
import struct

from package_chimera_persistent_ping_deb import pack_tar, ar_member

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "WebReader-Chimera-PhaseCL-SignedPeer-iOS12.deb"
CHECKSUM = ROOT / (OUT.name + ".sha256")
NAMES = {
    "server": "WebReader-CL-PeerServer-iOS12",
    "allowed": "WebReader-CL-PeerAllowedClient-iOS12",
    "foreign": "WebReader-CL-PeerForeignClient-iOS12",
}
INSTALL = {
    kind: "./usr/local/bin/webreader-peercl-" + kind
    for kind in NAMES
}
RUNNER = "./usr/local/bin/webreader-peercl-report"
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
CONTROL = """Package: com.example.webreader.peercl
Name: WebReader iOS12 Signed Peer Identity Read-Only Lab
Version: 0.1.0
Architecture: iphoneos-arm
Section: Development
Priority: optional
Maintainer: Personal WebReader QA
Description: Three separately signed iOS12 CLI binaries and one-shot non-root local peer diagnostic. No installer.
"""

def report_shell(allowed: str, foreign: str) -> bytes:
    if not HEX40.fullmatch(allowed) or not HEX40.fullmatch(foreign) or allowed == foreign:
        raise ValueError("two distinct canonical signed CodeDirectory references required")
    # This script never calls executable paths supplied by its caller.
    # mktemp and the socket name stay short under Darwin sun_path limits.
    script = r'''#!/bin/sh
set -eu
umask 077
if [ "$(id -u)" -eq 0 ]; then
  echo "REFUSE_ROOT: run only as mobile" >&2
  exit 3
fi
SERVER=/usr/local/bin/webreader-peercl-server
ALLOWED=/usr/local/bin/webreader-peercl-allowed
FOREIGN=/usr/local/bin/webreader-peercl-foreign
ALLOWED_PIN=__ALLOWED__
FOREIGN_PIN=__FOREIGN__
WORK="$(mktemp -d /tmp/wrcl.XXXXXX)" || exit 4
cleanup() {
  rm -f "$WORK"/a.sock "$WORK"/b.sock "$WORK"/c.sock "$WORK"/*.out "$WORK"/*.err
  rmdir "$WORK" 2>/dev/null || true
}
trap 'cleanup' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
echo "WEBREADER_CL_IOS12_SIGNED_PEER: NONROOT READ_ONLY"
echo "REFERENCE=ADHOC_HOST_BUILT_NOT_EDITORIAL"
echo "APP_PEER_AUTHENTICATED=NO"
echo "TRANSPORT_TEST=UNIX_LOCAL_TWO_SIGNED_EXECUTABLES"
run_case() {
  label="$1"
  client="$2"
  expected="$3"
  sock="$WORK/$label.sock"
  "$SERVER" serve-once "$sock" "$expected" >"$WORK/$label.out" 2>"$WORK/$label.err" &
  child="$!"
  attempt=0
  while [ "$attempt" -lt 30 ] && [ ! -S "$sock" ]; do
    attempt=$((attempt + 1))
    sleep 0.1
  done
  if [ ! -S "$sock" ]; then
    echo "OBSERVATION_$label=SOCKET_UNAVAILABLE AUTHORIZATION=DENIED"
    wait "$child" 2>/dev/null || true
    return 0
  fi
  if ! "$client" client-once "$sock" > /dev/null 2>&1; then
    echo "OBSERVATION_$label=CLIENT_FAILED AUTHORIZATION=DENIED"
    wait "$child" 2>/dev/null || true
    return 0
  fi
  wait "$child" 2>/dev/null || true
  result="$(grep '^RESULT ' "$WORK/$label.out" | tail -n 1 || true)"
  case "$result" in
    'RESULT MATCH_ONLY_NO_AUTH AUTHORIZATION=DENIED')
      echo "OBSERVATION_$label=MATCH_ONLY_NO_AUTH AUTHORIZATION=DENIED" ;;
    'RESULT MISMATCH_REJECTED AUTHORIZATION=DENIED')
      echo "OBSERVATION_$label=MISMATCH_REJECTED AUTHORIZATION=DENIED" ;;
    *)
      echo "OBSERVATION_$label=INCONCLUSIVE AUTHORIZATION=DENIED" ;;
  esac
}
run_case a "$ALLOWED" "$ALLOWED_PIN"
run_case b "$FOREIGN" "$ALLOWED_PIN"
run_case c "$FOREIGN" "$FOREIGN_PIN"
echo "IOS12_RUNTIME_CODE_IDENTITY_SUPPORT=UNPROVEN_BY_THIS_REPORT"
echo "BUNDLE_AND_PUBLISHER_IDENTITY=NOT_TESTED"
echo "FINAL_INSTALL_AUTHORIZATION=DENIED"
'''
    return script.replace("__ALLOWED__", allowed).replace("__FOREIGN__", foreign).encode("ascii")


def package(allowed: str, foreign: str) -> tuple[bytes, str]:
    if OUT.exists() or CHECKSUM.exists():
        raise ValueError("artifact already exists; refuse overwrite")
    files = []
    for kind, name in NAMES.items():
        binary = (ROOT / name).read_bytes()
        if not 1500 < len(binary) < 350_000 or binary[:4] != b"\xcf\xfa\xed\xfe":
            raise ValueError("missing signed thin Apple Mach-O for " + kind)
        if struct.unpack_from("<I", binary, 4)[0] != 0x0100000C:
            raise ValueError("not ARM64 binary")
        for marker in (
            b"FINAL_INSTALL_AUTHORIZATION=DENIED",
            b"TOKEN_UNAVAILABLE", b"csops_audittoken",
            b"MATCH_ONLY_NO_AUTH", b"MISMATCH_REJECTED"
        ):
            if marker not in binary:
                raise ValueError("peer diagnostic marker missing")
        for forbidden in (
            b"/usr/bin/appinst", b"WRINST1", b"I-CONFIRM-INSTALL",
            b"/var/mobile/Documents", b"launchctl"
        ):
            if forbidden in binary:
                raise ValueError("install or identity-leak marker found")
        files.append((INSTALL[kind], binary, 0o755))
    data = pack_tar([
        ("./usr/", None, 0o755),
        ("./usr/local/", None, 0o755),
        ("./usr/local/bin/", None, 0o755),
        *files,
        (RUNNER, report_shell(allowed, foreign), 0o755)
    ])
    body = (
        b"!<arch>\n" + ar_member("debian-binary", b"2.0\n")
        + ar_member("control.tar.gz", pack_tar([
            ("./control", CONTROL.encode("ascii"), 0o644)
        ])) + ar_member("data.tar.gz", data)
    )
    if not 4000 < len(body) < 1_000_000:
        raise ValueError("unexpected package envelope")
    return body, hashlib.sha256(body).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--allowed-cdhash", required=True)
    ap.add_argument("--foreign-cdhash", required=True)
    args = ap.parse_args()
    package_bytes, digest = package(args.allowed_cdhash, args.foreign_cdhash)
    OUT.write_bytes(package_bytes)
    CHECKSUM.write_text(digest + "  " + OUT.name + "\n", encoding="ascii")
    print("PASS CL: iOS12 ARM64 signed-peer CLI-only optional DEB generated")
    print("NONROOT, NO APPINST, NO INSTALL, NO POSTINST, NO AUTOMATIC EXECUTION")
    print("SHA256: " + digest)


if __name__ == "__main__":
    main()
