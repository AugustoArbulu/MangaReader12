#!/usr/bin/env python3
"""Read-only verification of an extracted WebReader iOS12 IPC field-test kit.

This is a transport/identity sanity check, NOT publisher authentication,
code-signature validation, a full IPA audit, jailbreak attestation or permission
to run the native helper. Use only the verified GitHub Actions artifact from
the intended commit. No network, execution, extraction or filesystem writes.
"""
import argparse
import hashlib
import json
import plistlib
from pathlib import Path
import re
import stat
import struct
import sys
import zipfile

IPA_NAME = "WebReader-IPC-Probe-iOS12-unsigned.ipa"
HELPER_NAME = "WebReader-Helper-Ping-iOS12"
PLIST_MEMBER = "Payload/MangaReader12.app/Info.plist"
HEX64 = re.compile(r"[0-9a-f]{64}", re.ASCII)
MAX_IPA_BYTES = 256 * 1024 * 1024
MAX_HELPER_BYTES = 8 * 1024 * 1024
MAX_PLIST_BYTES = 256 * 1024


class KitRejected(ValueError):
    pass


def _regular_file(path: Path, max_bytes: int) -> int:
    if path.is_symlink() or not path.is_file():
        raise KitRejected("missing or linked kit file: " + path.name)
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size == 0 or st.st_size > max_bytes:
        raise KitRejected("invalid kit file size: " + path.name)
    return st.st_size


def _digest_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while True:
            data = stream.read(256 * 1024)
            if not data:
                break
            digest.update(data)
    return digest.hexdigest()


def _expected_sha(sha_path: Path, filename: str) -> str:
    _regular_file(sha_path, 256)
    data = sha_path.read_bytes()
    if not data.endswith(b"\n") or data.count(b"\n") != 1:
        raise KitRejected("invalid checksum file format: " + filename)
    try:
        line = data.decode("ascii").rstrip("\n")
    except UnicodeDecodeError as error:
        raise KitRejected("invalid checksum encoding") from error
    match = re.fullmatch(r"([0-9a-f]{64})  ([A-Za-z0-9._-]+)", line)
    if not match or match.group(2) != filename:
        raise KitRejected("checksum name or digest malformed: " + filename)
    return match.group(1)


def _validate_ipa(path: Path):
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            names = [i.filename for i in infos]
            if len(names) != len(set(names)) or PLIST_MEMBER not in names:
                raise KitRejected("duplicate or missing entries in IPA")
            if any(name.startswith("/") or "\\" in name or
                   ".." in name.split("/") for name in names):
                raise KitRejected("untrusted entry names in IPA")
            info = archive.getinfo(PLIST_MEMBER)
            if info.file_size > MAX_PLIST_BYTES:
                raise KitRejected("oversized Info.plist")
            metadata = plistlib.loads(archive.read(info))
    except (OSError, zipfile.BadZipFile, plistlib.InvalidFileException) as exc:
        raise KitRejected("invalid IPA ZIP or Info.plist") from exc
    if type(metadata) is not dict:
        raise KitRejected("IPA metadata not dictionary")
    requirements = {
        "CFBundleIdentifier": "com.example.MangaReader12.ipcprobe",
        "CFBundleExecutable": "MangaReader12",
        "CFBundleVersion": "56",
        "CFBundleDisplayName": "WebReader IPC Test",
        "MinimumOSVersion": "12.0",
    }
    for key, value in requirements.items():
        if metadata.get(key) != value:
            raise KitRejected("unexpected IPA identity: " + key)
    if "UIBackgroundModes" in metadata:
        raise KitRejected("IPC diagnostic requests background activity")


def _validate_arm64_helper(path: Path):
    with path.open("rb") as stream:
        header = stream.read(32)
    if len(header) != 32:
        raise KitRejected("truncated native helper")
    magic, cpu_type, cpu_subtype, file_type = struct.unpack_from("<IIII", header)
    if (magic != 0xFEEDFACF or cpu_type != 0x0100000C or
            file_type != 2):
        raise KitRejected("helper is not a thin ARM64 Mach-O executable")
    # We deliberately do not infer signature validity from a Mach-O header.
    return {"format": "Mach-O 64-bit", "architecture": "arm64"}


def verify_kit(root: Path) -> dict:
    if not root.is_absolute() or not root.is_dir() or root.is_symlink():
        raise KitRejected("kit root must be an existing absolute directory")
    ipath = root / IPA_NAME
    hpath = root / HELPER_NAME
    sizes = {
        IPA_NAME: _regular_file(ipath, MAX_IPA_BYTES),
        HELPER_NAME: _regular_file(hpath, MAX_HELPER_BYTES),
    }
    hashes = {}
    for name, path in [(IPA_NAME, ipath), (HELPER_NAME, hpath)]:
        expected = _expected_sha(root / (name + ".sha256"), name)
        actual = _digest_file(path)
        if actual != expected:
            raise KitRejected("SHA-256 mismatch: " + name)
        hashes[name] = actual
    _validate_ipa(ipath)
    helper = _validate_arm64_helper(hpath)
    return {
        "status": "PASS",
        "bundle_id": "com.example.MangaReader12.ipcprobe",
        "version": "56",
        "ipa_bytes": sizes[IPA_NAME],
        "ipa_sha256": hashes[IPA_NAME],
        "helper_bytes": sizes[HELPER_NAME],
        "helper_sha256": hashes[HELPER_NAME],
        "helper_architecture": helper["architecture"],
        "installation_authorized": False,
        "signature_provenance_verified": False,
        "device_compatibility_proven": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True,
                        help="directory containing extracted CI artifact files")
    args = parser.parse_args()
    try:
        report = verify_kit(args.directory.resolve())
        print(json.dumps(report, sort_keys=True, ensure_ascii=False, indent=2))
    except (KitRejected, OSError, ValueError) as error:
        print("REJECTED IPC kit: " + str(error), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
