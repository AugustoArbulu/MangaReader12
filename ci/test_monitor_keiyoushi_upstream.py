#!/usr/bin/env python3
"""Offline tests for the read-only Keiyoushi monitor (no GitHub traffic)."""
import json
from pathlib import Path
import tempfile
import unittest
from monitor_keiyoushi_upstream import read_baseline, compare, markdown, latest_commit


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.baseline = read_baseline("ci/keiyoushi-upstream-baseline.json")

    def test_baseline_paths_and_sha(self):
        self.assertEqual(len(self.baseline["entries"]), 12)
        self.assertEqual(len({x["path"] for x in self.baseline["entries"]}), 12)

    def test_missing_and_changed_classification(self):
        entries = self.baseline["entries"]
        current = {
            entries[0]["path"]: {"sha": entries[0]["sha"], "date": "2026-11-01"},
            entries[1]["path"]: {"sha": "a" * 40, "date": "2026-11-02"},
        }
        rows = compare(self.baseline, current)
        self.assertEqual(rows[0]["status"], "unchanged")
        self.assertEqual(rows[1]["status"], "review")
        self.assertEqual(rows[2]["status"], "error")
        report = markdown(self.baseline, rows, {}, "2026-11-01T00:00:00Z")
        self.assertIn("Needs review: 1", report)
        self.assertIn("Read-only report", report)

    def test_safe_github_target_and_credentials_not_in_output(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, count):
                self_count = count
                self_size = len(b"test")
                assert self_count >= self_size
                return json.dumps([{
                    "sha": "c" * 40,
                    "commit": {"committer": {"date": "2026-11-02T00:00:00Z"}}
                }]).encode()

        def fake_open(request, timeout):
            self.assertTrue(request.full_url.startswith(
                "https://api.github.com/repos/keiyoushi/extensions-source/commits?"
            ))
            self.assertIn("path=src%2Fen%2Fcomix", request.full_url)
            self.assertEqual(request.get_header("Authorization"), "Bearer secret")
            self.assertEqual(timeout, 20)
            return Response()

        got = latest_commit(self.baseline["entries"][0], token="secret", opener=fake_open)
        self.assertEqual(got["sha"], "c" * 40)
        self.assertNotIn("secret", json.dumps(got))

    def test_malformed_baseline_is_rejected(self):
        doc = dict(self.baseline)
        doc["entries"] = [dict(self.baseline["entries"][0], path="../secrets")]
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "invalid.json"
            file.write_text(json.dumps(doc))
            with self.assertRaises(ValueError):
                read_baseline(file)


if __name__ == "__main__":
    unittest.main()
