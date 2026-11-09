#!/usr/bin/env python3
"""Future Build69 phases AM/AN: owner-signed release discovery & private QA link.

The public GitHub releases route is UNSIGNED; an authenticated update route
must ONLY use the independently provisioned publisher key + SPKI SHA-256,
not the GitHub API's SHA256, an injected fixture key, or UI-supplied trust.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parent.parent
SIGNED = (ROOT / "MangaReader12/Core/WebReaderProductionSignedReleaseChecker.swift").read_text()
TRUST = (ROOT / "MangaReader12/Core/WebReaderProductionPublisherTrust.swift").read_text()
VERIFIER = (ROOT / "MangaReader12/Core/WebReaderUpdateManifestVerifier.swift").read_text()
GATE = (ROOT / "MangaReader12/Core/WebReaderSignedReleaseTrustGate.swift").read_text()
CHANNEL_NATIVE = (ROOT / "ci/test_native_webreader_release_channel_separation.py").read_text()
PUB = (ROOT / "MangaReader12/Core/WebReaderUpdateChecker.swift").read_text()
UI = (ROOT / "MangaReader12/UI/WebReaderAppUpdatesViewController.swift").read_text()
PROJECT = (ROOT / "MangaReader12.xcodeproj/project.pbxproj").read_text()
INSTALL = (ROOT / "MangaReader12/Core/WebReaderAppinstSocket.swift").read_text()
NATIVE = (ROOT / "ci/test_native_webreader_signed_production_discovery.py").read_text()


class ProductionSignedDiscovery(unittest.TestCase):
    def test_native_signed_transport_compiled_into_ios12_target(self):
        name = "WebReaderProductionSignedReleaseChecker.swift"
        self.assertEqual(PROJECT.count(f"{name} in Sources"), 2)
        self.assertEqual(PROJECT.count(f"{name} */ = {{isa = PBXFileReference"), 1)
        self.assertIn(f"A20000000000000000000042 /* {name} */,", PROJECT)
        self.assertIn(f"A10000000000000000000042 /* {name} in Sources */,", PROJECT)

    def test_network_is_impossible_without_owner_provisioned_signer(self):
        section = SIGNED.split("func check(completion", 1)[1].split("func cancel()", 1)[0]
        self.assertIn("guard WebReaderProductionPublisherTrust.isProvisioned else", section)
        self.assertIn("callback(.disabled)", section)
        self.assertIn("return", section)
        self.assertLess(
            section.index("guard WebReaderProductionPublisherTrust.isProvisioned else"),
            section.index("let connection = URLSession(")
        )
        for t in (
            'main/updates/channel-production-v2.json',
            'raw.githubusercontent.com/AugustoArbulu/MangaReader12/',
            'static let maximumResponseBytes = 64 * 1024',
            'URLSessionConfiguration.ephemeral',
            'config.httpShouldSetCookies = false',
            'config.urlCredentialStorage = nil',
            'config.httpCookieStorage = nil',
            'config.urlCache = nil',
            'config.httpMaximumConnectionsPerHost = 1',
            'request.httpMethod = "GET"',
            'request.setValue("application/json", forHTTPHeaderField: "Accept")',
        ):
            self.assertIn(t, SIGNED)

    def test_only_exact_https_source_full_bounded_json_and_no_redirects(self):
        self.assertIn("completionHandler(nil)", SIGNED)
        self.assertIn("http.url == WebReaderSignedProductionChannel.manifestURL", SIGNED)
        self.assertIn("http.statusCode == 200", SIGNED)
        self.assertIn('mime == "application/json" || mime == "text/json"', SIGNED)
        self.assertIn("response.expectedContentLength <=", SIGNED)
        self.assertIn("data.count <= limit - responseData.count", SIGNED)
        for forbidden in (
            "http.value(forHTTPHeaderField:",  # iOS13-only, forbidden iOS12
            "allowInvalidSSLCertificates", "httpShouldUsePipelining",
            "setValue(\"Bearer", "forHTTPHeaderField: \"Authorization\"",
            "forHTTPHeaderField: \"Cookie\"",
        ):
            self.assertNotIn(forbidden, SIGNED)

    def test_manifest_bytes_must_pass_compiled_production_gate(self):
        section = SIGNED.split("didCompleteWithError error:", 1)[1].split(
            "private func finish(", 1
        )[0]
        self.assertIn("WebReaderProductionPublisherTrust.inspectProductionManifestReadOnly(", section)
        self.assertIn("finish(.updateAvailable(preview.update))", section)
        self.assertIn("catch WebReaderUpdateValidationError.notNewer", section)
        self.assertIn("finish(.upToDate)", section)
        self.assertIn("finish(.failed(.invalidSignedManifest))", section)
        self.assertNotIn("WebReaderUpdateManifestVerifier.verify(", SIGNED)
        self.assertNotIn("publicKeyX963:", SIGNED)
        self.assertNotIn("independentlyTrustedSPKISHA256:", SIGNED)
        self.assertIn("static let independentlyProvisionedSPKISHA256: String? = nil", TRUST)
        self.assertIn("static let productionTrustGeneration = 0", TRUST)
        self.assertIn("static let productionPublicKeyX963: Data? = nil", PUB)
        self.assertIn("static let liveInstallationEnabled = false", INSTALL)

    def test_valid_dev_signature_does_not_authorize_production_metadata(self):
        self.assertIn('expectedChannel: String = "development"', VERIFIER)
        self.assertIn('manifest["channel"] as? String == expectedChannel', VERIFIER)
        self.assertIn('expectedChannel: String = "development"', GATE)
        self.assertIn('expectedChannel: expectedChannel', GATE)
        self.assertIn('expectedChannel: "production"', TRUST)
        self.assertIn("reject(dev, \"production\"", CHANNEL_NATIVE)
        self.assertIn("reject(prod, \"development\"", CHANNEL_NATIVE)
        self.assertIn("signed-v2 channel binding: dev/prod do not cross", CHANNEL_NATIVE)
        self.assertNotIn("productionTrustGeneration = 1", TRUST)

    def test_ui_separates_public_unsigned_signed_and_private_actions(self):
        self.assertIn("if source == 1 { return 5 }", UI)
        self.assertIn("Copiar diagnóstico do canal assinado", UI)
        self.assertIn("case (1, 2):", UI)
        self.assertIn("case (1, 3):", UI)
        self.assertIn("Verificar canal assinado", UI)
        self.assertIn("Abrir Builds privadas no GitHub Actions", UI)
        self.assertIn('https://github.com/AugustoArbulu/MangaReader12/actions', UI)
        self.assertIn("private func checkSignedProductionChannel()", UI)
        self.assertIn("guard WebReaderProductionPublisherTrust.isProvisioned else", UI)
        self.assertIn("Canal bloqueado: falta chave editorial e SPKI independente", UI)
        self.assertIn("WebReaderProductionSignedReleaseChecker(", UI)
        self.assertIn("self.lastResult = .updateAvailable(update)", UI)
        self.assertIn("Manifesto editorial ECDSA verificado", UI)
        self.assertIn("Manifesto assinado indisponível", UI)
        self.assertIn("self.lastResult = .disabled", UI)
        self.assertIn("signedChecker?.cancel()", UI)
        self.assertIn("!checking, !signedChannelBusy", UI)
        self.assertIn("sem token no aplicativo", UI)
        self.assertNotIn("WebReaderAppinstSocket.install(", UI)
        self.assertNotIn("GitHubPersonalAccessToken", UI)
        self.assertNotIn("SecItemAdd(", UI)

    def test_ephemeral_native_harness_does_not_install_trust(self):
        self.assertIn("productionPublicKeyX963: Data? = nil", NATIVE)
        self.assertIn("no publisher pin must deny before HTTP request", NATIVE)
        self.assertIn("editorial trust root intentionally absent", NATIVE)
        self.assertIn("never promote trust generation from the network", NATIVE)
        for token in ("appinst(", "posix_spawn(", "install(", "URLSession.shared"):
            self.assertNotIn(token, SIGNED + NATIVE)


if __name__ == "__main__":
    unittest.main()
