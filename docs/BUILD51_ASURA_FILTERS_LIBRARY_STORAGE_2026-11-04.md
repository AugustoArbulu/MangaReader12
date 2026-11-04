# Build 51 + Asura EN v0.1.3 — filtros remotos, Biblioteca fixada e armazenamento

**Data:** 2026-11-04. **Prioridade:** melhorias gerais estáveis no iOS 12.5.8 e filtros sem promessas falsas de exclusão de gêneros na Asura. **Branch:** `feat/build51-asura-filters-library-downloads`. **Base:** Build 50 aprovado em teste físico de leitura e capas da Asura EN 0.1.2.

## 1. O que já existia e foi preservado

- Biblioteca em **grade** ou lista, categorias, busca, ordenação, filtro não-lidos/downloaded, **Continuar lendo** com histórico.
- Downloads com fila serial, prioridade, pausar/retomar e recuperação, download offline, fila com ações em lote, verificação de imagens (PNG/JPEG/WebP).
- Fontes via catálogos isolados, sem carregar APK Android e sem atualizar fontes upstream automaticamente.
- Leitor iOS 12, WebP integrado, Webtoons, WeebCentral EN 0.1.6 e Asura EN 0.1.2 como ponto validado.

Não reconstruir recursos existentes, não migrar ou apagar Biblioteca/Downloads, não alterar TLS/cookies/Cloudflare/proteção premium.

## 2. Asura EN 0.1.3 — filtros REAIS no servidor

**Referência pública:** `keiyoushi/extensions-source/src/en/asurascans/.../Filters.kt` e `AsuraScans.kt`.

- `filterOptions` obtém **gêneros disponíveis** da página pública `https://asurascans.com/browse` por um GET HTTPS, extrai o campo inert Astro `availableGenres` via `Native.htmlSelect` sem executar scripts remotos.
- Mapeia **nomes para slugs exatos** anunciados pelo site, sanitiza os valores (máx. 60 gêneros, nomes <=50 caracteres, slug sem path/query). Um único GET por sessão; callbacks concorrentes são coalescidos.
- Falha segura: caso /browse não esteja disponível, mantém **status, tipo e ordenação** como opções; não inventa slugs ou faz requisições repetidas.
- `search` aceita somente chaves `includedTags`, `excludedTags`, `types`, `statuses`, `sort`, `order`. API pública recebe `genres=slug1,slug2`, `type`, `status`, `sort`, `order` e `offset/limit` **antes da paginação**. Até 12 gêneros incluídos, 1 tipo, 1 status. Listas, tipos, ordenações e slugs desconhecidos dão erro **antes do HTTP**.
- Ordenação: Latest Updates/`latest`, Popularity/`popular`, Rating/`rating`, A-Z/`title`, Recently Added/`update`; order `asc`/`desc`.
- **Exclusão remota de gênero NÃO suportada** pelo upstream: `excludedTags` é explicitamente recusado. O filtro da Asura permite só inclusão de gêneros. Não fingir que o app filtrou o catálogo inteiro após receber uma página de 20 títulos; não garantir exclusão BL/GL em obras sem classificação. Ainda é possível ocultar manualmente obras na interface.
- Preserva IDs canônicos, capas WebP, links públicos, capítulos premium omitidos, páginas `tiles` ainda não habilitadas.
- Versão e checksum do script fixados no catálogo `fixtures/asurascans-pilot-repository.json`: **0.1.3**. Fonte-only isolada, compatível com Build51.

## 3. Build51 — UX de filtros

A folha de filtros nativa reutilizada aceita capacidades opcionais por fonte: `supportsTagExclusions` (default **true** para WeebCentral) e `singleTypeStatus` (default **false**). Asura:
- Gêneros: **um toque inclui e outro remove** (sem falsa opção de exclusão).
- Tipo e status: **seleção única**; outro item substitui o anterior.
- Ordenação e ordem ascend./descend. via chips.
- O menu funciona mesmo sem gêneros obtidos: as opções de tipo/status/sort são mostradas, `tags: []` válido.
- Preserva a seleção independente por fonte no `UserDefaults`, sanitiza seleções antigas e recarrega primeira página ao mudar filtro.
- WeebCentral conserva a experiência atual de inclusão/exclusão de tags e seleção múltipla. Não alterar `main` sem testes.

## 4. Build51 — Biblioteca fixada

- `LibraryPinnedWorks` usa `UserDefaults` com **identidade sourceID + mangaID prefixada por comprimento**, impedindo colisões entre fontes.
- Lista: gesto lateral mostra **Fixar/Desfixar**; grade: toque longo na capa mostra o mesmo.
- Obras fixadas aparecem **antes das demais** em qualquer ordenação e exibem etiqueta visual **★ Fixada**, também na grade.
- Não cria tabela SQLite, não altera IDs de obras/capítulos, não remove histórico; funciona sem internet.
- Preferência específica do dispositivo por ora: **não integrada ao formato de backup**. Ao restaurar backup em instalação limpa, os marcadores podem não ser preservados. Não alegar migração/backup universal de favoritos.

## 5. Build51 — estimativa de armazenamento

- Aba Downloads mostra **contagem e tamanho estimado dos arquivos no diretório oficial de downloads** em Application Support.
- Enumeração somente de leitura, limitada a 10.000 arquivos, exclui ocultos/symlinks e não percorre fora da pasta.
- Cálculo em fila de baixa prioridade; **no máximo uma varredura a cada 30 segundos**, ou ao abrir/atualizar manualmente, evitando trabalho repetitivo no timer de atualizações a cada 1,5 s.
- Se o limite for atingido, apresenta `≥` para não fingir resultado exato. Nenhuma exclusão, limpeza automática ou upload.
- O número é uma **estimativa dos bytes de arquivos**, não o espaço físico exato reservado em APFS (metadados, blocos, compressão, caches externos).

## 6. Testes

- `ci/test_asurascans_offline.cjs` testa `/browse` Astro com gêneros dinâmicos, slugs, cache, fallback sem gênero, status/tipo/ordenação, exclusão e filtros inválidos sem requests, paginação original e todas as regressões de leitura/segurança.
- `ci/test_build51_general.py` executa o **código Swift real** dos dois helpers em macOS com fixture isolada: pin/unpin, colisões de IDs, arquivo oculto, contagem de bytes e truncamento visível.
- Pipeline continua com testes WeebCentral, ImageIO/libwebp, parser Astro, CBZ, iOS12, CI Debug/Release e IPA não assinada.
- **QA físico obrigatória**: CI não garante a API do site nem todos os gestos no iPad.

## 7. Teste no iOS 12.5.8

1. Instalar Build51 por cima do Build50 pelo Sideloadly **sem desinstalar**. Biblioteca e arquivos existentes devem continuar.
2. Na Asura experimental, atualizar o catálogo e fonte EN **0.1.3**. Abrir Filtrar e checar gêneros retornados do site, tipo/estado, ordenação; testar um filtro **Romance** ou **Action** combinado com **Ongoing**; mudar de página e confirmar que o filtro continua. Limpar e conferir a listagem original.
3. Conferir que as opções **excluir gênero** não são oferecidas para Asura; não alegar exclusão BL/GL. Se não houver gêneros, enviar mensagem sem inventar slugs e conferir status/tipo/sort.
4. Na WeebCentral EN 0.1.6, checar que seleção de inclusão/exclusão continua funcionando.
5. Na Biblioteca lista: fixar uma obra pelo gesto lateral e confirmar que sobe ao topo; em grade: segurar capa e desfixar, conferir sincronização.
6. Na aba Downloads: verificar estimativa de espaço, contagem, status; verificar que não some após voltar da tela. A leitura offline deve continuar sem `-1009`.
7. Testar uma capa e um capítulo de Asura ou WeebCentral para regressão rápida, mas não forçar repetidas solicitações a sítios indisponíveis.

## 8. Limites e próximas etapas

- Asura só aceita **gêneros incluídos**; não há negativo remoto. Novos métodos exigem evidência do servidor e testes.
- Migração entre fontes, backup com pins, política de Wi-Fi-only, seleção massiva de capítulos e alerta de atualização **não foram implementados aqui**. Alteram estado e exigem um projeto separado.
- Sem suporte a capítulos premium/cookies/WAF; imagens `tiles` continuam limitação documentada.
- Manter Build50 como referência fisicamente validada; branch -> testes -> PR -> squash merge para main; só depois compartilhar IPA.
