#!/usr/bin/env python3
"""Build66 phase-B: crash-closed, host-only diagnostic replay ledger.

NO privileged service, socket, install request, appinst, IPA, or trusted consent.
The directory must already be provisioned with 0700 owner-only permissions.
The marker is reserved by O_CREAT | O_EXCL and fsynced; a crash or failed write
must never cause an accepted request to be reissued in the same trusted store.

This CANNOT resist rollback/deletion by an attacker who controls the directory,
disk snapshots, key storage or root. DO NOT reuse as an installation gate.
"""
import hashlib
import os
from pathlib import Path
import re
import stat
import struct

_HASH = re.compile(r"[0-9a-f]{64}\Z")
_NONCE = re.compile(r"[0-9a-f]{32}\Z")
_MAX_BUILD = 2_147_483_647


class ReplayJournalUnavailable(ValueError):
    pass


def _valid_hash(text, pattern):
    return isinstance(text, str) and pattern.fullmatch(text) is not None


class DiagnosticReplayJournal:
    """Atomic at-most-once marker per unique test request, durable on host FS.

    The directory is independently selected by the harness, not by the request.
    It is NEVER auto-created. Do not use a client-writable location for real
    authorization. Persistent test state contains no IPA bytes or credentials.
    """

    def __init__(self, directory):
        self.directory = Path(directory)
        # Opening / validating is repeated at each attempt, not just init.
        fd = self._validate_directory()
        os.close(fd)

    def _validate_directory(self):
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
        if not hasattr(os, "O_DIRECTORY") or not hasattr(os, "O_NOFOLLOW"):
            raise ReplayJournalUnavailable("atomic secure directory open unsupported")
        try:
            directory_fd = os.open(self.directory, flags)
        except OSError as exc:
            raise ReplayJournalUnavailable("protected replay directory unavailable") from exc
        try:
            identity = os.fstat(directory_fd)
            if (not stat.S_ISDIR(identity.st_mode)
                    or stat.S_IMODE(identity.st_mode) != 0o700
                    or identity.st_uid != os.getuid()):
                raise ReplayJournalUnavailable("replay directory not owner-private")
            return directory_fd
        except BaseException:
            os.close(directory_fd)
            raise

    @staticmethod
    def _marker_name(challenge, manifest_sha256, ipa_sha256, target_build):
        if (not _valid_hash(challenge, _NONCE)
                or not _valid_hash(manifest_sha256, _HASH)
                or not _valid_hash(ipa_sha256, _HASH)
                or type(target_build) is not int
                or not 1 <= target_build <= _MAX_BUILD):
            raise ReplayJournalUnavailable("invalid replay reference")
        domain = b"WEBREADER-DIAG-SPENT-V1\x00"
        data = (domain + bytes.fromhex(challenge)
                + bytes.fromhex(manifest_sha256)
                + bytes.fromhex(ipa_sha256)
                + struct.pack(">I", target_build))
        return hashlib.sha256(data).hexdigest() + ".spent"

    def reserve_once(self, *, challenge, manifest_sha256, ipa_sha256, target_build):
        """True for first durable reservation; False for a spent request.

        No accepted request is returned until the marker and its directory are
        fsynced. If any IO fails, the caller MUST treat it as rejection.
        """
        name = self._marker_name(challenge, manifest_sha256, ipa_sha256, target_build)
        directory_fd = self._validate_directory()
        child_fd = -1
        try:
            flags = (os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0))
            try:
                child_fd = os.open(name, flags, 0o600, dir_fd=directory_fd)
            except FileExistsError:
                return False
            except OSError as exc:
                raise ReplayJournalUnavailable("cannot reserve replay marker") from exc

            try:
                # An existing marker is spent, even if interrupted mid-write.
                with os.fdopen(child_fd, "wb") as marker:
                    child_fd = -1
                    marker.write(b"SPENT\n")
                    marker.flush()
                    os.fsync(marker.fileno())
                os.fsync(directory_fd)
            except OSError as exc:
                # Never unlink a possibly created marker on error.
                raise ReplayJournalUnavailable("failed to persist replay marker") from exc
            return True
        finally:
            if child_fd != -1:
                os.close(child_fd)
            os.close(directory_fd)
