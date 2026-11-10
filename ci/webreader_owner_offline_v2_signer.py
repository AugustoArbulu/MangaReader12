#!/usr/bin/env python3
"""Phase CP: owner-local OFFLINE encrypted P-256 signed v2 manifest candidate.

No production private key is generated, stored in Git, transferred to CI,
printed, or put on a process command line. The owner types the decryption
passphrase on their own computer. Works on Windows/Linux with cryptography.

This is NOT a native Apple code signature audit and does NOT publish/install.
Any resulting signed manifest is only a CANDIDATE requiring independent
macOS native IPA seal preflight, editor/owner approval, and later device trust.
"""
from __future__ import annotations

import argparse
import base64
from datetime import datetime
import getpass
import hashlib
import hmac
import io
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import sys
import zipfile

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from webreader_owner_key_ceremony import (
    PRIVATE_NAME, PUBLIC_NAME, FINGERPRINT_NAME, REPO_ROOT
)
from webreader_update_manifest import (
    APP_BUNDLE_ID, INSTALLED_APPLICATION_IDENTIFIER, MAX_IPA_BYTES,
    MAX_ENVELOPE_BYTES, MAX_PAYLOAD_BYTES, _validate_payload, ManifestRejected
)

ALGORITHM = "ecdsa-p256-sha256"
MAX_NOTES_FILE = 8 * 1024
MAX_KEYFILE = 4096
MIN_PASSWORD_BYTES = 16
MAX_PASSWORD_BYTES = 512
APP_PLIST = "Payload/MangaReader12.app/Info.plist"
EXECUTABLE = "Payload/MangaReader12.app/MangaReader12"
REQUIRED = (PRIVATE_NAME, PUBLIC_NAME, FINGERPRINT_NAME)


class OwnerManifestRejected(ValueError):
    pass


def _external_regular(path: Path, *, limit: int) -> bytes:
    if not isinstance(path, Path) or not path.is_absolute():
        raise OwnerManifestRejected("absolute local external file required")
    # Never accept a symlink or junction at any path component.
    if REPO_ROOT.resolve() == path.resolve() or REPO_ROOT.resolve() in path.resolve().parents:
        raise OwnerManifestRejected("release and private keys cannot reside in the repository")
    for parent in (path, *path.parents):
        try:
            st = os.lstat(parent)
        except OSError as exc:
            raise OwnerManifestRejected("input missing") from exc
        if (stat.S_ISLNK(st.st_mode) or
            getattr(st, "st_file_attributes", 0) &
                getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
            raise OwnerManifestRejected("reparse link input forbidden")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0)
                     | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            if not stat.S_ISREG(before.st_mode) or not 0 < before.st_size <= limit:
                raise OwnerManifestRejected("input regular file bounds invalid")
            content = handle.read(limit + 1)
            after = os.fstat(handle.fileno())
            identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns,
                                  s.st_ctime_ns)
            if len(content) != before.st_size or identity(before) != identity(after):
                raise OwnerManifestRejected("input changed during read")
            if identity(after) != identity(os.stat(path, follow_symlinks=False)):
                raise OwnerManifestRejected("input filename changed during read")
            return content
    except OSError as exc:
        raise OwnerManifestRejected("input cannot be safely read") from exc


def _parse_ipa_snapshot(raw: bytes, *, installed_build: int) -> dict:
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_IPA_BYTES:
        raise OwnerManifestRejected("invalid IPA snapshot")
    try:
        from build66_ipa_preflight import MAX_FILES, MAX_UNCOMPRESSED
        with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
            members = bundle.infolist()
            if not 1 <= len(members) <= MAX_FILES:
                raise OwnerManifestRejected("invalid IPA ZIP entries")
            total = 0
            names = set()
            for item in members:
                name = item.filename
                if (not name or name.startswith("/") or "\\" in name
                        or any(x in ("", ".", "..")
                               for x in name.rstrip("/").split("/"))
                        or (name != "Payload/" and not name.startswith(
                            "Payload/MangaReader12.app/"))):
                    raise OwnerManifestRejected("unsafe IPA ZIP member")
                if name in names or item.flag_bits & 1:
                    raise OwnerManifestRejected("duplicate or encrypted ZIP member")
                names.add(name)
                if (item.file_size < 0 or item.file_size > MAX_IPA_BYTES
                        or (item.file_size and not item.compress_size)
                        or (item.compress_size and
                            item.file_size > item.compress_size * 10000)):
                    raise OwnerManifestRejected("invalid IPA ZIP entry size")
                if (item.external_attr >> 16) & 0o170000 == stat.S_IFLNK:
                    raise OwnerManifestRejected("ZIP symlink")
                total += item.file_size
                if total > MAX_UNCOMPRESSED:
                    raise OwnerManifestRejected("IPA ZIP expansion limit")
            if APP_PLIST not in names or EXECUTABLE not in names:
                raise OwnerManifestRejected("missing expected app identity")
            if (bundle.getinfo(APP_PLIST).file_size > 1024 * 1024
                    or bundle.getinfo(EXECUTABLE).file_size < 4):
                raise OwnerManifestRejected("invalid app metadata or executable size")
            info = plistlib.loads(bundle.read(APP_PLIST))
    except (zipfile.BadZipFile, ValueError, OSError, EOFError, OverflowError,
            KeyError, RuntimeError, TypeError) as exc:
        if isinstance(exc, OwnerManifestRejected):
            raise
        raise OwnerManifestRejected("malformed IPA ZIP or plist") from exc
    if not isinstance(info, dict) or info.get("CFBundleIdentifier") != APP_BUNDLE_ID or (
        info.get("CFBundleExecutable") != "MangaReader12"
        or info.get("CFBundleDisplayName") != "WebReader"
    ):
        raise OwnerManifestRejected("wrong WebReader application")
    build = info.get("CFBundleVersion")
    minimum = info.get("MinimumOSVersion")
    if (not isinstance(build, str)
            or not re.fullmatch(r"[1-9][0-9]{0,9}", build)
            or not isinstance(minimum, str)
            or not re.fullmatch(r"\d{1,2}\.\d{1,2}(?:\.\d{1,2})?", minimum)):
        raise OwnerManifestRejected("invalid build or iOS version")
    build_int = int(build)
    if build_int <= installed_build or build_int > 2_147_483_647:
        raise OwnerManifestRejected("downgrade or oversized build")
    return {
        "build": build_int,
        "minimumIOS": minimum,
        "ipaSize": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest()
    }


def sign_owner_candidate(*, owner_directory: Path, ipa_path: Path,
                         notes_path: Path, output: Path,
                         passphrase: str, independent_spki_sha256: str,
                         published_at: str, installed_build: int = 70) -> dict:
    """Cryptographically bind reviewed input IPA bytes to candidate v2 envelope.

    Local file read is still not a native seal/installer immutable-file proof.
    """
    if type(installed_build) is not int or not 70 <= installed_build <= 2_147_483_647:
        raise OwnerManifestRejected("Build70+ installed baseline required")
    if type(independent_spki_sha256) is not str or not re.fullmatch(
        r"[0-9a-f]{64}", independent_spki_sha256
    ):
        raise OwnerManifestRejected("owner supplied pinned fingerprint missing")
    if (not isinstance(owner_directory, Path) or not owner_directory.is_absolute()
            or any(not (owner_directory / name).exists() for name in REQUIRED)):
        raise OwnerManifestRejected("owner local identity files missing")
    if type(passphrase) is not str:
        raise OwnerManifestRejected("owner must provide interactive passphrase")
    password = passphrase.encode("utf-8")
    if (not MIN_PASSWORD_BYTES <= len(password) <= MAX_PASSWORD_BYTES
            or b"\x00" in password or b"\n" in password or b"\r" in password):
        raise OwnerManifestRejected("invalid interactive passphrase")
    if not isinstance(output, Path) or not output.is_absolute():
        raise OwnerManifestRejected("absolute output filename required")
    if (output.is_symlink() or output.exists()
            or REPO_ROOT.resolve() == output.resolve()
            or REPO_ROOT.resolve() in output.resolve().parents
            or not output.parent.is_dir()):
        raise OwnerManifestRejected("unsafe output or existing signed manifest")
    if output.name != "channel-production-v2.json":
        raise OwnerManifestRejected("production channel output name must be exact")
    if (not isinstance(published_at, str) or
            not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}Z", published_at)):
        raise OwnerManifestRejected("exact owner-supplied UTC publishedAt required")
    try:
        datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise OwnerManifestRejected("invalid publication timestamp") from exc

    public_pem = _external_regular(owner_directory / PUBLIC_NAME, limit=MAX_KEYFILE)
    fingerprint_file = _external_regular(owner_directory / FINGERPRINT_NAME, limit=128)
    private_pem = _external_regular(owner_directory / PRIVATE_NAME, limit=MAX_KEYFILE)
    try:
        public = serialization.load_pem_public_key(public_pem)
        if not isinstance(public, ec.EllipticCurvePublicKey) or not isinstance(
            public.curve, ec.SECP256R1
        ):
            raise OwnerManifestRejected("owner public key is not P-256")
        public_spki = public.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        observed_pin = hashlib.sha256(public_spki).hexdigest()
        if (fingerprint_file != (observed_pin + "\n").encode("ascii")
                or not hmac.compare_digest(observed_pin, independent_spki_sha256)):
            raise OwnerManifestRejected("owner public key/pin do not match")
        if not private_pem.startswith(b"-----BEGIN ENCRYPTED PRIVATE KEY-----\n"):
            raise OwnerManifestRejected("private key must be encrypted PKCS8")
        private = serialization.load_pem_private_key(private_pem, password=password)
        if not isinstance(private, ec.EllipticCurvePrivateKey) or not isinstance(
            private.curve, ec.SECP256R1
        ) or private.public_key().public_numbers() != public.public_numbers():
            raise OwnerManifestRejected("owner keypair mismatch")
    except (ValueError, TypeError, UnicodeError) as exc:
        if isinstance(exc, OwnerManifestRejected):
            raise
        raise OwnerManifestRejected("encrypted private key, passphrase or public key rejected") from exc

    if not isinstance(ipa_path, Path) or not ipa_path.is_absolute():
        raise OwnerManifestRejected("absolute IPA path required")
    ipa_snapshot = _external_regular(ipa_path, limit=MAX_IPA_BYTES)
    ipa = _parse_ipa_snapshot(ipa_snapshot, installed_build=installed_build)
    build = ipa["build"]
    if ipa_path.name != f"WebReader-Build{build}-iOS12-adhoc.ipa":
        raise OwnerManifestRejected("IPA filename does not match signed Release URL")
    notes_raw = _external_regular(notes_path, limit=MAX_NOTES_FILE)
    try:
        notes = json.loads(notes_raw.decode("utf-8"))
    except (UnicodeError, ValueError, TypeError) as exc:
        raise OwnerManifestRejected("malformed local release notes") from exc
    if (type(notes) is not list or len(notes) > 20
            or any(type(x) is not str or not 1 <= len(x) <= 240 for x in notes)):
        raise OwnerManifestRejected("release notes must be bounded list")
    payload = {
        "schemaVersion": 2,
        "application": "WebReader",
        "bundleId": APP_BUNDLE_ID,
        "applicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
        "channel": "production",
        "build": build,
        "minimumIOS": ipa["minimumIOS"],
        "ipaUrl": ("https://github.com/AugustoArbulu/MangaReader12/releases/"
                   f"download/build{build}/WebReader-Build{build}-iOS12-adhoc.ipa"),
        "ipaSize": ipa["ipaSize"],
        "sha256": ipa["sha256"],
        "releaseNotes": notes,
        "publishedAt": published_at
    }
    try:
        _validate_payload(payload, installed_build, "12.5.8", "production")
    except ManifestRejected as exc:
        raise OwnerManifestRejected("invalid signed v2 payload") from exc
    raw_payload = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    if not len(raw_payload) <= MAX_PAYLOAD_BYTES:
        raise OwnerManifestRejected("payload too long")
    signature = private.sign(raw_payload, ec.ECDSA(hashes.SHA256()))
    try:
        public.verify(signature, raw_payload, ec.ECDSA(hashes.SHA256()))
    except InvalidSignature as exc:
        raise OwnerManifestRejected("signature did not verify") from exc
    envelope = {
        "schemaVersion": 2, "algorithm": ALGORITHM,
        "payload": base64.b64encode(raw_payload).decode("ascii"),
        "signature": base64.b64encode(signature).decode("ascii"),
    }
    raw_envelope = (
        json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("ascii")
        + b"\n"
    )
    if len(raw_envelope) > MAX_ENVELOPE_BYTES:
        raise OwnerManifestRejected("envelope too long")
    # Never overwrite an existing manifest; refuse an output filename that
    # could be used to feed the untrusted input path back to the owner.
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(output, flags, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw_envelope)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        raise OwnerManifestRejected("exclusive signed envelope output failed") from exc
    return {
        "status": "OWNER_LOCAL_SIGNED_CANDIDATE_NO_RELEASE",
        "build": build,
        "signedManifestSHA256": hashlib.sha256(raw_envelope).hexdigest(),
        "ipaSHA256": ipa["sha256"],
        "ipaSize": ipa["ipaSize"],
        "publicSPKISHA256": observed_pin,
        "signedPayloadVerifiedInMemory": True,
        "publicPinComparedToOwnerInput": True,
        "publicPinIndependentOwnerAuthenticationProvenByTool": False,
        "nativeAppleIPACodeSealVerifiedByTool": False,
        "macOSNativeProductionPreflightStillRequired": True,
        "ownerPublicationApprovalRecorded": False,
        "productionTrustProvisionedOnIPad": False,
        "releasePublished": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="check cryptography only; no signing")
    parser.add_argument("--sign", action="store_true",
                        help="owner-only explicit interactive signing")
    parser.add_argument("--owner-dir", type=Path)
    parser.add_argument("--ipa", type=Path)
    parser.add_argument("--notes-file", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--independent-spki-sha256")
    parser.add_argument("--published-at")
    parser.add_argument("--installed-build", type=int, default=70)
    args = parser.parse_args(argv)
    if args.check and not args.sign:
        print("PASS CP: P256 encrypted manifest signing dependencies available")
        print("NO KEY LOADED, NO MANIFEST SIGNED, NO RELEASE, NO INSTALL")
        return 0
    if not args.sign or args.check or any(x is None for x in (
        args.owner_dir, args.ipa, args.notes_file, args.output,
        args.independent_spki_sha256, args.published_at
    )):
        parser.error("use --sign with owner-dir, IPA, notes, output, public pin and publication UTC")
    if not sys.stdin.isatty():
        raise SystemExit("REFUSED: signing requires an interactive owner terminal")
    secret = getpass.getpass("Owner encrypted key passphrase (not echoed): ")
    try:
        report = sign_owner_candidate(
            owner_directory=args.owner_dir.expanduser().absolute(),
            ipa_path=args.ipa.expanduser().absolute(),
            notes_path=args.notes_file.expanduser().absolute(),
            output=args.output.expanduser().absolute(),
            passphrase=secret, independent_spki_sha256=args.independent_spki_sha256,
            published_at=args.published_at, installed_build=args.installed_build
        )
    except OwnerManifestRejected as exc:
        raise SystemExit("REFUSED: " + str(exc)) from exc
    finally:
        del secret
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
