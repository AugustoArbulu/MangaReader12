# M13 — Nine selected Keiyoushi extensions for MangaReader12

Status: **source audit and scoped port plan only** (2026-10-30). The port is **not yet implemented**; do not mark these sources as working or build a public catalog from upstream Kotlin/APK files.

## Project decision

Convert **only these nine** user-selected sources. Do not attempt to execute Android APKs or mirror the entire Keiyoushi repository. The official upstream repository is https://github.com/keiyoushi/extensions-source (Apache-2.0). A converted source must instead ship a MangaReader12 API v1+ manifest JSON and HTTPS JavaScript file, with a reviewed per-source host allowlist, integrity hash and explicit iOS 12 device QA.

"Webtoon" is interpreted provisionally as **Webtoons.com** at upstream path `src/all/webtoons`; this is separate from `webtoonscan` and `webtoonxyz` sources. If the user meant one of those, change the mapping explicitly rather than silently replacing it.

## Exact upstream module inventory

| User-selected source | Keiyoushi module path | Upstream engine/dependency | Approximate first-pass port concern |
| --- | --- | --- | --- |
| Comix | `src/en/comix` | Bespoke `Comix.kt` (about 52k characters) + multiple supporting files; Android WebView, OkHttp, custom image code | **Very high**; Android-specific WebView and source/network restrictions; do not promise viability |
| Asura Scans | `src/en/asurascans` | Bespoke API adapter, DTO, filters and image-processing interceptor | **High**; API mapping and scrambled image path need safe handling |
| Webtoons.com | `src/all/webtoons` | Bespoke source, HTML parsing, multiple official language variants, text interceptor | **Medium-high**; language, images/referer, compliant web transport |
| Vortex Scans | `src/en/vortexscans` | Small subclass of `lib-multisrc/iken` (shared Iken parser) | **Medium**; wrapper tiny, Iken engine not yet ported |
| MadaraDex | `src/en/madaradex` | `lib-multisrc/madara` plus site-specific cookie/auth refresh | **High**; Madara reuse but site authorization/access controls may preclude adaptation |
| HotComics | `src/en/hotcomics` | Bespoke Jsoup HTML parser / cookies | **Medium**; HTML parser/headers and page image loading; NSFW |
| Manhwa18.net | `src/all/manhwa18net` | Bespoke Jsoup source, DTO and rate limiting | **Medium**; pagination/pages, low-rate requests; NSFW |
| ToonGod | `src/en/toongod` | Tiny subclass of `MadaraNoAjax` in `lib-multisrc/madara` | **Medium-high**; must first port shared MadaraBase/NoAjax |
| Manhwa18.cc | `src/all/manhwa18cc` | Tiny subclass of `lib-multisrc/yiimadara` | **Medium**; YiiMadara parser first; English/Korean/all variants, NSFW |

These are **engineering estimates from the code structure, not verified operational availability or rankings of the original sites**. Keiyoushi Gradle declarations identify HotComics, Manhwa18.net and Manhwa18.cc as NSFW; Comix, MadaraDex and ToonGod as MIXED. Respect adult-content platform rules.

## Engine grouping / reuse

- **Madara family**: ToonGod (`MadaraNoAjax`) and MadaraDex (`Madara`) share much of `MadaraBase` but use different listing/authorization flows. The shared Kotlin files are `Madara.kt`, `MadaraBase.kt`, `MadaraNoAjax.kt`, `Models.kt`, `Filters.kt`. Port one safe parser module before individual adapters.
- **Iken**: Vortex Scans is currently a short adapter over `lib-multisrc/iken/Iken.kt`; need Iken data models, API transport and filters rather than copying only the wrapper.
- **YiiMadara**: Manhwa18.cc uses `lib-multisrc/yiimadara/YiiMadara.kt`; do not confuse this engine with WordPress Madara.
- **Independent**: Webtoons.com, HotComics and Manhwa18.net have their own HTML/API parsers. Asura Scans uses site-specific API and image transformations; Comix adds Android-specific implementations.

## Cohesive implementation packages (no one-IPA-per-source churn)

1. **M13-A / foundation and independent pilot**: add a bounded, tested HTML DOM/selectors bridge or equivalent native parser suitable for JSCore and iOS12, domain/cookie/referer handling without ATS bypass, per-source rate limiting, per-source integration fixtures and clear HTTP/TLS error reporting. Attempt HotComics, Manhwa18.net and the supported English Webtoons.com flow in one source pack; only distribute scripts whose contract tests pass. The physical gate is one IPA if and only if the native bridge changes.
2. **M13-B / shared engines**: port reusable parts of MadaraBase/NoAjax (ToonGod), Iken (Vortex Scans), YiiMadara (Manhwa18.cc), with typed DTO mapping and selector tests. Add MadaraDex only after authorization requirements have been evaluated; do not forge auth to bypass access checks.
3. **M13-C / complex implementations**: Asura Scans image processing and API, MadaraDex remaining permissible integration, and Comix last due to its Android WebView usage and separate anti-third-party history. Leave any unsupported source flagged unsupported rather than bypass site controls.
4. **M13-D / updates**: pin per-source version, content hash, ownership attribution, allowlist, and upstream source commit; use GitHub Actions to inspect changes and run fixtures. Upstream Android APK updates are **not** automatically usable and conversion is never claimed until port tests pass.

## Physical-test and release gates

- The currently tested device is iOS 12.5.8. The MangaDex trial produced TLS `-1200` with underlying `-9836` in URLSession while Safari /ping worked. This may recur on selected sites: do not assume the domain is reachable solely because Safari works.
- When building new adapters, first do **non-invasive HTTPS preflight** for exact selected domains. Preserve platform/system certificate validation and do not add global ATS exceptions.
- Source-level tests: syntax, contract metadata/popular/search/details/chapters/pages, predictable empty/errors, bounded pagination, rate limit, protected image host rules, iOS12 appropriate memory/timeout behavior.
- Real-device acceptance only after install, one search, details, latest chapters, at least one authorized chapter image/page and reader/download where permitted.
- Store script+catalog in a reviewed dedicated JS repository path; **do not attempt to use `https://github.com/keiyoushi/extensions/raw/repo/index.pb` as MangaReader12 catalog**.
- Do not promise a private raw.githubusercontent.com repository as a workable unauthenticated installation URL. A private GitHub file requires suitable authenticated delivery and security design.

## Source code links

- https://github.com/keiyoushi/extensions-source/tree/main/src/en/comix
- https://github.com/keiyoushi/extensions-source/tree/main/src/en/asurascans
- https://github.com/keiyoushi/extensions-source/tree/main/src/all/webtoons
- https://github.com/keiyoushi/extensions-source/tree/main/src/en/vortexscans
- https://github.com/keiyoushi/extensions-source/tree/main/src/en/madaradex
- https://github.com/keiyoushi/extensions-source/tree/main/src/en/hotcomics
- https://github.com/keiyoushi/extensions-source/tree/main/src/all/manhwa18net
- https://github.com/keiyoushi/extensions-source/tree/main/src/en/toongod
- https://github.com/keiyoushi/extensions-source/tree/main/src/all/manhwa18cc
