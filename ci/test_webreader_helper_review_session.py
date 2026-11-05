#!/usr/bin/env python3
"""Offline hostile-flow tests for the non-privileged review session prototype."""
from dataclasses import replace
import unittest

from webreader_helper_request_contract import ParsedReviewRequest
from webreader_helper_review_session import (
    ReviewSessionLedger, ReviewSessionRejected
)


def request(nonce="b" * 64, digest="a" * 64, build=57):
    return ParsedReviewRequest(build=build, manifest_sha256=digest, nonce=nonce)


class ReviewSessionTests(unittest.TestCase):
    def setUp(self):
        self.peer = object()
        self.other = object()
        self.counter = 0

        def unique_token():
            self.counter += 1
            return format(self.counter, "064x")

        self.ledger = ReviewSessionLedger(
            ttl_seconds=30.0, challenge_factory=unique_token, max_pending=2
        )

    def begin(self, nonce="b" * 64, peer=None, now=100.0):
        return self.ledger.begin_review(
            request(nonce), self.peer if peer is None else peer, now=now
        )

    def confirm(self, challenge, peer=None, digest="a" * 64,
                build=57, now=101.0):
        return self.ledger.confirm_review(
            challenge.token, self.peer if peer is None else peer,
            independently_verified_digest=digest,
            checked_build=build, now=now
        )

    def test_match_is_review_only_never_install_authorization(self):
        challenge = self.begin()
        result = self.confirm(challenge)
        self.assertEqual(result.requested_build, 57)
        self.assertTrue(result.manifest_sha256_matches_independent_check)
        self.assertFalse(result.install_authorized)

    def test_server_challenge_is_single_use(self):
        challenge = self.begin()
        self.confirm(challenge)
        with self.assertRaises(ReviewSessionRejected):
            self.confirm(challenge)

    def test_replay_of_client_nonce_rejected_after_consumption(self):
        ch = self.begin()
        self.confirm(ch)
        with self.assertRaises(ReviewSessionRejected):
            self.begin()

    def test_cross_peer_token_does_not_consume_original(self):
        ch = self.begin()
        with self.assertRaises(ReviewSessionRejected):
            self.confirm(ch, peer=self.other)
        self.assertFalse(self.confirm(ch).install_authorized)

    def test_bad_digest_consumes_challenge_fail_closed(self):
        ch = self.begin()
        with self.assertRaises(ReviewSessionRejected):
            self.confirm(ch, digest="c" * 64)
        with self.assertRaises(ReviewSessionRejected):
            self.confirm(ch)

    def test_wrong_build_and_type_fail_closed(self):
        for build in (58, True, "57"):
            with self.subTest(build=build):
                ch = self.begin(nonce=format(self.counter + 10, "064x"))
                with self.assertRaises(ReviewSessionRejected):
                    self.confirm(ch, build=build)

    def test_expiry_at_boundary_and_new_request_after_ttl(self):
        ch = self.begin(now=100)
        with self.assertRaises(ReviewSessionRejected):
            self.confirm(ch, now=130)
        # An expired correlation is no longer pending after a cleanup.
        later = self.begin(now=131)
        self.assertNotEqual(ch.token, later.token)

    def test_capacity_and_cancel(self):
        first = self.begin()
        second = self.begin(nonce="c" * 64)
        with self.assertRaises(ReviewSessionRejected):
            self.begin(nonce="d" * 64)
        self.assertFalse(self.ledger.cancel_review(first.token, self.other))
        self.assertTrue(self.ledger.cancel_review(first.token, self.peer))
        self.assertFalse(self.ledger.cancel_review(first.token, self.peer))
        with self.assertRaises(ReviewSessionRejected):
            self.confirm(first)
        replacement = self.begin(nonce="d" * 64)
        self.assertNotEqual(second.token, replacement.token)

    def test_peer_disconnected_revokes_all_reviews(self):
        first = self.begin()
        second = self.begin(nonce="c" * 64)
        self.ledger.revoke_peer(self.peer)
        for ch in (first, second):
            with self.assertRaises(ReviewSessionRejected):
                self.confirm(ch)

    def test_bad_peer_context_types_rejected(self):
        for bad in ("pid-123", 123, None, True, b"peer", 4.5):
            with self.subTest(bad=bad):
                with self.assertRaises(ReviewSessionRejected):
                    self.ledger.begin_review(request(), bad, now=100.0)

    def test_bad_time_rejected(self):
        for bad in (float("nan"), float("inf"), -float("inf"), True, "now"):
            with self.subTest(bad=bad):
                with self.assertRaises(ReviewSessionRejected):
                    self.ledger.begin_review(request(), self.peer, now=bad)

    def test_duplicate_or_malformed_server_token_rejected(self):
        duplicates = ReviewSessionLedger(
            challenge_factory=lambda: "e" * 64, max_pending=2
        )
        duplicates.begin_review(request(), self.peer, now=1)
        with self.assertRaises(ReviewSessionRejected):
            duplicates.begin_review(request("c" * 64), self.peer, now=2)
        malformed = ReviewSessionLedger(challenge_factory=lambda: "nope")
        with self.assertRaises(ReviewSessionRejected):
            malformed.begin_review(request(), self.peer, now=1)

    def test_recent_correlation_history_is_bounded(self):
        for i in range(8):
            ch = self.begin(nonce=format(i + 200, "064x"))
            self.confirm(ch)
        with self.assertRaises(ReviewSessionRejected):
            self.begin(nonce=format(300, "064x"), now=102)
        # Old correlations expire and are then pruned.
        fresh = self.begin(nonce=format(300, "064x"), now=131)
        self.assertTrue(fresh.token)

    def test_review_result_cannot_be_promoted_by_mutating_property(self):
        ch = self.begin()
        assessed = self.confirm(ch)
        with self.assertRaises((AttributeError, TypeError)):
            assessed.install_authorized = True
        self.assertFalse(assessed.install_authorized)

    def test_derived_request_cannot_smuggle_extra_fields(self):
        with self.assertRaises(ReviewSessionRejected):
            self.ledger.begin_review({"build": 57}, self.peer, now=1)

    def test_bad_checked_digest_consumes_once(self):
        ch = self.begin()
        with self.assertRaises(ReviewSessionRejected):
            self.confirm(ch, digest="A" * 64)
        with self.assertRaises(ReviewSessionRejected):
            self.confirm(ch)


if __name__ == "__main__":
    unittest.main()
