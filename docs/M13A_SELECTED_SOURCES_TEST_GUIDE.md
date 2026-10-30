# M13-A — Selected Keiyoushi ports: first live-device test

Status: **EXPERIMENTAL, PHYSICAL QA PENDING** — 2026-10-30.

This build adapts only **three of nine** requested Keiyoushi extensions. It is not a generic APK converter. The other six remain planned.

## First catalog

```
https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/keiyoushi-selected-repository.json
```

After the Build29 IPA is verified and installed via Sideloadly, open **Explorar → + → Inserir URL HTTPS**, paste the catalog above, then install each candidate. The earlier Demo repository and existing Library/Downloads should remain untouched.

| Source in catalog | Upstream original | Script path | Source-specific caveat |
| --- | --- | --- | --- |
| HotComics (experimental) | `src/en/hotcomics` | `fixtures/keiyoushi-hotcomics.js` | NSFW; HTML-based; login-required chapters cannot be accessed without authorization |
| Manhwa18.net (experimental) | `src/all/manhwa18net` | `fixtures/keiyoushi-manhwa18net.js` | NSFW; Inertia HTML `#app[data-page]` changes can break JSON parsing |
| Webtoons.com EN (experimental) | `src/all/webtoons` | `fixtures/keiyoushi-webtoons-en.js` | EN only; mobile episode API; motion toon unsupported |

## Test once per candidate

1. Install one source and open its Popular view; note titles, covers, or the **first exact error**.
2. Search a common permitted title. Check results and page progression if available.
3. Open manga details and chapter list.
4. Read a chapter where the site allows it. Verify whether image URLs load (not only JSON).
5. If a chapter opens, try a small download and reopen it offline.
6. Repeat for the other two sources and briefly check the existing Demo still works.
7. On HTTP 403/429 or other access controls, do not repeatedly retry or attempt bypasses. Report the exact error.

A compile PASS and mocked JavaScript tests are insufficient to validate real HTTP and WebKit parsing on iOS 12.5.8. In particular the MangaDex report previously demonstrated that Safari HTTPS availability does not guarantee URLSession HTTPS compatibility on the same device.

## Adapter design

- Original code reference: https://github.com/keiyoushi/extensions-source (Apache-2.0; see its LICENSE). These scripts are **unofficial adaptations**, not a port or distribution of Android APK binaries.
- The native `Native.htmlSelect` bridge accepts HTML and bounded CSS selector specifications, then invokes WebKit DOMParser against **inert markup** inside a local empty document. No site scripts are executed.
- Bounded HTML parsing queue, input/output limits and HTTP host allowlists prevent unexpected arbitrary requests; no Cloudflare bypass, authorization forgery, certificate override or globally insecure ATS exception.
- Manhwa18.net adapter extracts source-provided JSON from the Inertia data-page attribute; HotComics/Webtoons EN use CSS selectors derived from existing Kotlin parsers.
- Separate catalog SHA-256 pins verify each JS script before installation. New script versions must update hashes and source version together.
- Current selected domains: hotcomics.io; manhwa18.net; webtoons.com and pstatic.net. Hosts outside the selected source policy are not automatically approved.

## Scope / next milestone

The remaining selected extensions are Vortex Scans, ToonGod, Manhwa18.cc, Asura Scans, MadaraDex and Comix. Shared source engine ports will follow the M13 architecture after this initial physical integration test.


## Build29 real-device feedback and Build30 targeted fix — 2026-10-30

- **Webtoons.com EN**: source access and chapter images load; covers/series thumbnails missing.
- **Manhwa18.net**: source access and chapter images load; covers/series thumbnails missing.
- **HotComics**: server HTTP 403 (source unavailable on this device/network; no bypass or repeated retry).
- **Native defect**: CoverImageLoader's temporary HTTPClient was deinitialized before URLSession completed, which cancelled cover requests. Build30 retains it until completion and checks source host allowlist before cache access.
- **No source reinstall needed**: the selected scripts and the SHA-256 catalog were not changed. Install only the new IPA over the current app via Sideloadly.
- **Retest narrowly**: covers in source list and manga details (Webtoons.com EN and Manhwa18.net); verify one chapter still displays its pages and, if available, cover in Library.
- If a cover still fails, report the source and whether it fails only on list or also in manga details; examine actual cover host/HTTP status before allowing additional domain or changing headers.
- Do not keep retrying HotComics on HTTP403; access is restricted and remains out of physical acceptance.


## Webtoons EN v0.1.1 source-only list cover test

Physical Build30 result: Manhwa18.net series covers now display. Webtoons EN covers display within work details but not in lists. Webtoons JS v0.1.0 only consumed img.src on list cards, but details use og:image. New source-only v0.1.1 safely checks image lazy-load attributes and srcset before src. It does not guarantee the site actually provides these candidates or that the image host allows the fetch.

After source update is published, keep Build30 installed and refresh the existing selected Keiyoushi catalog. Update only Webtoons.com EN (v0.1.1); do not reinstall the application or other sources. Refresh Webtoons Popular and Search. Check thumbnails and then manga details. If list thumbnails remain blank, collect source and location (list vs details), and if necessary a targeted cover URL/status diagnostic in a later IPA batch. No repeated access retries or anti-bot bypass.


## Build31 — Webtoons EN list/detail cover diagnostic

User installed Webtoons.com EN source 0.1.1 on Build30; covers still absent on Popular/Search even while the selected work's detail cover is visible. Manhwa18.net covers now work.

Install Build31 without removing existing installed extensions. Open Webtoons.com EN, wait for Popular titles, tap `Testar capas` in the navigation bar, and `Copiar relatório`. Send the report with the list and detail cover results. This is a user-initiated read-only comparison of one source work: at most 2 direct image HTTPS GETs and 1 source details request. No request to HotComics; no MangaDex activity.

Interpretation guide:
- List cover URL absent -> inspect original listing markup/JS selector, do not change native network.
- Source list cover host rejected by manifest -> compare actual CDN host, request only narrowly justified changes.
- HTTP 200 and UIImage NO -> investigate MIME/format (e.g. WebP/AVIF) on iOS12; do not assume network failure.
- HTTP403/429 -> normal site decision; avoid bypass; stop on 429.
- HTTP200 and UIImage YES but no visual display -> inspect cover cache/cell reuse and source-specific presentation.
- Details cover succeeds while list fails -> compare reported hostname/content-type and source list semantics.

No manga titles, paths, URL query, cookies or image content are included in copied report.
