# HANDOFF COMPLETO — MangaReader12 iOS 12.5.8 — 2026-11-03

**Projeto:** APP para iOS 12 parecido com Mihon  
**Repositório:** https://github.com/AugustoArbulu/MangaReader12  
**Branch estável:** `main`; nunca publicar mudanças diretamente nela — usar branch de recurso, CI verde e merge squash  
**Dispositivo de QA:** iOS **12.5.8** (não assumir iPhone versus iPad)  
**Ponto de partida deste handoff:** Build **46**, com WeebCentral EN **0.1.5** e Asura EN **0.1.1** em **catálogos experimentais isolados**.  
**Orientação do usuário:** quer **WeebCentral e Asura como duas fontes completas**, com busca, Biblioteca, detecção de atualizações e downloads offline, como Webtoons.com. Pediu progresso amplo enquanto dorme, com testes físicos apenas depois.

## 1. Evidências físicas comprovadas pelo usuário

A evidência mais importante é a melhora efetiva da **WeebCentral**, não apenas testes mocks.

| Etapa | Relato físico iOS 12.5.8 | Estado |
| --- | --- | --- |
| WeebCentral 0.1.0 | títulos apareciam, mas capas não e páginas rejeitadas por host | diagnosticado |
| 0.1.1 | capas ainda faltavam; erro `no page images matched...` | diagnosticado |
| 0.1.2 | **capítulos abrem e imagens aparecem** | confirmado |
| Build 44 | *One Piece* passou de capítulos 998–1197 (exatos 200) para **capítulo 1 como mais antigo** | confirmado para essa obra |
| Build 45 + 0.1.3 | filtros gerais de inclusão/exclusão da fonte **parecem ter funcionado**, segundo o usuário | observação positiva, sem matriz completa |
| 0.1.4 | **gêneros aparecem nos detalhes** | confirmado pelo usuário |
| 0.1.5 | novas datas ISO dos capítulos | só testes offline; não testado pelo usuário |
| Build 46 | nova verificação de integridade de download | CI aprovado; não testado fisicamente |
| Asura 0.1.1 | busca pública, detalhes/chapters Astro, IDs estáveis, segurança de tiles/premium | **sem QA físico** |

**Não extrapolar:** capítulo 1 de *One Piece* visível não prova que todo capítulo intermediário está presente; filtros aparentemente funcionando não comprovam classificação perfeita; imagens online não garantem downloads offline.

## 2. O que foi feito nesta rodada

### PR #70 — WeebCentral EN 0.1.5: data dos capítulos

https://github.com/AugustoArbulu/MangaReader12/pull/70

- Mantém URLs/IDs e ordem já validada no Build 44.
- `source.chapters` agora preserva `time[datetime]` em ISO-8601 (ex.: `2026-10-29T20:05:15.069Z`) quando presente e válido, antes sempre `null`.
- Não inventa datas para capítulos sem atributo. Não faz requests extras.
- Testes offline verificam timestamps com precisão e integridade dos IDs.
- Catálogo experimental atualizado com SHA-256.
- **Source-only:** não exige nova IPA.

### PR #71 — Asura Scans EN 0.1.0: primeiro adaptador público e Astro

https://github.com/AugustoArbulu/MangaReader12/pull/71

- Criado `fixtures/keiyoushi-asurascans-en.js` (iOS12/JSCore ES5) e catálogo isolado.
- `metadata`, `popular`, `search`, `details`, `chapters`, `pages`; categorias Populares e Recentes.
- `GET https://api.asurascans.com/api/series` para listagens públicas, `limit=20`, `offset=(page-1)*20`.
- Dados da obra/capítulos extraídos de `props` serializados do Astro usando `Native.htmlSelect` **inerte**. Não roda JavaScript remoto da página.
- Detalhes e capítulos abertos simultaneamente compartilham **um GET** por obra, cacheando os `props` por 30 segundos.
- Ignora capítulos com `is_premium`, `is_locked` ou janela `early_access_until` ativa/ambígua. Não usa `access_token`, cookies autenticados, `Authorization` nem `X-Page-Token`.
- Páginas com `tiles` não são entregues nem baixadas como imagens legíveis; capítulo falha explicitamente. Hosts de imagens externos desconhecidos são recusados com diagnóstico só do hostname.
- Corrigido caso sutil do desempacotamento Astro: permutação `tiles: [1,0]` não pode virar número por confusão com array tipado. Metadata inválida também falha fechada.
- Suíte `ci/test_asurascans_offline.cjs` cobre JSON, Astro, premium, tiles, HTTP403, redirecionamento, CDN e integridade do catálogo.

### PR #72 — Build 46: integridade de imagens baixadas

https://github.com/AugustoArbulu/MangaReader12/pull/72

- Antes: um HTTP 200 com HTML de erro podia ser gravado como `page-00000.bin` e contado como página concluída, embora o leitor fosse falhar no modo avião.
- `ChapterDownloadManager` agora usa `ImageIO` e rejeita payloads vazios, textuais, JSON/XML e imagens incompletas/invalidas antes da gravação.
- PNG exige chunk terminal `IEND`; JPEG exige `EOI` perto do fim. Essa segunda camada foi necessária porque ImageIO reconheceu um PNG truncado somente pelo cabeçalho no primeiro teste.
- Nenhuma mudança em TLS, user-agent, domínios, acesso, sessão, cookies ou autenticação. Não altera downloads já persistidos.
- Nova falha explícita `invalidImagePayload` evita marcar arquivos como completos.
- `ci/test_build46_download_integrity.py` extrai e executa **o helper Swift real** em `xcrun swift`, com PNG 1×1 gerado localmente, HTML, PNG truncado e tipos MIME.
- Debug/Release e Configurações identificam **Build 46**.
- **QA físico de downloads ainda necessário.**

**IPA não assinada Build 46:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/41599907817/artifacts/13213783471  
**CI aprovado pós-merge:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/41599907817

### PR #73 — Asura EN 0.1.1: IDs canônicos para Biblioteca

https://github.com/AugustoArbulu/MangaReader12/pull/73

- Upstream fornece `slug` da série e `public_url` com possível sufixo aleatório.
- Novo ID estável: `https://asurascans.com/series/{slug}`; capítulos públicos: `.../series/{slug}/chapter/{número}`.
- URL real para acessar HTML continua `/comics/{public-slug}`; associações públicas armazenadas pelo namespace `SourceStorage` (UserDefaults), recuperáveis após reinício.
- Ao reencontrar a obra na API, atualiza o alias sem trocar ID estável, evitando falsos novos capítulos após mudança de URL.
- Mantém leitura de antigos IDs experimentais `/comics/`; não migra Bibliotecas automaticamente (potenciais duplicações se alguém já adicionou a obra antes do 0.1.1).
- Documentado em `docs/ASURA_V011_STABLE_IDS_2026-11-03.md`.
- **Não equivale a funcionalidade física comprovada**. Rotação de sufixo sem recarga de catálogo, redirects e persistência exigem QA real.

### PR #74 — investigação de imagem em tiles via CoreGraphics

https://github.com/AugustoArbulu/MangaReader12/pull/74

- Arquivo de **pesquisa offline** `ci/asura_coregraphics_tiles_probe.swift`, separado do app.
- Reordena tiles por permutação `srcIndex → tiles[srcIndex]`, conforme algoritmo público Keiyoushi.
- Limites de memória/dimensões, índice único e válido, grade divisível, imagens sintéticas com cores e 4×5.
- Não modifica `Page`, não liga o decodificador ao leitor ou downloads e não faz requisições.
- **CI aprovado e PR #74 integrado em `main`**. Os testes sintéticos de identidade 4×5 e permutações horizontais/verticais de pixels passaram com Swift 5.10. Isso valida a geometria no protótipo, **não** a integração no leitor, memória de produção ou imagens reais da Asura.

## 3. Infraestrutura existente e testes

### Biblioteca e Atualizações
- `MangaReader12/Library/LibraryUpdateManager.swift`: percorre obras da Biblioteca, carrega `source.chapters`, compara `sourceChapterID` com IDs conhecidos, persiste capítulos e adiciona eventos novos ao feed.
- `MangaReader12/Library/BackgroundLibraryUpdateManager.swift`: permite mínimo configurado de background fetch (~6 h). **O iOS controla quando realmente executa**, não prometer execução garantida.
- `MangaReader12/Database/SQLiteDatabase.swift`: biblioteca, capítulos, estados, histórico e downloads.
- WeebCentral usa IDs reais estáveis `https://weebcentral.com/chapters/{ID}`, já validada quanto a listagem; verificações de update e ausência de notificações duplicadas ainda pendem de teste.
- Asura precisa comprovar seu novo mapeamento estável em atualizações reais.

### Downloads offline
- `MangaReader12/Downloads/ChapterDownloadManager.swift`: fila serial, pausa/retomada, arquivos em Application Support e plano de recuperação após encerrar app.
- Leitor online/offline em `MangaReader12/UI/ReaderViewController.swift`. O modo avião deve usar **páginas locais** após download concluído.
- Build46 rejeita payload de imagem inválido antes de salvar. Ainda não foi testado um capítulo WeebCentral inteiro offline no dispositivo.

### Compatibilidade do parser iOS 12
- `MangaReader12/SourceRuntime/JavaScriptSourceRuntime.swift`, `Native.htmlSelect` via WKWebView local + DOMParser inerte; sem executar JS da página.
- Build44 elevou os tetos de seleção: até **4.000 capítulos** e **1.500 imagens**, falha explícita em excesso, demais seletores até 200. Limites 3 MiB HTML / 4 MiB saída mantidos.
- Diferença crítica: Jsoup `[x-data~=scroll]` = **regex**, CSS/WebKit `~=` = palavra isolada; WeebCentral já corrigiu para `*=`/seletores compatíveis.
- WeebCentral 0.1.4 corrige rótulos `Tags(s)` e `Author(s)`, gêneros via `href*="included_tag="` e tipo via `included_type` no HTML. QA positivo.

## 4. Catálogos e códigos atuais

**WeebCentral EN, catálogo experimental:**
`https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/weebcentral-pilot-repository.json`

- Script: `fixtures/keiyoushi-weebcentral-en.js` — **v0.1.5**.
- SHA-256: `431e59eeb801bbda2a935da5c0f923f609a8807a8b48d2713223bc7a315d74d7`.
- Origens listadas: `weebcentral.com`, `temp.compsci88.com`, `hot.planeptune.us`.
- Filtros gerais 0.1.3: 38 tags da fonte com inclusão, exclusão, tipo, status, ordenação; aplicados no servidor antes da paginação; interface no Build45.

**Asura EN, catálogo experimental separado:**
`https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/asurascans-pilot-repository.json`

- Script: `fixtures/keiyoushi-asurascans-en.js` — **v0.1.1**.
- SHA-256: `b4d69dd159d8499c641e54f651f4abbe6ff7c3264db734a845fcf4c62d0fe004`.
- Origens iniciais: `asurascans.com`, `api.asurascans.com`. Nenhum CDN externo de imagem adicionado sem evidência.
- Premium indisponível, tiles ainda bloqueados, filtros avançados ainda não portados, **sem QA físico**.
- NÃO inserir no catálogo principal nem anunciar leitura completa.

## 5. Plano de QA físico — ao usuário voltar

**Prioridade 1 — Build 46 + WeebCentral (uma obra pequena):**
1. Baixar a IPA não assinada Build46 pelo link acima, extrair do ZIP e instalar via Sideloadly por cima da versão anterior, **sem desinstalar**, preservando dados de Biblioteca/Downloads.
2. Atualizar o catálogo experimental WeebCentral e a fonte para **0.1.5**. Não precisa baixar outra IPA para scripts posteriores.
3. Confirmar que capas, gêneros nos detalhes e capítulo 1 de *One Piece* continuam disponíveis; datas podem aparecer caso a UI as apresente.
4. Adicionar **uma obra curta** à Biblioteca (evitar começar com centenas de downloads), entrar em Biblioteca e realizar atualização manual. Uma segunda atualização sem conteúdo novo não deve criar eventos novos.
5. Selecionar **um capítulo público pequeno**, baixar, verificar estado de conclusão, ativar modo avião e percorrer as páginas offline. Depois testar pausa/retomada de outro download pequeno, se necessário.
6. Se aparecer erro HTTP 403/429, recusa explícita, imagem inválida ou CDN desconhecido, interromper e enviar apenas mensagem do erro/hostname — não copiar URL assinada, cookies ou tokens.

**Prioridade 2 — Asura (experimento pontual e sem promessas):**
1. Importar manualmente o **catálogo Asura isolado** (não substituir WeebCentral); instalar a Asura EN 0.1.1.
2. Testar Populares e uma busca por obra pública, detalhes, gêneros e capítulo aberto (não premium). Registrar separadamente se título, capa e capítulos aparecem.
3. Se as capas não aparecerem, o provável bloqueio é o host de CDN não autorizado — **não** liberar wildcard sem comprovação.
4. Se ocorrer `tiled images`, é o limite deliberado; não repetir muitos capítulos. Não tentar premium.
5. Se houver 403/429 ou site indisponível, parar; não contornar.

**Prioridade 3 — Qualidade de Biblioteca/Leitor:**
- Verificar progresso de leitura e histórico após fechar/reabrir o app.
- Conferir leituras offline de arquivos completos em modo avião.
- Testar filtros da WeebCentral em mais de uma página, inclusive limpar seleção.
- Conferir fonte Webtoons EN para regressões.

## 6. Roadmap de implementação após QA

1. **Asura public-only QA e CDN:** observar sem tráfego massivo, conferir respostas API e Astro no iOS12, hostnames reais de capas/imagens, redirects e limites de tamanho, sem contornar restrições.
2. **Asura tile renderer:** transformar o protótipo offline em componente nativo seguro, adicionar metadata opcional `tiles` ao modelo Page sem quebrar Codable/arquivos antigos; integrar separadamente ReaderImageLoader e ChapterDownloadManager; validar pixels sintéticos, memória, imagem final e modo avião, e só então habilitar páginas públicas com tiles.
3. **Asura IDs/migração:** garantir que rota pública com sufixo renovado não provoque novos IDs; nunca migrar/remover registros sem backup e aprovação explícita. Verificar estratégia de alias em atualizações de Biblioteca.
4. **Asura filtros remotos:** port de gêneros dinâmicos Astro `/browse` e de status/tipo/sort da API. **A API oferece inclusão de gêneros, não exclusão remota genérica**; a UI deve indicar o que suporta e evitar excluir apenas depois da paginação como se fosse filtragem completa.
5. **WeebCentral qualidade:** teste real da atualização de capítulos e download offline, monitorar HTML/CDNs quando o site mudar, tratamento de falha explícita, melhorias de interface e seleção de filtros quando a lista é longa.
6. **Comix (somente após decidir retomar):** no Build43, WKWebView recebeu HTTP200/didFinish mas tela branca; Safari no mesmo iOS12 mostrou tela preta. Próxima investigação planejada é HTML **local** inerte para separar WebKit/renderização/JS do site, sem requests automáticos ou tentativas de bypass; não misturar com este trabalho.
7. **Higiene:** manter `main` estável, CI verde, SHA-256 dos scripts e origem fixa por fonte; nenhuma atualização automática de todo Keiyoushi.

## 7. Política operacional para o próximo chat

- **Não reiniciar do zero.** Ler este handoff, docs de PRs #70–#74 e branch `main` mais recente.
- Nenhuma solicitação ao Comix durante esta rodada; projeto Android Mihon Comix Tweaks é separado e não deve ser modificado aqui.
- Para código: feature branch -> commits -> CI -> squash merge; não alterar `main` diretamente.
- Para IPA: usar artefato GitHub Actions com run/ID reais. Não inventar links sandbox nem prometer teste físico.
- Para segurança: HTTPS normal, sem credenciais de premium, cookies de sessão ou WAF bypass; retornar falhas claras, limitar memória/domínios e proteger dados locais.
- Dizer claramente o que foi **confirmado pelo usuário** e o que só passou em **fixture offline**.
- **Não exigir novos testes do usuário enquanto estiver dormindo.** O próximo contato começa com o roteiro resumido, links e a pergunta sobre resultados depois de ele testar.

## 8. Links diretos

- [PR70 — WeebCentral 0.1.5](https://github.com/AugustoArbulu/MangaReader12/pull/70)
- [PR71 — Asura piloto](https://github.com/AugustoArbulu/MangaReader12/pull/71)
- [PR72 — Build46 download](https://github.com/AugustoArbulu/MangaReader12/pull/72)
- [PR73 — Asura 0.1.1 IDs estáveis](https://github.com/AugustoArbulu/MangaReader12/pull/73)
- [PR74 — Asura tiles CoreGraphics protótipo](https://github.com/AugustoArbulu/MangaReader12/pull/74)
- [IPA Build46, CI verde](https://github.com/AugustoArbulu/MangaReader12/actions/runs/41599907817/artifacts/13213783471)
- [WeebCentral 0.1.5](https://github.com/AugustoArbulu/MangaReader12/blob/main/docs/WEEBCENTRAL_V015_CHAPTER_DATES_2026-11-03.md)
- [Asura 0.1.1](https://github.com/AugustoArbulu/MangaReader12/blob/main/docs/ASURA_V011_STABLE_IDS_2026-11-03.md)
- [Protótipo offline de tiles CoreGraphics](https://github.com/AugustoArbulu/MangaReader12/blob/main/docs/ASURA_COREGRAPHICS_TILES_OFFLINE_PROBE_2026-11-03.md)
- [Build46](https://github.com/AugustoArbulu/MangaReader12/blob/main/docs/BUILD46_DOWNLOAD_IMAGE_INTEGRITY_2026-11-03.md)

**Estado ao encerrar esta rodada:** WeebCentral observavelmente funcional para leitura online e filtros/detalhes no iOS12.5.8; downloads offline e atualização de Biblioteca ainda pendentes de QA. Asura experimental com arquitetura pública e **protótipo geométrico de tiles testado em CI**, mas leitores de tiles ainda não publicados. Build46 disponível para teste. Não transformar protótipo de tiles em recurso sem validação adequada.
