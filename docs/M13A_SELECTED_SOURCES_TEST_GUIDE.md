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
