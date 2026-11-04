# Build 55 — ícones oficiais de sources Keiyoushi para WebReader

**Data:** 2026-11-04. **Base:** Build 54; usuário confirmou funcionamento no iOS 12.5.8. **Branch:** `feat/build55-official-keiyoushi-source-icons`. Mantém mínimo iOS 12.0.

## Escopo

O usuário solicitou os ícones publicados no Keiyoushi, não as iniciais ilustrativas. Esta build incorpora **bytes idênticos** aos PNGs `ic_launcher.png` do repositório `keiyoushi/extensions-source` no commit `ee661f5233b346559fbdd53993d447c318c5aef0`. A imagem é colocada em `MangaReader12/Assets.xcassets/{Asset}.imageset/icon.png` e compilada no app.

| SourceManifest.id | Origem Keiyoushi | Asset | Git blob SHA-1 |
|---|---|---|---|
| `kei.asurascans.en` | `src/en/asurascans/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiAsuraScans` | `a38ffbc68c48079c97ffca069d9e3ff18290af5e` |
| `kei.weebcentral.en` | `src/en/weebcentral/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiWeebCentral` | `8cc011d9a951a4c7199a3f17eff8880ff9a1f5e2` |
| `kei.webtoons.en` | `src/all/webtoons/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiWebtoons` | `957cbe99b67ac7318ccaa0485d67e3c0655528f7` |
| `kei.hotcomics` | `src/en/hotcomics/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiHotComics` | `0549a3a8f580ef32e8cb7831b3fc6eecbfd2ea7a` |
| `kei.comix` | `src/en/comix/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiComix` | `c25865fac427afbea1e2bcd39e3c064d15470a20` |
| `kei.vortexscans` | `src/en/vortexscans/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiVortexScans` | `8f646462eb87992378ae423a7a5d755f7bdca5c7` |
| `kei.toongod` | `src/en/toongod/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiToonGod` | `7c788a87596d26cf61677dc9d2bee8b89f06d608` |
| `kei.madaradex` | `src/en/madaradex/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiMadaraDex` | `d77ac49d0d51b430f20f8416315b676615204545` |
| `org.mangareader12.mangadex` | `src/all/mangadex/res/mipmap-xxxhdpi/ic_launcher.png` | `KeiMangaDex` | `ab5b8b0e8f455580375711d7a01024fa59e254ff` |

- `MangaReader12/UI/MangaArtwork.swift`: `KeiyoushiSourceIconAssets` mapeia o ID estável da source para o asset, que carrega com `UIImage(named:)`. O `SourceIconCell` prefere a imagem local e não consulta a rede para esses IDs.
- `MangaReader12/UI/MainTabBarController.swift`: tanto a lista de sources instaladas quanto o catálogo usam o mesmo ID para escolher o ícone. A interface exibe Build 55.
- Fontes **não mapeadas** preservam o comportamento anterior: ícone HTTPS se a source declarou `manifest.icon` ou, como último fallback, iniciais. Mantido o controle de reutilização assíncrona de células por URL **e** ID.
- Mantém `com.example.MangaReader12`, leitores, SQLite, backups e download sem mudanças e preserva o nome WebReader.
- `ci/test_build55_source_icons.py`: confere tamanho/dimensões de PNG, hash Git exato da imagem de origem, manifesto assetcat e integração UI; o CI ainda executa as regressões iOS12 Debug/Release e IPA.

### Distinção crítica: Manhwa18.net
O ícone publicado em `src/en/manhwa18` refere-se à fonte **manhwa18.com** no upstream, que não equivale necessariamente à `kei.manhwa18net` da nossa fonte. Para evitar associação errada, não há mapeamento inventado: esta source mantém ícone declarado/fallback até encontrarmos correspondência Keiyoushi exata.

### Proveniência e uso
O repositório Keiyoushi publica código sob Apache-2.0; logotipos/ícones podem conter marcas de terceiros. O WebReader não é afiliado ao Keiyoushi nem aos sites das fontes. A origem de cada PNG foi preservada e os bytes conferidos pelos hashes de blob.

## Teste físico
1. Instalar a nova IPA sobre a Build54, usando mesma assinatura, sem remover o app antigo.
2. Explorar → fontes instaladas: conferir Asura Scans, WeebCentral e Webtoons com os símbolos **reais** mesmo sem internet; testar também catálogo de repositórios.
3. Rolar rápido e voltar da lista, para assegurar que o reuso de células não mistura ícones.
4. Em fontes não mapeadas, validar `manifest.icon` ou fallback, sem exibir ícone de fonte diferente.
5. Conferir Biblioteca, leitura WebP online/offline, filtros Asura e downloads.

**Estado atualizado (2026-11-04):** usuário confirmou **“está funcionando”** no iOS 12.5.8 (aceite preliminar, não validação exaustiva de cada ícone). PR #86 aprovado em CI e integrado à `main`, commit `9657d235b959e5647893889d863be7a82365f355`. **Build 56 prevista:** mostrar junto a cada obra a fonte a que pertence, incluindo nome, ícone oficial quando mapeado e identidade correta em lista e grade. Consulte [HANDOFF_WEBREADER_BUILD55_ROADMAP_2026-11-04.md](HANDOFF_WEBREADER_BUILD55_ROADMAP_2026-11-04.md). AVIF continua não decodificado.
