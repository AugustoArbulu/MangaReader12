#!/usr/bin/env python3
"""CT host-only adversarial copy stages; synthetic bytes only."""
import hashlib
import inspect
from pathlib import Path
import tempfile
import unittest

from build70_ct_two_hop_delivery_lab import (
    ALTERED, ORIGINAL, CTReviewRejected, same_uid_post_review_mutation,
    two_hop_review,
)


class CTTwoHopTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="wr-ct-unittest-")
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.source, self.review, self.second = (
            root / "source", root / "review", root / "second"
        )
        for folder in (self.source, self.review, self.second):
            folder.mkdir(mode=0o700)
            folder.chmod(0o700)
        self.candidate = self.source / "candidate.fake"
        self.candidate.write_bytes(ORIGINAL)
        self.digest = hashlib.sha256(ORIGINAL).hexdigest()

    def run_review(self, **kwargs):
        return two_hop_review(
            source_dir=self.source, review_dir=self.review,
            second_dir=self.second, expected_sha256=self.digest,
            expected_size=len(ORIGINAL), **kwargs
        )

    def test_clean_two_hop_review_not_install_permission(self):
        result = self.run_review()
        self.assertTrue(result.both_copies_verified_at_review)
        self.assertEqual(result.expected_sha256, self.digest)
        self.assertEqual(result.helper_review_sha256, self.digest)
        self.assertEqual(result.second_copy_sha256, self.digest)
        for field in ("protection_from_later_same_uid_mutation",
                      "true_privilege_separation_proven",
                      "macos_native_code_signature_checked",
                      "exact_iOS_installer_consumption_proven",
                      "publisher_authenticated", "owner_consent_verified",
                      "appinst_called", "installation_authorized",
                      "installation_performed"):
            with self.subTest(field=field):
                self.assertFalse(getattr(result, field))

    def test_injection_between_first_and_second_copy_rejected(self):
        def swap(path):
            old = path.with_suffix(".old")
            path.rename(old)
            path.write_bytes(ALTERED)
        with self.assertRaises(CTReviewRejected):
            self.run_review(after_first_copy=swap)

    def test_inplace_mutation_between_copies_rejected(self):
        def mutate(path):
            path.write_bytes(ALTERED)
        with self.assertRaises(CTReviewRejected):
            self.run_review(after_first_copy=mutate)

    def test_second_pathname_swap_before_final_readback_rejected(self):
        def swap(path):
            path.rename(path.with_suffix(".old"))
            path.write_bytes(ALTERED)
        with self.assertRaises(CTReviewRejected):
            self.run_review(after_second_copy=swap)

    def test_second_inplace_mutation_before_final_readback_rejected(self):
        with self.assertRaises(CTReviewRejected):
            self.run_review(after_second_copy=lambda path: path.write_bytes(ALTERED))

    def test_review_stage_already_exists_never_overwritten(self):
        self.run_review()
        second_expected = hashlib.sha256(next(self.second.iterdir()).read_bytes()).hexdigest()
        with self.assertRaises(CTReviewRejected):
            self.run_review()
        self.assertEqual(
            hashlib.sha256(next(self.second.iterdir()).read_bytes()).hexdigest(),
            second_expected
        )

    def test_wrong_expected_digest_rejected(self):
        with self.assertRaises(CTReviewRejected):
            two_hop_review(
                source_dir=self.source, review_dir=self.review, second_dir=self.second,
                expected_sha256="0" * 64, expected_size=len(ORIGINAL)
            )

    def test_wrong_size_rejected(self):
        with self.assertRaises(CTReviewRejected):
            two_hop_review(
                source_dir=self.source, review_dir=self.review, second_dir=self.second,
                expected_sha256=self.digest, expected_size=len(ORIGINAL) + 1
            )

    def test_permissive_staging_directory_rejected(self):
        for field in ("source", "review", "second"):
            with self.subTest(directory=field):
                target = getattr(self, field)
                target.chmod(0o777)
                try:
                    with self.assertRaises(CTReviewRejected):
                        self.run_review()
                finally:
                    target.chmod(0o700)

    def test_readable_by_other_users_directory_rejected(self):
        self.review.chmod(0o755)
        with self.assertRaises(CTReviewRejected):
            self.run_review()

    def test_symlink_source_rejected(self):
        other = self.source / "original.fake"
        self.candidate.rename(other)
        self.candidate.symlink_to(other)
        with self.assertRaises(CTReviewRejected):
            self.run_review()

    def test_hardlink_rejected_with_valid_preparation(self):
        another = self.source / "linked.fake"
        another.hardlink_to(self.candidate)
        with self.assertRaises(CTReviewRejected):
            self.run_review()

    def test_symlink_directory_rejected(self):
        link = self.review.parent / "alias"
        link.symlink_to(self.review, target_is_directory=True)
        with self.assertRaises(CTReviewRejected):
            two_hop_review(
                source_dir=self.source, review_dir=link, second_dir=self.second,
                expected_sha256=self.digest, expected_size=len(ORIGINAL)
            )

    def test_duplicate_directory_rejected(self):
        with self.assertRaises(CTReviewRejected):
            two_hop_review(
                source_dir=self.source, review_dir=self.source, second_dir=self.second,
                expected_sha256=self.digest, expected_size=len(ORIGINAL)
            )

    def test_read_only_file_and_0700_parent_not_immutable(self):
        report = same_uid_post_review_mutation()
        self.assertTrue(report.later_writes_remain_possible)
        self.assertNotEqual(report.verified_sha256, report.later_sha256)
        self.assertFalse(report.installer_byte_identity_proven)
        self.assertFalse(report.installation_authorized)
        self.assertFalse(report.installation_performed)

    def test_no_installer_or_network_runtime_calls(self):
        import build70_ct_two_hop_delivery_lab as lab
        source = inspect.getsource(lab)
        for forbidden in ("subprocess.run(", "os.system(", "socket.connect(",
                          "requests.get(", "urllib.request."):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
