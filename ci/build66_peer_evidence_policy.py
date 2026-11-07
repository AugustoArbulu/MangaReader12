#!/usr/bin/env python3
"""Build66 unprivileged peer-evidence threat-model evaluator.

NO peer authenticity can be concluded from a caller-supplied JSON report.
This model records why PID, UID, TCP loopback, observed HMAC and unsigned or
ad-hoc code identity are inadequate. It never opens IPC, calls a privileged
helper, checks a live device, or returns permission to install.

Actual client identity would require an independent OS-authoritative binding
between the connection and a verified running code identity on iOS12/Chimera.
No such primitive has been established by this project.
"""
from dataclasses import dataclass
import json

FIELDS = frozenset({
    "transport", "pid", "uid", "bundleId", "appIdentifier",
    "hmacPairingPassed", "codeSignatureValid", "auditTokenClaimed",
})
TRANSPORTS = frozenset({"unix", "tcp-loopback", "xpc", "unknown"})
BUNDLE = "com.example.MangaReader12"
APP_IDENTIFIER = "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
MAX_REPORT_BYTES = 1024


@dataclass(frozen=True)
class PeerEvidenceReport:
    metadata_consistent: bool
    reason: str
    os_bound_audit_identity_verified: bool = False
    running_code_identity_verified: bool = False
    requester_authenticated: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def _keys(pairs):
    obj = {}
    for k, v in pairs:
        if k in obj:
            raise ValueError("duplicate key")
        obj[k] = v
    return obj


def _deny(reason, metadata_consistent=False):
    return PeerEvidenceReport(metadata_consistent, reason)


def evaluate_untrusted_peer_evidence(blob):
    """Purely classify untrusted data; always deny actual peer authorization.

    Never construct or accept an authentication decision from this payload.
    In particular, auditTokenClaimed is a *self-reported boolean*, not an OS
    audit token obtained from the connection transport.
    """
    if not isinstance(blob, bytes) or not 0 < len(blob) <= MAX_REPORT_BYTES:
        return _deny("UNTRUSTED_REPORT_SIZE")
    try:
        report = json.loads(
            blob.decode("utf-8"), object_pairs_hook=_keys,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite"))
        )
    except (UnicodeError, ValueError, TypeError, OverflowError):
        return _deny("UNTRUSTED_REPORT_MALFORMED")
    if not isinstance(report, dict) or set(report) != FIELDS:
        return _deny("UNTRUSTED_REPORT_FIELDS")
    if (report["transport"] not in TRANSPORTS
            or type(report["pid"]) is not int or report["pid"] < 0
            or type(report["uid"]) is not int or report["uid"] < 0
            or type(report["bundleId"]) is not str
            or type(report["appIdentifier"]) is not str
            or any(type(report[name]) is not bool for name in
                   ("hmacPairingPassed", "codeSignatureValid", "auditTokenClaimed"))):
        return _deny("UNTRUSTED_REPORT_TYPES")
    if report["bundleId"] != BUNDLE or report["appIdentifier"] != APP_IDENTIFIER:
        return _deny("CLAIMED_APPLICATION_MISMATCH")
    if report["transport"] == "unknown":
        return _deny("NO_OBSERVABLE_TRANSPORT")
    if report["pid"] == 0:
        return _deny("PID_UNAVAILABLE")
    # These are observations/claims, never kernel-bound code attestation.
    if report["auditTokenClaimed"]:
        return _deny("SELF_ASSERTED_AUDIT_TOKEN_IS_NOT_EVIDENCE", True)
    if report["codeSignatureValid"]:
        return _deny("ADHOC_CODE_SEAL_DOES_NOT_AUTHENTICATE_PEER", True)
    if report["hmacPairingPassed"]:
        return _deny("PAIRING_PROOF_IS_NOT_PEER_IDENTITY", True)
    return _deny("PID_UID_AND_SOCKET_CANNOT_AUTHORIZE", True)
