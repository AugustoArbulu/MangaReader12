#!/usr/bin/env python3
"""Build66 physical iOS12/Chimera peer-capability decision, host-only.

This parses the seven lines actually produced by the user's nonroot Build66
diagnostic. Text reports are forgeable: a valid report is OBSERVATIONAL,
never a cryptographic trust root or install permission.

The policy intentionally makes NO assumption about why LOCAL_PEERTOKEN failed:
getsockopt errno, absent support, sandbox policy, buffer sizing or process
environment can be indistinguishable in the current diagnostic output.

No socket, subprocess, filesystem writes, appinst or network APIs.
"""
from dataclasses import dataclass
from build66_csops_capability_report import (
    CSOpsReportRejected, parse_csops_report
)

ALL_SYMBOLS = (
    "SecCodeCreateWithAuditToken",
    "SecCodeCopyGuestWithAttributes",
    "SecCodeCreateWithPID",
)


class PhysicalCapabilityRejected(ValueError):
    pass


@dataclass(frozen=True)
class PhysicalDeviceDecision:
    reported_socket_status: str
    reported_csops_status: str
    reported_security_symbols: tuple
    ios12_runtime_peer_identity_available: bool = False
    per_message_sender_authenticated: bool = False
    release_publisher_authenticated: bool = False
    production_key_provisioned: bool = False
    safe_automatic_install_path_confirmed: bool = False
    # A host-only model never knows which app is installed, or whether the
    # text was genuinely captured on the device.
    device_report_attested: bool = False
    client_may_request_check_only: bool = True
    interactive_manual_install_remains_fallback: bool = True
    root_escalation_permitted_for_diagnostic: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False
    reason: str = ""


def assess_physical_diagnostic(blob, *, reported_user: str):
    """Consume captured transcript only, with explicit observed 'mobile' user.

    reported_user comes from a separately observed 'whoami' result; it is a
    claim for lab reporting, NOT an authenticated identity assertion.
    """
    if reported_user != "mobile":
        raise PhysicalCapabilityRejected("nonroot mobile observation required")
    try:
        parsed = parse_csops_report(blob)
    except CSOpsReportRejected as exc:
        raise PhysicalCapabilityRejected("invalid or unauthorized device transcript") from exc
    symbols = dict(parsed.security_symbol_observations)
    if set(symbols) != set(ALL_SYMBOLS):
        raise PhysicalCapabilityRejected("incomplete symbol observations")
    if parsed.socket_observation == "UNAVAILABLE":
        reason = "PEERTOKEN_UNAVAILABLE_CSOPS_NOT_TESTED"
    elif parsed.socket_observation == "TRANSPORT_FAILED":
        reason = "CONTROLLED_TRANSPORT_FAILED"
    elif parsed.socket_observation == "ZERO":
        reason = "ZERO_KERNEL_TOKEN_NOT_USABLE"
    elif parsed.csops_observation in ("MUTATION_ACCEPTED_UNSAFE",
                                      "CROSS_PID_ACCEPTED_UNSAFE"):
        reason = "KERNEL_BINDING_NEGATIVE_TEST_FAILED"
    elif parsed.csops_observation == "MUTATION_REJECTED":
        reason = "LAB_CHILD_BINDING_OBSERVED_NOT_APP_AUTHENTICATED"
    else:
        reason = "KERNEL_CODE_IDENTITY_NOT_CONFIRMED"
    return PhysicalDeviceDecision(
        reported_socket_status=parsed.socket_observation,
        reported_csops_status=parsed.csops_observation,
        reported_security_symbols=tuple(sorted(symbols.items())),
        reason=reason,
    )


# A fixture of the user's ACTUAL seven public status lines.
# No PID, device identifier, secret, token bytes or personal path is included.
IOS12_CHIMERA_MOBILE_OBSERVATION_2026_11_07 = b"""\
WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only
PROBE UNIX_PEERTOKEN=UNAVAILABLE AUTHORIZATION=DENIED
PROBE CSOPS_TOKEN_BINDING=NOT_TESTED AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithAuditToken=MISSING AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCopyGuestWithAttributes=MISSING AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithPID=MISSING AUTHORIZATION=DENIED
FINAL_INSTALL_AUTHORIZATION=DENIED
"""
