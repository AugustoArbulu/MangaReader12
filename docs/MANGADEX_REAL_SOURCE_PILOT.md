# MangaDex real-source pilot — Build 26

Status: JavaScript syntax + mocked adapter check PASS, Swift compile CI pending, real iOS 12 test PENDING.

This is an **unofficial**, experimental MangaDex integration for MangaReader12.
It is not a Tachiyomi/Keiyoushi APK extension, nor an affiliation with MangaDex.

## Install on iOS 12

1. Install a verified Build 26 IPA using the established Sideloadly workflow.
2. Explorar → + → Inserir URL HTTPS.
3. Paste the catalog URL:

   https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/repository-mangadex.json

4. Open the catalog and install "MangaDex (experimental)".
5. Explore the source, search an English title, open details, list chapters and try reading one English chapter.

The catalog is intentionally separate from the bundled Demo repository. Do not replace the Demo catalog.

## Scope and constraints

- Uses MangaDex public JSON API at https://api.mangadex.org.
- The adapter uses new optional JS callback-based async source methods; prior synchronous fixtures remain unchanged.
- Manga covers use uploads.mangadex.org; chapter images use the API-selected MangaDex@Home baseUrl with data-saver mode.
- The manifest permits *.mangadex.org and *.mangadex.network, with HTTPS and redirect allowlist checks enforced by HTTPClient.
- Dynamic CDN servers outside those domains are blocked safely, and a missing image is a legitimate pending integration problem; never expand to unrestricted domains.
- Pilot only returns the most recent 100 English chapters; no login, custom search filters, or multi-language chapter listing.
- MangaDex and scanlation groups must be credited; respect removals and do not monetize access to MangaDex-powered content.
- No captcha bypass or access-control evasion.

## Known distinction

Compile CI + simulated response tests do not verify production API permissions, CDN reachability, iOS 12 JavaScriptCore behavior, chapter image delivery, or download reliability. Real on-device validation is required before calling this integration functional.


## Build 26 first physical test: TLS error (-1200)

Opening MangaDex experimental source failed with Network transport error -1200 while loading the production API. The source was installed successfully, but the live integration remains unverified.

## Build 27 diagnostic instructions

1. On the iOS 12 device, open https://api.mangadex.org/ping in Safari and record whether it displays pong or a secure-connection warning.
2. Open Explorar -> MangaDex source -> Informações e dados da fonte -> Diagnosticar HTTPS do MangaDex.
3. Use Copiar relatório and share the result. It includes point OS version, API HTTPClient and system URLSession results, MangaDex home and independent HTTPS controls.
4. Compare results before designing a fix. Never bypass certificate checks, set NSAllowsArbitraryLoads, or silently switch to untrusted proxies.
5. The diagnostic makes read-only requests, does not change installed source data and does not fix the TLS problem by itself.

Reference: https://developer.apple.com/library/archive/technotes/tn2232/
