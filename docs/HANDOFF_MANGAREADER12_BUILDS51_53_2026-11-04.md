# HANDOFF ATUAL — MangaReader12 Builds 51–53 / Compatibilidade e Roadmap

**Data:** 2026-11-04 (America/Sao_Paulo). **Repositório:** `AugustoArbulu/MangaReader12`; branch estável: `main`. **HEAD após PR #83:** `4923420f918c57772037112c50f93995549b09f3`. **Dispositivo-alvo:** iOS 12.5.8; deployment target 12.0; macOS 14 / Xcode 15.4 para CI. **Nunca modificar main diretamente**: branch, testes, PR, CI verde, squash merge.

## 1. Ordem dos fatos: o que NÃO deve ser confundido

| Build | PR | Merge na main | Estado de validação |
| --- | --- | --- | --- |
| 49 | [#79](https://github.com/AugustoArbulu/MangaReader12/pull/79) | Sim | libwebp 1.6.0; leitura e capas foram reportadas funcionais após correção, com ressalvas de telas específicas tratadas no 50 |
| 50 | [#80](https://github.com/AugustoArbulu/MangaReader12/pull/80) | Sim | miniatura WebP reduzida; usuário declarou tudo aparentemente funcionando |
| 51 | [#81](https://github.com/AugustoArbulu/MangaReader12/pull/81) | `63b915bd8997dbcfb11fdabb0eb54f32608d9fce` | **usuário disse “tudo parece estar funcionando”**; aceite preliminar, não prova de cada gesto |
| 52 | [#82](https://github.com/AugustoArbulu/MangaReader12/pull/82) | `f424fcd2ac483d3765e95e1625e8acb9d8d04e1b` | CI branch/PR e pós-merge completos; **ainda sem teste físico** |
| 53 | [#83](https://github.com/AugustoArbulu/MangaReader12/pull/83) | `4923420f918c57772037112c50f93995549b09f3` | CI branch/PR completo; pós-merge automático e **QA física ainda a confirmar** |

Não confundir compilação/fixture offline com acesso legítimo ao site ou desempenho real no hardware antigo. Não alegar que a Build 53 foi fisicamente aprovada.

## 2. Funcionalidades presentes antes da Build 52

- Fontes principais para reteste: **Asura Scans EN 0.1.3**, **WeebCentral EN 0.1.6** e **Webtoons EN**. Scripts JS convertidos são independentes de APKs Keiyoushi.
- Asura: filtros públicos de gêneros por `/browse`, tipo, status e ordem, aplicados à busca remota antes da paginação. **Não suporta exclusão remota de gêneros**; não prometer remoção completa de BL/GL. Falha de /browse deve manter filtros de tipo/status/ordem.
- Biblioteca SQLite (categorias, filtros, progresso, histórico), leitor online/offline, WebP em páginas e capas, cache em memória/disco, fila de download serial com pausar/retomar/priorizar, e backups portáteis.
- Biblioteca: opção **Fixar/Desfixar** Build 51 via swipe na lista e pressionar na grade. Os pins são `UserDefaults` com identidade `sourceID + mangaID`, sem schema SQLite.
- A **seleção em lote de até cinco capítulos** JÁ EXISTE em `MangaDetailsViewController` com `ChapterBatchPickerViewController` e operações sequenciais: não reconstruir como recurso novo.
- A aba **Updates** JÁ EXISTE, com eventos `LibraryUpdateEvent`, armazenamento em `UpdateFeedStore` e rótulo **Novo**. A Biblioteca também mostra números de capítulos não lidos e filtros por estado.

## 3. Build 52 — Compatibility Engine

Código: `MangaReader12/UI/MangaArtwork.swift`, `MangaReader12/Networking/MR12WebPBridge.h`, `MangaReader12/UI/ReaderViewController.swift`. Testes: `ci/test_build52_image_engine.py` e extensão de `ci/test_build49_webp.py`. Documento: `docs/BUILD52_IOS12_IMAGE_COMPATIBILITY_ENGINE_2026-11-04.md`.

- `ImageCompatibilityDecoder.cover/page` centraliza o roteamento de imagem sem mudar URL/header/hosts/transporte.
- WebP usa libwebp **1.6.0** já instalada estaticamente via archive SHA256 pin. Capas até 420 px; páginas WebP muito grandes são **redimensionadas durante a decodificação** com buffer BGRA de saída limitado, sem alocar o RGBA original. Máximo 24M pixels de saída / até 32.768px de lado; no máximo 128M pixels de origem.
- JPEG/PNG/GIF/HEIC usam ImageIO do sistema **apenas se o dispositivo conseguir decodificar**. Pré-valida conteúdo, status completo, dimensão e limite, usa miniatura quando grande. Não faz fallback ilimitado para `UIImage(data:)` nos novos caminhos do leitor e capas.
- Até 20MiB de dados comprimidos por imagem (compatível com o HTTPClient). Decodificar uma página de 24M pixels ainda pode consumir ~96MiB apenas para BGRA, sem contabilizar outras alocações. Não elevar limite sem medição.
- **AVIF é identificado, não decodificado.** `libavif` exige codec AV1 (dav1d/libaom), build estático arm64 iOS12, análise de dependências/licenças/tamanho e testes de arquivos reais e adversariais. Não inventar compatibilidade ou incluir decoder pesado sem evidência de páginas AVIF encontradas.
- JPEG XL, HEIC em hardware incompatível, PDF, SVG e TLS moderno também não são resolvidos automaticamente. Cloudflare/403/503 e certificados -1200 não se resolvem com libwebp.

## 4. Build 53 — backup portátil de obras fixadas

Código: `MangaReader12/Core/BackupManager.swift` e `MangaReader12/UI/BackupViewController.swift`. Teste `ci/test_build53_backup_pins.py`; documentação `docs/BUILD53_BACKUP_PINNED_WORKS_2026-11-04.md`.

- O `.mr12backup` **mantém formatVersion 1** e agora suporta a preferência opcional `stringArray`. Backups antigos sem esse campo continuam decodificáveis.
- Chave de pins `library.pinned.sources.v1` é incluída entre preferências exportadas e restauradas. Limites: até 10.000 IDs, até 2.048 bytes UTF8 por ID.
- **Não inclui arquivos de capítulos baixados nem os scripts de extensões**. Restaurar os backups existentes usa fluxo de importação que substitui a base local e limpa downloads excluídos; não testar sobre única cópia de dados importantes.
- Não há migração de esquema SQLite; não há sincronização de pins entre dispositivos fora do backup manual.

## 5. Procedimento de QA físico com a nova IPA

1. Instalar **Build 53** por cima de 51, sem desinstalar, via Sideloadly; confirmar versão em Ajustes.
2. Testar capa e capítulo público de Asura e WeebCentral; navegar muitas páginas JPEG/PNG/WebP, inclusive capítulo vertical, conferir páginas brancas/ausentes e comportamento da memória.
3. Confirmar leitura **offline em modo avião** de capítulo previamente baixado; validação não deve acionar rede.
4. Confirmar Biblioteca, obras fixadas, favoritos no topo, categorias, filtros locais, gênero/status/ordem da Asura, fila de Downloads.
5. Em ambiente de teste seguro, fixar duas obras de fontes diferentes, criar/exportar backup, modificar pins e restaurar; verificar se pins originais voltam. **O restore atual apaga downloads locais excluídos do backup**.
6. Caso apareça AVIF, mandar diagnóstico só de **formato, MIME, HTTP, tamanho, host** (não URL completa, query, headers privados ou tokens). Não insistir em requisições após bloqueio.

## 6. Próximas prioridades de implementação (não duplicar recursos)

1. **QA física da Build 53** antes de elevá-la a nova referência totalmente aprovada; preservar Build 51/50 como rollback funcional.
2. **Formatos modernos**: investigar AVIF somente se surgirem respostas reais `image/avif` em fontes autorizadas. Experimento em branch isolada, codec e deps pinados, estático arm64, offline tests; não mesclar no leitor até prova.
3. **Downloads**: aprimorar seleção em lote *já existente* (cancelamento após capítulo, feedback e limites) sem disparar downloads automáticos. Testar estado SQLite/retomada.
4. **Biblioteca/Updates**: refinar indicadores de novidades usando o feed já existente, evitando afirmar “novo” para uma obra apenas pelo contador de não lidos.
5. Comix no iOS12: seguir investigação C2 separada, sem bypass CAPTCHA, sem relaxar TLS e sem requests agressivos a fonte indisponível.

## 7. Comandos e checkpoints

- Workflow: `.github/workflows/build.yml` executa Swift/JS offline, libwebp real em host, build iOS12 Debug e Release, gera **IPA não assinada** nos artifacts GitHub Actions. Arquivos IPA exigem novo build ao mudar Swift nativo.
- PR #82: `feat/build52-ios12-image-compatibility-engine`; merged squash `f424fcd...`. CI PR/passagem confirmados.
- PR #83: `feat/build53-backup-library-pins`; merged squash `4923420...`. CI PR/passagem confirmados.
- Atualizar `PROJECT_STATE.md` e o handoff atual sempre que nova build mudar a linha de base ou se um teste físico revelar incompatibilidade. Os documentos antigos são histórico.
- **Nunca fazer mudanças diretas em main; não publicar aprovação física sem relato do dispositivo.**
