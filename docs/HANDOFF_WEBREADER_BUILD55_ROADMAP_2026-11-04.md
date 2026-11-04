# WebReader — checkpoint Build 55 e roadmap Build 56+

**Atualizado em:** 2026-11-04. **Sistema-alvo:** iOS 12.5.8, deployment target 12.0. **Repositório:** `AugustoArbulu/MangaReader12`. O nome exibido é **WebReader**, mas o executável e bundle ID `com.example.MangaReader12` permanecem inalterados para preservar os dados. **Baseline:** Build 55, PR [#86](https://github.com/AugustoArbulu/MangaReader12/pull/86), merge na `main` em `9657d235b959e5647893889d863be7a82365f355` com CI verde.

## Último aceite físico

O usuário reportou **“está funcionando”** na Build 55 instalada em iOS 12.5.8. Registrar como **aceite preliminar de funcionamento geral**, sem presumir que todas as nove fontes/ícones, modo avião, backups e stress de memória foram testados individualmente. A Build 54 também havia recebido avaliação positiva. Manter Build 55 como referência de rollback.

## Funcionalidades JÁ presentes — não duplicar

- Asura Scans EN 0.1.3, WeebCentral EN 0.1.6, Webtoons EN e outros adaptadores JS independentes de APKs Android. Controle de catálogo, instalação, ativação, rollback, HTTPS e SHA.
- Ícones Keiyoushi reais (9 PNGs locais da Build55) mapeados por IDs de fonte em `KeiyoushiSourceIconAssets` (`MangaArtwork.swift`). Manhwa18.net não deve receber o ícone de Manhwa18.com.
- Biblioteca SQLite com categorias, filtro, ordenação, fixação e histórico. Cada `LibraryMangaRecord` **já guarda `sourceID`** e `sourceMangaID`, portanto **não precisa migração do banco** para mostrar a origem.
- Feed `UpdateFeedStore`, `LibraryUpdateEvent`, verificação manual de novos capítulos, indicadores de não lidos. Background Fetch é oportunista.
- Downloads: lote **até cinco capítulos**, fila persistente serial, pausar, retomar, priorizar e leitura offline.
- Leitor com navegação paginada / rolagem Webtoon / escala, WebP nativo e ImageIO limitado; CBZ/ZIP local.
- Backup `.mr12backup` inclui Biblioteca e obras fixadas, não arquivos de capítulos baixados nem scripts de extensões.
- AVIF é identificado, **não decodificado**. Comix permanece investigação separada; não contornar Cloudflare/TLS/403.

> **ESTADO ATUAL (2026-11-04):** Build 56 com as entregas A/B aprovada em CI de branch/PR e integrada à `main` pelo PR #88 (`6c3bef88c...`). IPA iOS12 disponível para Sideloadly. **QA física ainda pendente**; a Build55 é a última referência aprovada pelo usuário. Handoff específico: [BUILD56_SOURCE_ATTRIBUTION_UPDATES_2026-11-04.md](BUILD56_SOURCE_ATTRIBUTION_UPDATES_2026-11-04.md).

## Build 56 — duas entregas combinadas (NOVO REQUISITO DO USUÁRIO)

### A. Identificação da fonte de **cada obra**

**Pedido expresso do usuário:** “adiciona as fontes que está sendo usada por cada obra também”.

- **Biblioteca em lista:** mostrar um rótulo visível como `Fonte: Asura Scans EN` para cada obra, preferencialmente com o ícone real já incluído na Build 55. Não substituir o título, contagem de não lidos ou marcador de obra fixada.
- **Biblioteca em grade:** mostrar o ícone correspondente e um nome compacto da fonte no card, mantendo títulos legíveis e suporte a telas pequenas do iOS 12. Não deixar rótulos sobrepostos à capa ou escondidos atrás de ações.
- **Ficha de detalhes:** exibir a fonte no cabeçalho ou metadados, junto ao nome e ícone quando houver, para o usuário saber a procedência antes de ler/baixar.
- **Fonte de verdade:** `record.sourceID` + `SourceLifecycleManager.installedSources()` / `InstalledSourceRecord.manifest.name`. Obter um dicionário `[sourceID: manifest]` **uma vez por refresh da Biblioteca**, não consultar ou requisitar fonte por célula. Usar `KeiyoushiSourceIconAssets.image(for: sourceID)` para ícone local conhecido; para fontes personalizadas respeitar `manifest.icon` validado com cache ou exibir nome sem ícone.
- **Fonte desinstalada/ausente:** não atribuir uma fonte parecida. Exibir `Fonte não instalada` com ID exato visível em detalhes/acessibilidade, ou o último rótulo persistido somente se houver dado confiável. A obra deve continuar na Biblioteca, sem apagar nada.
- **Múltiplas fontes:** duas obras com o mesmo título, mas source IDs diferentes, aparecem separadamente com origem própria. Não mesclar, migrar nem trocar automaticamente a fonte usada por qualquer obra.
- **Sem mudança de DB** e sem novos requests aos sites só para descobrir o nome. Preservar `sourceID`, `sourceMangaID`, progresso, downloads e backup. Acessibilidade deve ler o nome completo da fonte, mesmo se rótulo visual truncado.
- **QA:** testar lista, grade, detalhes; mesmas obras em Asura e WeebCentral; fonte desativada ou removida; fontes personalizadas sem ícone; offline; rolagem/reuso rápido de células; sem regressão dos filtros e obras fixadas.

### B. Novidades e Atualizações

- Diferenciar **novo capítulo detectado desde a última verificação** versus **capítulo não lido** (não são a mesma coisa). Nunca inferir “novo” de um simples contador de não lidos.
- Melhorar a visualização/agrupamento dos eventos da `UpdateFeedStore`, criar ação para reconhecer/dispensar novidades persistindo a preferência de maneira não destrutiva.
- Preservar feed após upgrade, histórico, data e leitura offline; falha da rede não gera evento falso.
- Não recriar a aba Updates nem um segundo banco/serviço de atualizações.

**Critério de aceite Build56:** ambos os recursos acima, testes offline e CI Xcode iOS12 Debug/Release, IPA não assinada; validação física antes de tornar a nova build referência. Se a origem por obra exigir mudanças maiores de UI, pode ser um PR preparatório na mesma Build56 sem considerá-la pronta antes de completar a etapa B.

## Builds posteriores (planejadas, NÃO implementadas por este handoff)

**Build 57 — Downloads:** evoluir ações sobre lote já existente, cancelamento seguro de itens pendentes, retry isolado, feedback claro de filas/completo/falhas, consistência dos arquivos após restart.

**Build 58 — Leitor:** avaliar corte de margens, páginas duplas, ajuste de escala e prefetch dentro da RAM limitada do iOS12; proteger leitura vertical Webtoon e páginas offline.

**Build 59 — Fontes:** aprimorar diagnósticos e ciclo de atualização dos ports, monitor upstream Keiyoushi somente leitura, considerar novos adaptadores somente com fontes autorizadas e fixtures.

**Futuro:** EPUB local, rastreadores AniList/MAL com autenticação opt-in, modo incógnito e estatísticas. Experimento AVIF apenas com imagem real demonstrada e codec estático iOS12 validado. Comix C2 fica em investigação separada, sem bypass de CAPTCHA, 403/503 ou TLS.

## Fluxo de desenvolvimento

1. Criar branch a partir da Build55 na `main`; nunca editar `main` diretamente.
2. Testes Swift/JS offline e Xcode 15.4 Debug/Release para iOS12, hashes e pacote IPA no GitHub Actions. Diferenciar CI verde de aceite físico.
3. Mudar somente scripts/catálogos JS? preferir atualizar sem IPA. Mudança nativa/UI/asset gera nova IPA e exige instalação sobre a anterior, sem desinstalar, mantendo bundle ID legado.
4. Atualizar este handoff e `PROJECT_STATE.md` após cada checkpoint. Preservar dados antigos, nunca apagar Biblioteca, downloads ou backups automaticamente.
