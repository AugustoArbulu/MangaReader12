#!/usr/bin/env python3
"""CR adversarial tests. Files and child process remain in temp lab only."""
from dataclasses import fields, replace
from pathlib import Path
import hashlib
import inspect
import unittest

from build70_cr_fd_alias_lab import (
    EVIL, GOOD, FdAliasLabRejected, observe_swapped_path, _alias,
)


class CRFdAliasTests(unittest.TestCase):
    def test_parent_name_swapped_child_preserves_original_descriptor(self):
        result = observe_swapped_path()
        self.assertEqual(result.original_sha256, hashlib.sha256(GOOD).hexdigest())
        self.assertEqual(result.child_alias_sha256, result.original_sha256)
        self.assertEqual(result.pathname_after_swap_sha256, hashlib.sha256(EVIL).hexdigest())
        self.assertNotEqual(result.pathname_after_swap_sha256, result.child_alias_sha256)
        self.assertTrue(result.pathname_swap_resisted)
        self.assertTrue(result.host_fd_alias_supported)

    def test_child_without_fd_inheritance_fails_closed(self):
        with self.assertRaises(FdAliasLabRejected):
            observe_swapped_path(forward_fd=False)

    def test_observation_never_authorizes(self):
        observation = observe_swapped_path()
        for field in ("ios12_verified", "appinst_fd_alias_compatible", "appinst_used",
                      "immutable_install_bytes_proven", "publisher_authenticated",
                      "consent_verified", "install_authorized", "installation_performed"):
            with self.subTest(field=field):
                self.assertFalse(getattr(observation, field))
        self.assertTrue(getattr(observation, "host_fd_alias_supported"))

    def test_child_alias_does_not_reference_source_path(self):
        alias = _alias(17)
        self.assertTrue(alias.endswith("/17"))
        self.assertNotIn("candidate.fake", alias)

    def test_no_install_or_network_capabilities_in_lab(self):
        import build70_cr_fd_alias_lab as lab
        source = inspect.getsource(lab)
        for forbidden in ("/usr/bin/appinst", "requests.get(", "urllib.request",
                          "socket.connect(", "codesign --force", "os.system("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

if __name__ == "__main__":
    unittest.main()
