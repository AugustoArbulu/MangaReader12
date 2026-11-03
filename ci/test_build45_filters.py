#!/usr/bin/env python3
"""Build45 source-filter UI integration regression checks (offline, no network)."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parent.parent


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


class Build45RemoteFilters(unittest.TestCase):
    def test_app_version_and_existing_reader(self):
        pbx = read("MangaReader12.xcodeproj/project.pbxproj")
        view = read("MangaReader12/UI/MainTabBarController.swift")
        self.assertEqual(pbx.count("CURRENT_PROJECT_VERSION = 45;"), 2)
        self.assertIn("Build 45 • compatível com iOS 12.0", view)
        # Native chapter and image caps from Build44 must remain.
        runtime = read("MangaReader12/SourceRuntime/JavaScriptSourceRuntime.swift")
        self.assertIn('name === "chapters" ? 4000', runtime)
        self.assertIn('name === "images" ? 1500', runtime)

    def test_generic_remote_metadata_and_tag_controls(self):
        ui = read("MangaReader12/UI/SourceBrowserViewController.swift")
        for expected in [
            "private struct SourceRemoteFilterOptions: Decodable",
            "private struct SourceRemoteFilterSelection: Codable, Equatable",
            "remoteFilterOptions: SourceRemoteFilterOptions?",
            'runtime.callDecoded(\n            "filterOptions"',
            'exclusions: excludedTags,',
            'remoteOptions: remoteFilterOptions,',
            'remoteSelection: remoteFilters,',
            '"discover.remote.tag."',
            '"discover.remote.type."',
            '"discover.remote.status."',
            '"discover.remote.sort."',
            '"discover.remote.order."',
            'self.remoteFilters != remoteSelection',
            'UserDefaults.standard.set(\n                    data, forKey: "explore.remote."',
            '"excludedTags": excludedTags',
            '"includedTags": includedTags',
            'self.loadFirstPage()',
            'query ?? "", page,',
            'remoteFilters.arguments(fallbackSort: fallbackSort)',
            'remoteSelection = SourceRemoteFilterSelection()'
        ]:
            self.assertIn(expected, ui, expected)
        self.assertIn('self.remoteFilters = self.remoteFilters.sanitized(for: options)', ui)
        self.assertIn('if remoteFilterOptions != nil && remoteFilters.hasActiveFilters', ui)
        self.assertIn('sourceRecord.manifest.id == "kei.webtoons.en"', ui)

    def test_source_support_is_server_side_only(self):
        source = read("fixtures/keiyoushi-weebcentral-en.js")
        version = re.search(r"var version = '(\\d+)\\.(\\d+)\\.(\\d+)';", source)
        self.assertIsNotNone(version, "WeebCentral version must be numeric")
        self.assertGreaterEqual(tuple(map(int, version.groups())), (0, 1, 3))
        import json
        catalog = json.loads(read("fixtures/weebcentral-pilot-repository.json"))
        self.assertEqual(catalog["sources"][0]["version"], ".".join(version.groups()))
        self.assertIn("filterOptions: filterOptions", source)
        for param in ("excluded_tag", "included_tag", "included_type", "included_status",
                      "sort", "order"):
            self.assertIn(param, source)
        for tag in ("Romance", "Action", "Horror", "Yaoi", "Yuri", "Other"):
            self.assertIn("'" + tag + "'", source)
        self.assertIn("validatedFilters(rawFilters)", source)
        self.assertIn("throw new Error('Unknown filter: '", source)
        self.assertNotIn("document.cookie", source)
        self.assertNotIn("Cloudflare", source)
        self.assertNotIn("XMLHttpRequest", source)

    def test_ci_integration(self):
        workflow = read(".github/workflows/build.yml")
        self.assertIn("node ci/test_weebcentral_offline.cjs", workflow)
        self.assertIn("python3 ci/test_build45_filters.py", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
