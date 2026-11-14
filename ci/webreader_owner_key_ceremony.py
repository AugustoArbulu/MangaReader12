#!/usr/bin/env python3
"""Owner-run OFFLINE P-256 signing key ceremony for WebReader (Phase CO).

No production key is created by CI, GitHub, the assistant or import.
The owner must run --create and enter/confirm an encryption passphrase
interactively on THEIR OWN device. Private key remains AES-encrypted PKCS#8
in an independently selected, pre-existing private directory OUTSIDE repo.

This does NOT enroll the public key into WebReader, publish a release, sign an
IPA/manifest, connect to GitHub, or authorize/perform installation.
Only Python stdlib and a locally preinstalled cryptography package are used.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import getpass
import hashlib
import os
from pathlib import Path
import re
import stat
import sys

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

REPO_ROOT = Path(__file__).resolve().parent.parent
PRIVATE_NAME = "webreader-owner-private-encrypted.pem"
PUBLIC_NAME = "webreader-owner-public.pem"
FINGERPRINT_NAME = "webreader-owner-public-spki-sha256.txt"
FILE_NAMES = (PRIVATE_NAME, PUBLIC_NAME, FINGERPRINT_NAME)
MIN_PASSPHRASE_BYTES = 16
MAX_PASSPHRASE_BYTES = 512
SPKI_P256_PREFIX = bytes.fromhex("3059301306072a8648ce3d020106082a8648ce3d030107034200")


class OwnerCeremonyRejected(ValueError):
    pass


@dataclass(frozen=True)
class OwnerPublicReceipt:
    public_spki_sha256: str
    public_key_curve: str = "secp256r1"
    owner_action_required: bool = True
    private_key_in_repository: bool = False
    key_enrolled_in_app: bool = False
    github_release_published: bool = False
    publisher_authenticated_on_ipad: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def _validate_directory(directory: Path):
    if not isinstance(directory, Path) or not directory.is_absolute():
        raise OwnerCeremonyRejected("pre-existing absolute private directory required")
    # Do not follow symlinks / Windows junctions in ANY part of the parent chain.
    for part in (directory, *directory.parents):
        try:
            st = os.lstat(part)
        except OSError as exc:
            raise OwnerCeremonyRejected("pre-existing directory cannot be inspected") from exc
        if stat.S_ISLNK(st.st_mode) or (
            hasattr(st, "st_file_attributes")
            and st.st_file_attributes & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        ):
            raise OwnerCeremonyRejected("symlink/junction path not permitted")
    resolved = directory.resolve(strict=True)
    repo = REPO_ROOT.resolve(strict=True)
    if resolved == repo or repo in resolved.parents or resolved in repo.parents:
        raise OwnerCeremonyRejected("private files must stay outside repository")
    info = os.stat(directory, follow_symlinks=False)
    if not stat.S_ISDIR(info.st_mode):
        raise OwnerCeremonyRejected("not an existing directory")
    if os.name == "posix" and (
        info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise OwnerCeremonyRejected("on POSIX the owner directory must be user-owned 0700")
    if any((directory / name).exists() or (directory / name).is_symlink()
           for name in FILE_NAMES):
        raise OwnerCeremonyRejected("key ceremony output already exists; never overwrite")
    return resolved


def _passphrase(value: str) -> bytes:
    if type(value) is not str:
        raise OwnerCeremonyRejected("encrypted private key passphrase missing")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise OwnerCeremonyRejected("invalid passphrase") from exc
    if (not MIN_PASSPHRASE_BYTES <= len(encoded) <= MAX_PASSPHRASE_BYTES
            or b"\x00" in encoded or b"\n" in encoded or b"\r" in encoded):
        raise OwnerCeremonyRejected("passphrase must have 16-512 UTF-8 bytes and no controls")
    return encoded


def _write_exclusive(directory: Path, basename: str, payload: bytes):
    if basename not in FILE_NAMES:
        raise OwnerCeremonyRejected("unexpected owner file")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = -1
    try:
        fd = os.open(str(directory / basename), flags, 0o600)
        with os.fdopen(fd, "wb") as output:
            fd = -1
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
    except OSError as exc:
        raise OwnerCeremonyRejected("exclusive key output failed; inspect directory before retry") from exc
    finally:
        if fd >= 0:
            os.close(fd)


def create_owner_identity(*, output_directory: Path, passphrase: str) -> OwnerPublicReceipt:
    """Generate key ONLY from explicit owner CLI invocation or disposable test."""
    target = _validate_directory(output_directory)
    password = _passphrase(passphrase)
    # No networking, no repository mutations, no appinst.
    private = ec.generate_private_key(ec.SECP256R1())
    try:
        encrypted_pem = private.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(password)
        )
        public_pem = private.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        public_spki = private.public_key().public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        if (len(public_spki) != len(SPKI_P256_PREFIX) + 65
                or not public_spki.startswith(SPKI_P256_PREFIX)
                or public_spki[len(SPKI_P256_PREFIX)] != 4
                or b"ENCRYPTED PRIVATE KEY" not in encrypted_pem
                or b"BEGIN PUBLIC KEY" not in public_pem):
            raise OwnerCeremonyRejected("unexpected P-256 or encrypted PKCS8 serialization")
        digest = hashlib.sha256(public_spki).hexdigest()
        # Owner must protect the encrypted key and passphrase independently.
        # Never replace or remove possible partial artifacts on failure.
        _write_exclusive(target, PRIVATE_NAME, encrypted_pem)
        _write_exclusive(target, PUBLIC_NAME, public_pem)
        _write_exclusive(target, FINGERPRINT_NAME,
                         (digest + "\n").encode("ascii"))
        return OwnerPublicReceipt(public_spki_sha256=digest)
    finally:
        # Immutable Python bytes cannot be guaranteed zeroized; passphrase
        # entered via getpass is not printed or placed on process command line.
        del password


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    choice = p.add_mutually_exclusive_group(required=True)
    choice.add_argument("--check", action="store_true",
                        help="verify local tooling ONLY; never create any key")
    choice.add_argument("--create", action="store_true",
                        help="OWNER ACTION: generate an encrypted private key on this computer")
    p.add_argument("--output-dir", type=Path,
                   help="pre-created private directory OUTSIDE the repository")
    args = p.parse_args(argv)
    if args.check:
        print("PASS: local cryptography supports P-256 + encrypted PKCS8 PEM")
        print("NO KEY CREATED, NO NETWORK, NO RELEASE, NO INSTALLATION")
        return 0
    if args.output_dir is None:
        p.error("--create requires --output-dir")
    if not sys.stdin.isatty():
        raise SystemExit("REFUSED: interactive owner terminal required; no CI/key automation")
    directory = _validate_directory(args.output_dir.expanduser().absolute())
    secret = getpass.getpass("Owner release key passphrase (not echoed): ")
    again = getpass.getpass("Confirm passphrase: ")
    if secret != again:
        raise SystemExit("REFUSED: passphrase confirmation differs; no key generated")
    try:
        result = create_owner_identity(output_directory=directory, passphrase=secret)
    except OwnerCeremonyRejected as exc:
        raise SystemExit("REFUSED: " + str(exc)) from exc
    finally:
        del secret, again
    print("PASS: encrypted owner private key created ONLY in the selected local directory")
    print("PUBLIC SPKI SHA256: " + result.public_spki_sha256)
    print("NEXT: independently record/verify public fingerprint; DO NOT upload the private key")
    print("NO WebReader trust installed, NO RELEASE, NO APPINST, NO AUTOUPDATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
