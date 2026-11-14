#!/usr/bin/env python3
"""Build68 Phase V — conservative, read-only Chimera installer readiness audit.

The input is a diagnostic transcript, NOT an authenticated statement of
device facts. It does not grant installation even if all lines say "success".
It does not issue IPC, read an IPA, enroll a publisher key or call appinst.
"""
from dataclasses import dataclass

from build66_ios12_physical_capability_policy import (
    PhysicalCapabilityRejected, assess_physical_diagnostic
)

@dataclass(frozen=True)
class Gate:
    name: str
    state: str
    reason: str

@dataclass(frozen=True)
class Readiness:
    gates: tuple
    request_identity_authenticated: bool = False
    release_editor_authenticated_on_device: bool = False
    immutable_ipa_checked_by_installer: bool = False
    trusted_one_shot_consent_verified: bool = False
    anti_replay_verified_in_privileged_helper: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False
    manual_export_remains_available: bool = True

    @property
    def blocked_gates(self):
        return tuple(g.name for g in self.gates if g.state != "PASSED")

    def report(self):
        """Sanitized human-readable audit, no user paths or private tokens."""
        lines = [
            "WEBREADER_BUILD68_CHIMERA_READINESS: READ_ONLY",
            "AUTO_INSTALL=DENIED",
        ]
        for g in self.gates:
            lines.append("GATE " + g.name + "=" + g.state + " " + g.reason)
        lines.extend([
            "MANUAL_EXPORT=REMAINS_AVAILABLE",
            "HELPER_PUBLISHER_AUTHENTICATED=NO",
            "HELPER_PEER_AUTHENTICATED=NO",
            "INSTALLATION_AUTHORIZED=NO",
            "INSTALLATION_PERFORMED=NO",
        ])
        return "\n".join(lines)

def inspect_reported_capabilities(transcript, *, reported_user):
    """Classify observations only; caller cannot turn claims into authority."""
    try:
        decision = assess_physical_diagnostic(
            transcript, reported_user=reported_user
        )
        physical = decision.reason
        if decision.reported_socket_status == "UNAVAILABLE":
            kernel_note = "IOS12_NONROOT_LOCAL_PEERTOKEN_UNAVAILABLE"
        elif decision.reported_socket_status == "TRANSPORT_FAILED":
            kernel_note = "CONTROLLED_SOCKET_TEST_FAILED"
        elif decision.reported_socket_status == "ZERO":
            kernel_note = "ZERO_KERNEL_TOKEN"
        else:
            kernel_note = "LAB_TOKEN_OBSERVED_NOT_WEBREADER_PEER"
    except PhysicalCapabilityRejected:
        physical = "INVALID_UNTRUSTED_TRANSCRIPT"
        kernel_note = physical

    gates = (
        Gate("IOS12_KERNEL_PEER_TOKEN", "UNPROVEN", kernel_note),
        Gate("IOS12_RUNNING_APP_CODE_IDENTITY", "UNPROVEN",
             "NO_KERNEL_BOUND_VERIFIED_WEBREADER_CODE_IDENTITY"),
        Gate("PER_MESSAGE_ORIGIN", "UNPROVEN",
             "SOCKET_HANDLE_CAN_BE_FORWARDED_OR_MESSAGES_QUEUED"),
        Gate("RELEASE_EDITOR_TRUST_ANCHOR", "NOT_CONFIGURED",
             "PRODUCTION_PUBLIC_KEY_MISSING"),
        Gate("RELEASE_BYTES_IN_HELPER", "UNPROVEN",
             "NO_PRIVILEGED_SAME_OBJECT_REHASH_AND_CODESIGN"),
        Gate("TRUSTED_OWNER_CONSENT", "NOT_IMPLEMENTED",
             "NO_SEPARATE_ONE_SHOT_INSTALL_APPROVAL"),
        Gate("PRIVILEGED_REPLAY_AND_DOWNGRADE", "UNPROVEN",
             "NO_PRODUCTION_ATOMIC_JOURNAL_OR_ROLLBACK_POLICY"),
        Gate("PHYSICAL_IOS12_REPRODUCTION", "UNPROVEN",
             physical),
    )
    return Readiness(gates=gates)
