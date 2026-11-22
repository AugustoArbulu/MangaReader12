#!/usr/bin/env python3
"""Phase DE: strict parser for self-only UID/GID probes, NOT attestation.

Even if two reports say that their EUIDs differ, the labels/output are
untrusted bytes. This code NEVER grants access to a helper, network, IPA,
release, download or install. It is not an IPC peer identity checker.
"""
from dataclasses import dataclass
import re


class DEReportRejected(ValueError):
    pass


FIELDS = (
    "DE_SCHEMA",
    "DE_ROLE",
    "DE_SELF_UID",
    "DE_SELF_EUID",
    "DE_SELF_GID",
    "DE_SELF_EGID",
    "DE_SELF_PID",
    "DE_SELF_PPID",
    "DE_SELF_GROUPS",
    "DE_SELF_BINARY_METADATA",
    "DE_SELF_BINARY_OWNER_UID",
    "DE_SELF_BINARY_MODE",
    "DE_KERNEL_FAMILY",
    "DE_PROCESS_IDENTITY_SCOPE",
    "DE_SELF_BINARY_SIGNING_VERIFIED",
    "DE_IPC_PEER_AUTHENTICATED",
    "DE_IOS12_HELPER_ISOLATION_VERIFIED",
    "DE_APP_WRITE_DENIAL_VERIFIED",
    "DE_OWNER_INSTALL_CONSENT_VERIFIED",
    "DE_INSTALLATION_AUTHORIZED",
    "DE_INSTALLATION_ATTEMPTED",
)
KNOWN_ROLES = frozenset({"MOBILE_CANDIDATE", "HELPER_CANDIDATE"})
UINT32 = (1 << 32) - 1


@dataclass(frozen=True)
class DEIdentityObservation:
    role_label: str
    uid: int
    euid: int
    gid: int
    egid: int
    pid: int
    ppid: int
    supplementary_groups: tuple[int, ...] | None
    kernel_family: str
    binary_owner_uid: int | None
    binary_mode: int | None
    # These labels are a parse of UNTRUSTED report text, not authority.
    real_ios12_process_identity_attested: bool = False
    peer_identity_authenticated: bool = False
    ios12_helper_uid_isolation_proven: bool = False
    ipad_app_write_denial_proven: bool = False
    binary_code_signature_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


@dataclass(frozen=True)
class DEPairAssessment:
    verdict: str
    mobile_label_euid: int
    helper_label_euid: int
    same_kernel_family_reported: bool
    self_reported_euids_differ: bool
    # No matter what text is supplied, a report pair is not an attestation.
    actual_process_separation_proven_on_ios12: bool = False
    ipc_peer_identity_authenticated: bool = False
    helpers_independently_provisioned: bool = False
    same_uid_app_tamper_excluded: bool = False
    owner_install_consent_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def _uint(name: str, value: str) -> int:
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,9})", value, flags=re.ASCII):
        raise DEReportRejected("invalid unsigned field: " + name)
    n = int(value, 10)
    if n > UINT32:
        raise DEReportRejected("integer overflow: " + name)
    return n


def parse_self_report(source: bytes) -> DEIdentityObservation:
    if type(source) is not bytes or len(source) > 4096 or b"\r" in source:
        raise DEReportRejected("untrusted report format/length")
    try:
        s = source.decode("ascii")
    except UnicodeDecodeError as exc:
        raise DEReportRejected("report must be ASCII") from exc
    if not s.endswith("\n"):
        raise DEReportRejected("report is truncated")
    lines = s[:-1].split("\n")
    if len(lines) != len(FIELDS):
        raise DEReportRejected("unexpected report line count")
    values = {}
    for expected, line in zip(FIELDS, lines):
        if not line.startswith(expected + "="):
            raise DEReportRejected("missing, duplicate or reordered key")
        value = line[len(expected)+1:]
        if not value:
            # Empty supplementary groups are valid. No other fields may be empty.
            if expected != "DE_SELF_GROUPS":
                raise DEReportRejected("empty required value")
        if any(ch in value for ch in "\n\0="):
            raise DEReportRejected("invalid report value")
        values[expected] = value
    if values["DE_SCHEMA"] != "1" or values["DE_ROLE"] not in KNOWN_ROLES:
        raise DEReportRejected("unknown protocol or role")
    if values["DE_KERNEL_FAMILY"] not in ("Linux", "Darwin"):
        raise DEReportRejected("unexpected kernel family")
    if values["DE_PROCESS_IDENTITY_SCOPE"] != "SELF_ONLY":
        raise DEReportRejected("report claiming peer attestation")
    for field in (
        "DE_SELF_BINARY_SIGNING_VERIFIED", "DE_IPC_PEER_AUTHENTICATED",
        "DE_IOS12_HELPER_ISOLATION_VERIFIED", "DE_APP_WRITE_DENIAL_VERIFIED",
        "DE_OWNER_INSTALL_CONSENT_VERIFIED", "DE_INSTALLATION_AUTHORIZED",
        "DE_INSTALLATION_ATTEMPTED",
    ):
        if values[field] != "NO":
            raise DEReportRejected("authority field must be NO: " + field)
    numbers = {
        name: _uint(name, values[name])
        for name in (
            "DE_SELF_UID", "DE_SELF_EUID", "DE_SELF_GID", "DE_SELF_EGID",
            "DE_SELF_PID", "DE_SELF_PPID",
        )
    }
    groups_text = values["DE_SELF_GROUPS"]
    if groups_text == "UNAVAILABLE":
        groups = None
    elif not groups_text:
        groups = ()
    else:
        fragments = groups_text.split(",")
        if len(fragments) > 64:
            raise DEReportRejected("too many groups")
        groups = tuple(_uint("DE_SELF_GROUPS", value) for value in fragments)
    meta = values["DE_SELF_BINARY_METADATA"]
    if meta == "UNAVAILABLE":
        if (values["DE_SELF_BINARY_OWNER_UID"] != "UNAVAILABLE" or
                values["DE_SELF_BINARY_MODE"] != "UNAVAILABLE"):
            raise DEReportRejected("inconsistent binary metadata")
        owner, mode = None, None
    elif meta == "AVAILABLE":
        owner = _uint("DE_SELF_BINARY_OWNER_UID",
                      values["DE_SELF_BINARY_OWNER_UID"])
        raw_mode = values["DE_SELF_BINARY_MODE"]
        if not re.fullmatch(r"[0-7]{4}", raw_mode, flags=re.ASCII):
            raise DEReportRejected("invalid binary mode")
        mode = int(raw_mode, 8)
    else:
        raise DEReportRejected("unexpected binary metadata status")
    return DEIdentityObservation(
        role_label=values["DE_ROLE"],
        uid=numbers["DE_SELF_UID"], euid=numbers["DE_SELF_EUID"],
        gid=numbers["DE_SELF_GID"], egid=numbers["DE_SELF_EGID"],
        pid=numbers["DE_SELF_PID"], ppid=numbers["DE_SELF_PPID"],
        supplementary_groups=groups,
        kernel_family=values["DE_KERNEL_FAMILY"],
        binary_owner_uid=owner, binary_mode=mode,
    )


def assess_self_report_pair(
    a: DEIdentityObservation, b: DEIdentityObservation,
) -> DEPairAssessment:
    if not isinstance(a, DEIdentityObservation) or not isinstance(b, DEIdentityObservation):
        raise DEReportRejected("both reports must be parsed observations")
    by_label = {a.role_label: a, b.role_label: b}
    if len(by_label) != 2 or set(by_label) != KNOWN_ROLES:
        raise DEReportRejected("requires one of each role label")
    mobile = by_label["MOBILE_CANDIDATE"]
    helper = by_label["HELPER_CANDIDATE"]
    same_kernel = mobile.kernel_family == helper.kernel_family
    different = mobile.euid != helper.euid
    if not same_kernel:
        verdict = "INCOMPARABLE_SELF_REPORTS"
    elif not different:
        verdict = "SAME_EUID_SELF_REPORTED_NOT_ISOLATED"
    else:
        verdict = "DISTINCT_EUID_SELF_REPORTED_UNATTESTED"
    return DEPairAssessment(
        verdict=verdict,
        mobile_label_euid=mobile.euid,
        helper_label_euid=helper.euid,
        same_kernel_family_reported=same_kernel,
        self_reported_euids_differ=different,
    )


# Deliberately no CLI options, no OS authorization API and no side effects.
