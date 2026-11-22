#!/usr/bin/env python3
"""WebReader Build70/DF: offline, read-only Mach-O iOS12 ABI preflight.

Validates text emitted by file(1), otool -hv/-l/-L and nm -u from a
DISPOSABLE Xcode-built CLI. This does NOT verify code signatures,
sandbox entitlements, executable provenance, dynamic-loader behavior
on the iPad, or actual process identity. It does not sign, execute on
iOS, package, distribute or install an executable.

A failure means the candidate is not approved even for further
read-only device validation. A pass is NOT install authorization.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
import sys
from pathlib import Path


class DFMachORejected(ValueError):
    pass


@dataclass(frozen=True)
class DFPreflight:
    verdict: str
    target_arch: str
    target_min_ios: str
    target_platform: str
    only_apple_libsystem_dependency: bool
    imported_symbol_count: int
    self_identity_cli_compatible_by_static_host_checks: bool
    code_signature_validated_on_ios12: bool = False
    app_sandbox_entitlements_validated: bool = False
    actual_ipad_execution_proven: bool = False
    ios12_helper_identity_proven: bool = False
    ipc_peer_authenticated: bool = False
    editor_trust_provisioned: bool = False
    owner_install_consent_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


ALLOWED_IMPORTS = frozenset({
    "_getuid", "_geteuid", "_getgid", "_getegid",
    "_getpid", "_getppid", "_getgroups", "_getgroups$DARWIN_EXTSN",
    "_stat", "_uname",
    "_printf", "_puts", "_putchar",
    "__NSGetExecutablePath",
    "___stack_chk_fail", "___stack_chk_guard",
    "dyld_stub_binder", "_dyld_stub_binder",
})
# Not a generic whitelist for arbitrary apps; only the tiny DE CLI.
TARGET_IOS = (12, 0)
ALLOWED_DYLIBS = frozenset({"/usr/lib/libSystem.B.dylib"})


def _bounded_text(name: str, value: str) -> str:
    if type(value) is not str or not value or len(value) > 128_000 or "\x00" in value:
        raise DFMachORejected("invalid tool output: " + name)
    return value.replace("\r\n", "\n")


def _minimum_ios(load_commands: str) -> tuple[str, tuple[int, int]]:
    # Each LC command is parsed as a block to avoid accepting a random
    # occurrence of "12.0" in a library name or unrelated field.
    chunks = re.split(r"(?m)^\s*Load command\s+\d+\s*$", load_commands)
    identified = []
    for block in chunks:
        if re.search(r"(?m)^\s*cmd\s+LC_BUILD_VERSION\s*$", block):
            platform = re.search(r"(?m)^\s*platform\s+([A-Za-z0-9_]+)\s*$", block)
            minos = re.search(r"(?m)^\s*minos\s+(\d+(?:\.\d+){1,2})\s*$", block)
            if not platform or not minos:
                raise DFMachORejected("incomplete LC_BUILD_VERSION")
            if platform.group(1).upper() not in ("IOS", "2"):
                raise DFMachORejected("not an iOS device Mach-O target")
            identified.append(("IOS", minos.group(1)))
        if re.search(r"(?m)^\s*cmd\s+LC_VERSION_MIN_IPHONEOS\s*$", block):
            version = re.search(r"(?m)^\s*version\s+(\d+(?:\.\d+){1,2})\s*$", block)
            if not version:
                raise DFMachORejected("incomplete legacy iOS min-version")
            identified.append(("IOS", version.group(1)))
    if len(identified) != 1:
        raise DFMachORejected("exactly one iOS build/min-version load command required")
    platform, v = identified[0]
    parts = tuple(int(x) for x in v.split("."))
    if len(parts) == 3 and parts[2] != 0:
        raise DFMachORejected("unexpected patch component in min iOS")
    if len(parts) not in (2, 3) or parts[:2] != TARGET_IOS:
        raise DFMachORejected("minimum iOS must be exactly 12.0")
    return platform, parts[:2]


def _dylibs(value: str) -> frozenset[str]:
    lines = value.splitlines()
    candidates = []
    for line in lines[1:]:
        line = line.strip()
        if not line:
            continue
        match = re.fullmatch(r"(.+?)\s+\(compatibility version [^,]+, current version [^)]+\)", line)
        if not match:
            raise DFMachORejected("unexpected otool -L line")
        candidates.append(match.group(1))
    if not candidates or len(candidates) != len(set(candidates)):
        raise DFMachORejected("no dylibs or duplicate dependency")
    return frozenset(candidates)


def _imports(value: str) -> frozenset[str]:
    imports = []
    for line in value.splitlines():
        if not line.strip():
            continue
        line = line.strip()
        # nm -u may print a path header when multiple binaries are supplied;
        # our workflow passes ONE executable and expects only symbols.
        # Apple nm -u can show either BSD-style "U _name" or just
        # "_name" (one undefined name per line). Both are parsed using
        # an anchored grammar and the SAME small symbol allowlist.
        # Never strip arbitrary suffixes, comments, or library names.
        match = re.fullmatch(r"(?:U\s+)?([A-Za-z_][A-Za-z0-9_$]*)", line)
        if not match:
            raise DFMachORejected("unexpected undefined-symbol line")
        symbol = match.group(1)
        imports.append(symbol)
    if not imports or len(set(imports)) != len(imports):
        raise DFMachORejected("empty or duplicate undefined-symbol list")
    disallowed = set(imports) - ALLOWED_IMPORTS
    if disallowed:
        raise DFMachORejected("unexpected import: " + ",".join(sorted(disallowed)))
    return frozenset(imports)


def inspect_static_macho(*, file_summary: str, header: str,
                         loads: str, dylibs: str, undefined: str) -> DFPreflight:
    f = _bounded_text("file", file_summary)
    h = _bounded_text("otool -hv", header)
    l = _bounded_text("otool -l", loads)
    d = _bounded_text("otool -L", dylibs)
    u = _bounded_text("nm -u", undefined)
    if not re.search(r"Mach-O 64-bit executable arm64(?:\s|$)", f, re.I):
        raise DFMachORejected("expected ARM64 executable, not a library/object")
    # Must be executable, ARM64, PIE. Position of values varies with Xcode.
    machine = h.upper()
    if (not re.search(r"\bARM64\b", machine) or
        not re.search(r"\bEXECUTE\b", machine) or
        not re.search(r"\bPIE\b", machine)):
        raise DFMachORejected("missing ARM64/EXECUTE/PIE Mach header evidence")
    platform, minimum = _minimum_ios(l)
    linked = _dylibs(d)
    if linked != ALLOWED_DYLIBS:
        raise DFMachORejected("unreviewed Mach-O dylib dependency")
    symbols = _imports(u)
    essential = {"_getuid", "_geteuid", "_getgid", "_getegid",
                 "_getpid", "_getppid", "_uname", "_stat",
                 "_printf", "_puts", "_putchar", "__NSGetExecutablePath"}
    groups_symbols = symbols.intersection({"_getgroups", "_getgroups$DARWIN_EXTSN"})
    # The observed iOS12/Xcode16.4 variant is the exact decorated
    # _getgroups$DARWIN_EXTSN import. Accept exactly one of two specific
    # spellings; do NOT normalize arbitrary $suffixes or allow both.
    if len(groups_symbols) != 1 or not essential.issubset(symbols):
        raise DFMachORejected("missing required self-identity imports")
    return DFPreflight(
        verdict="HOST_STATIC_ABI_ONLY_NOT_DEVICE_AUTHORIZED",
        target_arch="arm64",
        target_min_ios=f"{minimum[0]}.{minimum[1]}",
        target_platform=platform,
        only_apple_libsystem_dependency=True,
        imported_symbol_count=len(symbols),
        self_identity_cli_compatible_by_static_host_checks=True,
    )


def main(argv: list[str]) -> int:
    # Explicit five text files, all produced under the ephemeral runner.
    # This CLI never executes the supplied target binary.
    if len(argv) != 6 or any(not p for p in argv[1:]):
        print("usage: audit file.txt header.txt loads.txt dylibs.txt nm.txt",
              file=sys.stderr)
        return 2
    try:
        parts = [
            Path(p).read_text(encoding="utf-8")
            for p in argv[1:]
        ]
        result = inspect_static_macho(
            file_summary=parts[0], header=parts[1],
            loads=parts[2], dylibs=parts[3], undefined=parts[4],
        )
    except (DFMachORejected, UnicodeError, OSError) as exc:
        print("DF_REJECTED: " + str(exc), file=sys.stderr)
        return 3
    print(json.dumps(asdict(result), sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
