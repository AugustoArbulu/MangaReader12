#!/usr/bin/env python3
"""Phase CN: PURE, HOST-ONLY untrusted update-check wakeup policy.

An untrusted Chimera IPC connection may at most request a RATE-LIMITED,
FIXED-SOURCE, READ-ONLY version check. It supplies NO URL, path, digest,
version, publisher key, installer consent, user identity or code signature.

This function DOES NOT fetch anything, open sockets, create a privileged
service, mutate a file, download an IPA, call appinst or install a release.
An accepted check wakeup is NEVER authorization to install.

Design alternative to LOCAL_PEERTOKEN when real iOS12 reports unavailable.
Peer authenticity is deliberately NOT considered or inferred.
"""
from dataclasses import dataclass
import math

# Exactly seven bytes. There is no variable-length or caller-controlled data.
CHECK_ONLY_FRAME = b"WRCHK2\n"
MIN_CHECK_INTERVAL = 60.0


class CheckOnlyRejected(ValueError):
    pass


@dataclass(frozen=True)
class CheckOnlyDecision:
    check_notice_accepted: bool
    reason: str
    source_caller_untrusted: bool = True
    externally_supplied_url_accepted: bool = False
    externally_supplied_path_accepted: bool = False
    externally_supplied_manifest_accepted: bool = False
    externally_supplied_digest_accepted: bool = False
    publisher_identity_verified: bool = False
    release_signature_verified: bool = False
    installer_file_verified: bool = False
    owner_install_consent_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


class CheckOnlyGate:
    """Single-process, in-memory *read-only notification*, not an installer.

    In real software a global bounded queue and resource caps are necessary.
    This pure simulation cannot be an authorization source. It deliberately
    does not track, rely on, or receive asserted client PID/UID/bundle ID.
    """

    def __init__(self):
        self._next_allowed_at = None

    def offer(self, packet: bytes, *, monotonic_seconds: float) -> CheckOnlyDecision:
        if type(packet) is not bytes or packet != CHECK_ONLY_FRAME:
            raise CheckOnlyRejected("only fixed untrusted check-only frame accepted")
        if (type(monotonic_seconds) not in (int, float)
                or not math.isfinite(monotonic_seconds)
                or monotonic_seconds < 0):
            raise CheckOnlyRejected("invalid monotonic timestamp")
        timestamp = float(monotonic_seconds)
        if self._next_allowed_at is not None and timestamp < self._next_allowed_at:
            return CheckOnlyDecision(False, "RATE_LIMITED_OR_CLOCK_REWOUND")
        self._next_allowed_at = timestamp + MIN_CHECK_INTERVAL
        return CheckOnlyDecision(True, "FIXED_READ_ONLY_VERSION_CHECK_NOTICE_ONLY")
