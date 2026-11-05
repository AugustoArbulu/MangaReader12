#!/usr/bin/env python3
"""Build43 C2 safety contract. Static guardrails only; not a device or site test."""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent

def read(path):
    return (ROOT / path).read_text(encoding="utf8")


class ComixC2Contract(unittest.TestCase):
    def test_isolated_webview_requires_user_gesture(self):
        s = read("MangaReader12/UI/ComixBrowserProbeViewController.swift")
        self.assertIn('URL(string: "https://comix.to/")', s)
        self.assertIn("configuration.websiteDataStore = .nonPersistent()", s)
        self.assertIn("guard !hasOpened else { return }", s)
        open_start = s.index("@objc private func openTapped()")
        copy_start = s.index("@objc private func copyResultTapped()")
        before_open, open_body, after_open = (
            s[:open_start], s[open_start:copy_start], s[copy_start:]
        )
        self.assertIn("webView.load(URLRequest(url: Self.startURL))", open_body)
        self.assertNotIn("webView.load(", before_open)
        self.assertNotIn("webView.load(", after_open)
        self.assertIn("openButton.addTarget(self, action: #selector(openTapped)", s)
        self.assertIn("openButton.isEnabled = false", open_body)

    def test_no_automation_or_privileged_bridge(self):
        s = read("MangaReader12/UI/ComixBrowserProbeViewController.swift")
        forbidden = [
            "evaluateJavaScript(", "WKUserScript(", "WKScriptMessageHandler",
            "addUserScript(", "URLSession(", "httpShouldSetCookies",
            "customUserAgent =", "javaScriptEnabled = false",
            "allowsArbitraryLoads", "didReceive challenge:", "credentialForTrust",
            "setValue(", "URLProtocol", "document.cookie",
        ]
        for term in forbidden:
            self.assertNotIn(term, s, term)
        self.assertIn("url.scheme?.lowercased() == \"https\"", s)
        self.assertIn('normalized == "comix.to"', s)
        self.assertIn('normalized.hasSuffix(".comix.to")', s)
        self.assertIn('normalized == "comix.ws"', s)
        self.assertIn('normalized.hasSuffix(".comix.ws")', s)
        self.assertIn("decisionHandler(.cancel)", s)
        self.assertIn("decisionHandler(.allow)", s)
        self.assertIn("navigationResponse.isForMainFrame", s)
        self.assertIn("navigationResponse.response.url", s)

    def test_report_does_not_copy_site_data(self):
        s = read("MangaReader12/UI/ComixBrowserProbeViewController.swift")
        self.assertIn("case 403, 429, 500, 503:", s)
        self.assertIn("observedHTTPStatus", s)
        self.assertIn("UIPasteboard.general.string", s)
        self.assertIn("nsError.domain", s)
        self.assertIn("nsError.code", s)
        self.assertNotIn("nsError.userInfo", s)
        self.assertNotIn("webView.url?.absoluteString", s)
        self.assertIn("browser?.stopLoading()", s)

    def test_integrated_and_version_pinned(self):
        main = read("MangaReader12/UI/MainTabBarController.swift")
        project = read("MangaReader12.xcodeproj/project.pbxproj")
        workflow = read(".github/workflows/build.yml")
        self.assertIn("ComixBrowserProbeViewController()", main)
        settings = main[main.index("final class SettingsViewController"):]
        # Build56 had 8 rows; updater's separate release screen adds row 9.
        # The Comix manual WebView action must remain present at the same index.
        self.assertTrue("return 8" in settings or "return 9" in settings)
        self.assertIn("case 6:", settings)
        self.assertIn("ComixBrowserProbeViewController()", settings)
        self.assertIn("ComixBrowserProbeViewController.swift in Sources", project)
        import re
        version_values = re.findall(r"CURRENT_PROJECT_VERSION = ([0-9]+);", project)
        self.assertEqual(len(version_values), 2)
        self.assertEqual(version_values[0], version_values[1])
        self.assertGreaterEqual(int(version_values[0]), 43)
        self.assertIn(
            f"Build {version_values[0]} • compatível com iOS 12.0", main
        )
        self.assertIn("IPHONEOS_DEPLOYMENT_TARGET = 12.0;", project)
        self.assertIn("python3 ci/test_comix_c2_contract.py", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
