#!/usr/bin/env python3
"""Build66 Phase D: requester-blind READ-ONLY release check policy.

A local client may request ONLY a check for a trusted release: not a URL,
filename, bundle, command, digest or installed build. The host policy receives
those from its OWN separately configured inputs. This makes spoofed requests
incapable of selecting arbitrary IPA bytes, but does not prevent denial of
service and DOES NOT authorize installation.

No listener, daemon, credentials, shell, network, appinst or privileges exist
in this module. The production iOS app still has no pinned release key.
"""
from dataclasses import dataclass
import threading

from build66_release_key_pinning_gate import verify_independently_pinned_v2

REQUEST = b"WR-CHECK-APPROVED-RELEASE-ONLY-V1\n"


@dataclass(frozen=True)
class CheckOnlyReceipt:
    candidate_verified: bool
    reason: str
    candidate_build: int | None = None
    release_ipa_sha256: str | None = None
    requester_authenticated: bool = False
    user_install_consent_verified: bool = False
    publisher_trust_root_configured_by_app: bool = False
    code_signature_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


class RequesterBlindCheck:
    """A host-only check engine; a client cannot select the verified artifact.

    In a future implementation, the HOST itself must obtain the signed
    manifest and staged IPA from an independently trusted release channel.
    Constructor arguments here model a preconfigured host, not IPC fields.
    """

    def __init__(self, *, trusted_manifest, pinned_p256_public_key,
                 independently_trusted_spki_sha256, host_staged_ipa,
                 host_installed_build):
        receipt = verify_independently_pinned_v2(
            trusted_manifest, pinned_p256_public_key,
            independently_trusted_spki_sha256, host_staged_ipa,
            installed_build=host_installed_build
        )
        self._build = receipt["build"]
        self._ipa_digest = receipt["ipa_sha256"]
        self._lock = threading.Lock()
        self._spent = False

    def check_once(self, client_message):
        with self._lock:
            if self._spent:
                return CheckOnlyReceipt(False, "REPLAY_OR_DUPLICATE_REQUEST")
            # Even an invalid command consumes one attempt in this laboratory.
            self._spent = True
            if type(client_message) is not bytes or client_message != REQUEST:
                return CheckOnlyReceipt(False, "UNTRUSTED_REQUEST_REJECTED")
            return CheckOnlyReceipt(
                True, "TRUSTED_CANDIDATE_ONLY_NO_INSTALL",
                candidate_build=self._build,
                release_ipa_sha256=self._ipa_digest
            )
