#!/usr/bin/env python3
"""Phase CS offline tests: no network, actual appinst process or install."""
from dataclasses import asdict
import hashlib
import inspect
import unittest

import build70_cs_appinst_path_boundary_audit as audit


def fake_source():
    return "\n".join(marker for _, marker in audit.STEPS)


class AppinstBoundarySourceTests(unittest.TestCase):
    def test_step_order_in_synthetic_source(self):
        self.assertEqual(
            audit.identify_reference_steps(fake_source()),
            tuple(name for name, _ in audit.STEPS)
        )

    def test_reordered_source_rejected(self):
        text = fake_source()
        a, b = (marker for _, marker in audit.STEPS[:2])
        with self.assertRaises(audit.SourceAuditRejected):
            audit.identify_reference_steps(text.replace(a, "__A__").replace(b, a).replace("__A__", b))

    def test_missing_copy_rejected(self):
        text = fake_source().replace("copyItemAtPath:", "noCopyItemAtPath:")
        with self.assertRaises(audit.SourceAuditRejected):
            audit.identify_reference_steps(text)

    def test_absence_of_mutable_temp_mode_rejected(self):
        text = fake_source().replace("@0777", "@0700")
        with self.assertRaises(audit.SourceAuditRejected):
            audit.identify_reference_steps(text)

    def test_unpinned_forged_source_rejected(self):
        with self.assertRaises(audit.SourceAuditRejected):
            audit.audit_pinned_reference(fake_source().encode() * 40)

    def test_git_blob_hash_not_plain_sha1(self):
        content = b"example"
        self.assertNotEqual(audit.git_blob_sha1(content), hashlib.sha1(content).hexdigest())
        self.assertEqual(len(audit.git_blob_sha1(content)), 40)

    def test_pathname_swapped_after_closed_review_fd(self):
        x = audit.simulate_host_pathname_replacement()
        self.assertTrue(x.simulated_pathname_race_observed)
        self.assertEqual(x.checked_original_sha256, hashlib.sha256(audit.GOOD).hexdigest())
        self.assertEqual(x.final_named_source_sha256, hashlib.sha256(audit.EVIL).hexdigest())
        self.assertEqual(x.copied_file_sha256, x.final_named_source_sha256)
        self.assertNotEqual(x.checked_original_sha256, x.copied_file_sha256)

    def test_all_authorizations_remain_false(self):
        x = audit.simulate_host_pathname_replacement()
        for name in ("source_code_executed_on_device", "appinst_executed",
                     "ios12_runtime_verified", "installation_authorized",
                     "installation_performed"):
            with self.subTest(name=name):
                self.assertFalse(getattr(x, name))
        for name, field in audit.SourceReferenceObservation.__dataclass_fields__.items():
            if name in ("exact_installed_appinst_binary_identified",
                        "ios12_runtime_verified", "installer_consumes_verified_same_fd",
                        "immutable_installer_bytes_proven", "publisher_authenticated",
                        "user_consent_verified", "installation_authorized", "installation_performed"):
                self.assertFalse(field.default)

    def test_no_executable_install_or_network_in_script(self):
        text = inspect.getsource(audit)
        for marker in ("/usr/bin/appinst", "LSApplicationWorkspace(", "socket.connect(",
                       "subprocess.run(", "os.system(", "requests.get(", "urllib.request."):
            with self.subTest(marker=marker):
                self.assertNotIn(marker, text)

if __name__ == "__main__":
    unittest.main()
