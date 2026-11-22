#!/usr/bin/env python3
"""Nonprivileged integration laboratory: independently pinned signed v2
metadata -> single-use request consistency -> durable replay marker.

This is an offline diagnostic ONLY. The code has NO IPC, socket, updater,
appinst, consent UI, helper, or other privileged capability.
"""
import hashlib

from build66_durable_replay_journal import (
    DiagnosticReplayJournal, ReplayJournalUnavailable
)
from build66_one_shot_diagnostic import (
    OneShotDiagnostic, DiagnosticResult
)
from build66_release_key_pinning_gate import verify_independently_pinned_v2


class DurableOneShotDiagnostic:
    def __init__(
        self, *, signed_envelope, public_key_pem, trusted_spki_sha256,
        staged_ipa_path, installed_build, replay_directory, entropy=None,
        clock=None
    ):
        # Verify signed metadata and IPA independently before issuing any
        # diagnostic challenge. This creates NO installation authorization.
        receipt = verify_independently_pinned_v2(
            signed_envelope, public_key_pem, trusted_spki_sha256,
            staged_ipa_path, installed_build=installed_build
        )
        self._manifest_digest = hashlib.sha256(signed_envelope).hexdigest()
        self._ipa_digest = receipt["ipa_sha256"]
        self._target_build = receipt["build"]
        self._ledger = DiagnosticReplayJournal(replay_directory)
        self._session = OneShotDiagnostic(
            target_build=self._target_build, installed_build=installed_build,
            manifest_sha256=self._manifest_digest,
            ipa_sha256=self._ipa_digest,
            entropy=entropy, clock=clock,
        )

    def challenge(self):
        return self._session.challenge()

    def check_once(self, request_bytes):
        # A nonce returned in public is not an authenticator or a capability.
        # Reserve BEFORE inspecting untrusted request bytes. A malformed
        # attempt therefore stays spent even if the host process crashes.
        try:
            new_reservation = self._ledger.reserve_once(
                challenge=self.challenge(),
                manifest_sha256=self._manifest_digest,
                ipa_sha256=self._ipa_digest,
                target_build=self._target_build,
            )
        except ReplayJournalUnavailable:
            return DiagnosticResult(
                request_consistent=False,
                reason="REPLAY_JOURNAL_UNAVAILABLE_REJECTED",
            )
        if not new_reservation:
            return DiagnosticResult(
                request_consistent=False,
                reason="PERSISTENT_REPLAY_REJECTED",
            )
        return self._session.check_once(request_bytes)
