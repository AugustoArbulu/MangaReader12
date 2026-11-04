# HANDOFF COMPLETO — ROADMAP MangaReader12 (iOS 12)

> **STATUS NOVO, 2026-11-04:** Este roadmap contém fases históricas. Para o estado de fato após Build 53, veja [HANDOFF_MANGAREADER12_BUILDS51_53_2026-11-04.md](HANDOFF_MANGAREADER12_BUILDS51_53_2026-11-04.md). **Não** recriar seleção de capítulos (até 5 por lote), feed de Updates, ou indicadores de não lidos: já estão no código. A Build 51 foi relatada como funcional; Builds 52/53 aguardam QA física. O foco de compatibilidade é WebP/ImageIO limitado, e AVIF segue apenas detectado.


> **Atualização após execução do roadmap (2026-11-01):** R1-A/R1-B e início de R1-D já foram implementados no **Build37** (PR #49); **Webtoons EN 0.1.9** oferece categorias de rankings, gêneros experimentais e Recentes (Originals do dia) via PR #52. **R2-A**, o monitor somente de leitura do Keiyoushi, foi integrado no PR #50. A versão nativa Build37 e a fonte 0.1.9 aguardam validação física; a referência comprovada ainda é Build36 + Webtoons 0.1.7. **Leia o novo handoff:** docs/HANDOFF_BUILD37_WEBTOONS019_R2_2026-11-01.md. Os trechos abaixo descrevem o planejamento original antes desses PRs e devem ser interpretados como histórico, não como status atualizado.


**Data do checkpoint:** 2026-11-01  
**Repositório:** AugustoArbulu/MangaReader12  
**Branch principal:** main  
**Referência do código antes deste handoff:** 003807a77351b98c9a531b884771586fde82740d (merge do Build 36, PR #47)  
**Natureza deste arquivo:** planejamento, decisões, critérios de aceite e continuidade. Não é implementação de novas funcionalidades.  
**Status de produto:** app nativo funcional em iOS 12.5.8, com validação inicial do fluxo real Webtoons.com EN.

> **Para o próximo chat/agente:** não reinicie o projeto nem suponha que os recursos planejados já existem. Leia primeiro este handoff, PROJECT_STATE.md e docs/MIHON_FEATURE_AUDIT_IOS12.md; confira o HEAD atual de main e os PRs recentes antes de agir. Preserve o Build 36 como checkpoint funcional até que um substituto seja aprovado no aparelho. Não faça alterações diretas em main.

---

## 1. Decisões do usuário e objetivo do produto

Criar e evoluir o **MangaReader12**, um leitor independente de mangás/manhwas/webtoons que funcione em **iOS 12** e ofereça experiências semelhantes às do Mihon, respeitando o ecossistema Apple. Mihon é referência de UX e funcionalidades, não código portável diretamente.

Preferências/princípios explicitados no projeto:

- Priorizar **compatibilidade com iOS 12.0** e uso real no aparelho com **iOS 12.5.8**.
- Não quebrar o fluxo validado por causa de uma melhoria estética ou uma nova fonte; conservar um build conhecido como bom.
- Fonte/adapter em JavaScript no runtime próprio é diferente de APK Android do Keiyoushi. Não afirmar compatibilidade binária.
- Desenvolver e testar de maneira incremental: branch de trabalho, testes automáticos, PR, CI verde, squash merge para main. **Nunca editar main diretamente.**
- Evitar muitos IPAs para pequenas mudanças em fontes: quando só o script/catálogo muda, atualizar a fonte pelo catálogo sem reconstruir o app. Gerar novo IPA quando mudar Swift/UI/runtime nativo.
- Só considerar um recurso **fisicamente validado** após relato do usuário no iPhone. CI e mock offline não provam funcionamento real de sites, desempenho ou leitura offline.
- Não driblar autenticação, Cloudflare, restrições de acesso de terceiros, certificados TLS, limites da fonte ou bloqueios 403/429. Falhas de acesso são resultado de teste, não autorização para bypass.
- O usuário pediu planejar filtros por gênero, categorias **Populares/Recentes** e saber como receber mudanças do Keiyoushi; em seguida perguntou por outros recursos; esta é a consolidação desse roadmap **para consulta posterior**, não uma autorização para implementar tudo agora.

## 2. Estado factual do app no checkpoint

### 2.1 Referência funcional

- **App:** Build 36, CFBundleVersion 36; deployment target iOS 12.0; iPhone de teste em iOS 12.5.8.
- **Fonte principal em teste:** Webtoons.com EN (id kei.webtoons.en), **versão 0.1.7** (arquivo fixtures/keiyoushi-webtoons-en.js).
- **Feedback físico:**
  1. App 34 + Webtoons EN 0.1.6: capas que antes falhavam começaram a abrir.
  2. Webtoons EN 0.1.7: capítulos abrem e imagens parecem normais durante leitura, incluindo rolagem em várias páginas; aceite inicial positivo.
  3. Usuário confirmou download e armazenamento no aparelho; ao testar modo avião no Build 35 apareceu erro de fonte/network -1009.
  4. Build 36 corrigiu o caminho de abertura offline; após teste físico o usuário informou **“está funcionando”**.
  5. Build 35 também recebeu avaliação geral positiva para navegação/leitura, mas sem medição de uso prolongado de memória/RAM ou stress de grandes capítulos.
- **Não ampliar a conclusão:** isso não significa que todas as fontes, capítulos, downloads simultâneos, reinícios, sincronização, longa duração ou todas as opções foram testadas.

### 2.2 Correções recentes de referência

- Webtoons 0.1.6: normalização segura de URL de capas para peculiaridades de Foundation/URL(string:) no iOS 12.
- Webtoons 0.1.7: normalização de URLs de imagens de capítulos sem reescrever indevidamente o host CDN; mantém Referer e controles de domínio.
- **PR #46 / Build 35**: ReaderImageLoader tem fila de trabalho, máximo 3 transferências, coalescência de requisições idênticas, NSCache até 8 imagens/~48 MiB de pixels estimados, cache em disco até 160 arquivos/192 MiB, sem prometer redução mensurada de RAM.
- **PR #47 / Build 36**: capítulo baixado concluído abre diretamente do armazenamento sem consultar source.details/chapters, e a Biblioteca possui fallback local. Snapshot SQL preserva metadados durante gravação de progresso.
- SHA de main após PR #47: 003807a77351b98c9a531b884771586fde82740d. Confirme HEAD real ao retomar: outros merges podem ocorrer depois do handoff.

### 2.3 Funcionalidades já existentes no código

- Biblioteca SQLite com categorias, filtros locais, leitura e histórico, atualização manual e feed de Updates.
- Reader em páginas LTR/RTL ou rolagem Webtoon; direção, zoom, duplo toque, zonas de toque, barra de controles, brilho, fundo, indicador de página, manter tela ligada, escala e pré-carregamento de páginas/próximo capítulo.
- Downloads e armazenamento local, fila, pausar/retomar/priorizar, leitura offline, gerenciamento de espaço/cache.
- Backup/restore portátil .mr12backup, importação por Files, migração entre fontes (sem migrar downloads), fonte Demo.
- Catálogos de fontes JavaScript, instalar/atualizar/desativar/rollback, verificação de domínio e SHA-256, busca por fonte e busca global.
- Temas/ícones, diagnósticos e configuração parcial de fontes, suporte oportunista a Background Fetch.

**Distinguir** “implementado no código”, “CI aprovado” e “validado fisicamente”. O documento docs/MIHON_FEATURE_AUDIT_IOS12.md é anterior ao Build 36 e contém estados históricos que devem ser confrontados com PROJECT_STATE.md.

## 3. Arquitetura e regras que não podem ser perdidas

### 3.1 Fluxo de fontes

- iOS executa scripts de fonte pelo runtime **JavaScriptCore** e ponte HTTPS/DOM segura do próprio MangaReader12; não executa Kotlin, APK, OkHttp nem extensões Keiyoushi sem conversão.
- Contrato obrigatório de fonte v1 em MangaReader12/Sources/SourceManifest.swift: **metadata, popular, search, details, chapters, pages**. Busca já recebe (query, page, filters), mas os adapters não precisam implementar filtros reais apenas porque o parâmetro existe.
- Catálogo JSON com apiVersion, SourceManifest, versão, minAppVersion, domínios permitidos, URL HTTPS de script e SHA-256 opcional/verificado nos catálogos selecionados. A decisão de atualizá-lo é do nosso repositório, **não do Keiyoushi**.
- Entrada do usuário: Exporar → repositório → fonte → SourceBrowserViewController → MangaDetailsViewController → ReaderViewController. Downloads concluídos usam rota **local** direta no Build36.
- Scripts experimentalmente convertidos: fixtures/keiyoushi-selected-repository.json, fixtures/keiyoushi-*.js, ci/test_m13a_js.cjs.
- O fluxo de gerenciamento/upgrades do catálogo fica em MangaReader12/Sources/RepositoryManager.swift e arquivos correlatos. Mudanças nativas de contrato devem ser compatíveis com o v1 e manter as fontes instaladas.

### 3.2 Infra e CI

- Repositório: AugustoArbulu/MangaReader12; workflow .github/workflows/build.yml.
- macos-14, Xcode 15.4, Swift 5 language mode, iOS deployment 12.0; builds Debug e Release para device genérico; verificação de mínimo OS e CFBundleVersion, testes de fonte offline e artifact unsigned IPA.
- Commits em branch de feature ou docs → PR contra main → esperar **push e PR CI verde** para o HEAD exato → squash merge; não alterar main diretamente.
- Alterações **somente em scripts JS/catálogo**: atualizar version + SHA256 pin + testes; em geral não criar IPA.
- Alterações **nativas**: incrementar CFBundleVersion e respectivo script de verificação de versão, PR + CI, IPA sem assinatura para Sideloadly e teste físico.
- Não adicionar iOS Simulator/XCTest pesado por padrão; o usuário aceitou adotar esses testes **quando realmente necessário**. Simulador não substitui aparelho iOS12 físico.
- Backups portáteis **não incluem** downloads nem scripts de fontes; informar isso antes de propor mudanças destrutivas. Nunca apagar repositórios, downloads ou DB sem autorização explícita.

### 3.3 Limitações de plataforma/sítios

- iOS 12 possui RAM limitada e decodificar imagens verticais grandes é caro; qualquer crop, escala, modo Webtoon ou prefetch precisa ser limitado em memória e responsivo.
- Background Fetch depende do iOS, **não garante horário de execução**; agendamento de atualizações ou downloads automáticos deve ser best effort, com operação manual confiável.
- WKWebView de login/captcha pode ser considerado apenas para fluxos legítimos de interação do usuário; não fingir suporte a páginas com bloqueios de terceiros, burlar controles de acesso ou reduzir garantias TLS.
- Fontes reais podem oferecer gêneros, popularidade e ordenação com semântica diferente; não inventar “Recentes” a partir de listas sem dados de atualização.

---

## 4. Ordem do roadmap e critérios de priorização

| Ordem | ID | Entrega | Prioridade | Natureza |
|---|---|---|---|---|
| 0 | R0 | Preservar/regredir Build36 e integridade dos dados | Gate permanente | Estabilidade |
| 1 | R1 | Descoberta: Populares, Recentes, filtros, gêneros e ordenação | Muito alta | UI + contrato de fonte |
| 2 | R2 | Mais fontes Keiyoushi + monitoramento supervisionado upstream | Muito alta | Infra de fontes |
| 3 | R3 | Leitor: crop, páginas duplas, escala, ações e desempenho | Alta | UI/decodificação |
| 4 | R4 | Biblioteca: filtros avançados, duplicatas, ordenação, estatísticas básicas | Alta | SQLite/UI |
| 5 | R5 | Downloads: políticas, retomada/automação confiável | Média | Persistência + iOS |
| 6 | R6 | Fonte local: ZIP/CBZ primeiro; EPUB depois | Média | Parser/Files |
| 7 | R7 | Segurança, backups, isolamento de fontes, observabilidade | Transversal | Hardening |
| 8 | R8 | Incógnito, rastreadores, customização extra e recursos opcionais | Posterior | QoL/integrações |

**Essa ordem é uma proposta, não uma sequência inflexível.** Corrigir regressão real e manter leitura estável tem precedência sobre qualquer milestone. Agrupar alterações pequenas correlatas em um único IPA sem acumular alterações de alto risco no mesmo release.

## 5. R0 — baseline e regressão antes de expandir

**Objetivo:** não perder os fluxos validados enquanto incrementamos funcionalidades.

### Plano técnico
1. Registrar baseline de main e fontes instaladas antes de qualquer PR. Fixar versão Webtoons 0.1.7 e guardar screenshots/logs úteis, sem tokens/cookies.
2. Fazer regressão leve: abrir Populares, pesquisar, detalhes, lista, leitura online, capítulos baixados via Downloads e Biblioteca com modo avião, e voltar para online.
3. Confirmar que navegar e ler offline atualiza progresso sem destruir número/capa/URL armazenados; verificar no código as invariantes de SQLite.
4. Manter limites existentes de cache, política HTTPS e headers; não regredir cache coalescido.
5. CI: offline mocks do JS, auditoria iOS12, Debug/Release, versão embedded. Teste físico apenas para mudanças que impactam navegação, fonte real, armazenamento, reader ou integrações sensíveis.

### Aceite
- Não há falha nova em leitura, navegação, download/offline, histórico e dados persistidos comparados ao Build36.
- Uma nova versão somente vira checkpoint funcional depois do relato do usuário no aparelho.

## 6. R1 — Navegação e descoberta: Populares / Recentes / Filtros

**É a primeira grande feature visível recomendada.** A experiência desejada é parecida com o Mihon: uma fonte abre abas/modos reconhecíveis e informa quais controles realmente suporta.

### 6.1 Problema atual verificado

- SourceBrowserViewController usa currentQuery == nil para chamar **popular(page)**; com texto chama **search(query, page, [])**, sempre com filtros vazios.
- O contrato v1 **não possui função Recentes obrigatória**, nem descrição padronizada de gêneros, ordenações, tipos de filtro ou capacidades.
- O adapter Webtoons EN 0.1.7 implementa **popular(page)** mapeando indevidamente os quatro valores de page para rankings **trending, popular, originals, canvas**, com limite fixo page 1..4. Isso confunde **categoria de ranking** com **paginação real** e deve ser redesenhado com compatibilidade.
- A busca Webtoons aceita o argumento filters, mas no adapter atual **não o transforma em filtro real**; títulos com genres só aparecem nos detalhes, não nos cards.
- Há filtros de **categorias da Biblioteca**, mas **não confundir** com busca remota por gênero.

### 6.2 UX proposta

- Modos separados: **Populares**, **Recentes** e **Filtros** dentro da navegação da fonte, mantendo busca por título.
- A aba “Recentes” deve explicitar semântica da fonte: “atualizados recentemente” (novo capítulo) x “adicionados recentemente” (nova série) x “ranking novo”; não rotular sem prova.
- Filtros: seleção de um ou mais gêneros, status (em andamento/concluído), tipo/idioma e ordenação (popularidade, data, alfabético) **apenas quando suportados**.
- Estado dos filtros deve permanecer ao paginar, voltar dos detalhes e alternar layout; botão “Limpar filtros”.
- Mostrar rótulo/capacidade indisponível de forma clara: ocultar/explicar onde o site não oferece busca por gênero, em vez de devolver resultados sem filtrar.
- Adotar UI UIKit enxuta, com persistência de preferências quando fizer sentido, sem afetar iOS12 ou busca global existente.

### 6.3 Contrato de fonte proposto

Desenhar um **capabilities** opcional e versionado, preservando integralmente as seis funções do v1:
- Capabilities opcionais: supportsLatest, supportedSorts, genreFilterOptions, statusOptions, languageOptions, supportsAdvancedSearch e tipo de paginação.
- Método opcional **latest(page, done)** para fontes que realmente forneçam listagem de últimos updates.
- Busca ou browse tipado com argumentos para filtros/ordem, sem exigir que sources v1 implementem nada. Considerar chamar search("", page, filters, done) **somente se** cada adapter validar explicitamente busca vazia como modo de descoberta.
- Cada filtro precisa de semântica e serialização estáveis, validadas no runtime e no JS; nunca interpolar texto arbitrário em endpoints sem URL encoding e allowlist.
- Paginação deve ser consistente: page 1 é primeira página, page 2 é próxima página do **mesmo** modo/filtro, não outro ranking.
- Fazer migração incremental: primeiro Webtoons EN com mecanismo de ranking confiável; depois adapter por adapter. Não converter todas as fontes no mesmo PR.
- Distinguir retorno “sem resultados” de indisponibilidade/403/429/falha de parse.

### 6.4 Etapas implementáveis

1. **R1-A — arquitetura/capabilities**: definir modelo de capacidades/ordens, interface UIKit, fallback v1 e testes de compatibilidade. Sem alterar fonte real inicialmente.
2. **R1-B — Populares Webtoons**: separar trending/popular/originals/canvas com seletores explícitos e paginação correta baseada na resposta real do site. Não fazer quatro requests automaticamente se um já atende à tela.
3. **R1-C — Recentes**: identificar endpoint/listagem legítima por fonte, provar semântica de “recentes” e teste com fixture. Caso não exista, não habilitar opção.
4. **R1-D — Filtros**: implementar ao menos gêneros reais em uma fonte que ofereça filtro remoto, depois status/sort; usar filtros de client-side apenas em **itens já carregados** e declarar essa limitação.
5. **R1-E — evolução das demais fontes**: capability matrix por adapter e regressão.

### 6.5 Testes e aceite

- CI: capabilities opcionais com source v1 legacy, popular/latest/search/filters, falta de suporte, erro remoto, filtro e paginação consistentes, não duplicação de IDs, rollback de JS, hash do catálogo.
- iPhone iOS12: popular 1→2→voltar, alterar categoria sem misturar páginas, pesquisar com e sem filtro, confirmar títulos e gêneros reais, abrir detalhes/chapítulo e ler, retornar mantendo estado.
- Segurança: sem resultados falsos, sem rotular como data recente uma lista meramente popular, sem escala não limitada de chamadas.

**Definition of Done R1:** UI universal funcional, pelo menos uma fonte real com popularidade/recência/filtro explicitamente suportado e validado, casos de indisponibilidade honestos, leitura existente preservada.

## 7. R2 — Fontes Keiyoushi e atualização supervisionada

### 7.1 Verdade sobre compatibilidade e updates

As nossas fontes **não são APKs oficiais do Keiyoushi**. São **ports JS próprios baseados nas implementações upstream**. O app já suporta **atualizar os nossos scripts pelo catálogo JSON** e verificar versões/hash, mas **não ingere mudanças Kotlin/APK upstream automaticamente**.

Fluxo recomendado de atualização upstream:

1. GitHub Actions agendado ou execução manual lê **somente informações públicas/autorizadas** do repositório keiyoushi/extensions-source para os diretórios das fontes selecionadas.
2. Salva upstream commit/hash/path/changed files e compara com último snapshot revisto; identifica mudanças Kotlin e componentes compartilhados (Madara, Iken, YiiMadara).
3. Emite relatório/issue ou PR de **análise**, não atualiza silenciosamente scripts publicados em main.
4. Humano/assistente interpreta diff e porta apenas comportamento compatível para JS + bridge existente.
5. Adiciona/atualiza fixtures, testes offline, version e SHA256 pin, valida CI, e publica via PR. Atualização pelo catálogo no iPhone **não exige IPA** se Swift não mudar.
6. Erros de site 403/429/Cloudflare, quebra de API e host novo entram em investigação documentada; nada de bypass, cookies forjados ou TLS relaxado.

**Importante:** monitorar upstream pode ser automatizado; **portar e validar uma mudança arbitrária Kotlin** não pode ser prometido como conversão 100% automática.

### 7.2 Matriz das nove fontes selecionadas

| Fonte | Situação no MangaReader12 (2026-11-01) | Dependências/riscos | Próximo passo |
|---|---|---|---|
| Webtoons.com EN | **Implementada v0.1.7, uso físico inicial aprovado** (capas, leitura, download/offline via Build36) | Sem motion toon; rankings/filtros ainda limitados; imagens CDN; semântica de recência | R1 UI e capacidades; monitorar upstream |
| Manhwa18.net | Adapter JS v0.1.0 experimental; parte da leitura testada em Build29; não afirmar aceite completo atual | HTML/API e paginação podem variar | Revalidar listagem, capítulos, imagens, downloads e covers |
| HotComics | Adapter JS v0.1.0 experimental; HTTP403 reportado em teste físico anterior | Restrição da fonte, cookies/autorização | Investigar viabilidade legítima; sinalizar indisponível se bloqueado |
| Vortex Scans | Não portado | lib-multisrc/iken | Portar Iken de forma reutilizável |
| ToonGod | Não portado | lib-multisrc/madara, MadaraNoAjax | Base Madara limitada e testada; respeitar acesso |
| Manhwa18.cc | Não portado | lib-multisrc/yiimadara | Engine YiiMadara compartilhável |
| Asura Scans | Não portado | API/DTO e processamento de imagens específico | Revisão de legalidade técnica/compatibilidade, depois parser |
| MadaraDex | Não portado | engine Madara + autorização/cookies | Avaliar restrições; não contornar |
| Comix | Não portado | Android/WebView, API/site e bloqueios contra terceiros | Último/alto risco; não prometer suporte ou driblar bloqueios |

Inventário técnico de paths upstream e engines já está em **docs/M13_SELECTED_KEIYOUSHI_SOURCE_PORTS.md**. Verificar atualizações upstream antes de portar, sem presumir que módulos ainda existem na mesma forma.

### 7.3 Entregas recomendadas

- **R2-A:** sistema de relatório de diferenças upstream para essas nove fontes e bibliotecas compartilhadas relevantes; sem mudanças automáticas em produção.
- **R2-B:** consolidar matriz status por fonte: implementada, instalada, CI, teste físico, acesso permitido, falha HTTP/DOM, pendente e última revisão.
- **R2-C:** portar shared engines por famílias com testes unitários offline (Iken → Vortex; Madara → ToonGod/MadaraDex; YiiMadara → Manhwa18.cc) e só depois adapters específicos.
- **R2-D:** portas independentes de alto risco por último; medição de tráfego, compatibilidade iOS12, requisitos de sessão/documentação.
- **R2-E:** manter distribuição própria com SHA256 por fonte, version monotônica, rollback e isolamento de hosts.

**Definition of Done R2:** upstream monitorável com diffs úteis e nenhuma atualização não revisada; novas fontes publicadas somente após testes e identificação honesta dos limites.

## 8. R3 — Qualidade de leitura e desempenho

Propostas ordenadas por risco/benefício:

1. **Ações de página:** salvar imagem no Files/Fotos com autorização, compartilhar via UIActivityViewController, copiar URL somente se permitido. Não expor tokens/headers.
2. **Crop automático de margens:** identificar faixas brancas/pretas sem decodificar todas as páginas ao mesmo tempo; cálculo em fila, cache de resultado, toggle reversível e opção desligada por padrão.
3. **Páginas duplas:** detectar página horizontal larga, permitir dividir em esquerda/direita conforme LTR/RTL; preservar índices e progresso corretos; não alterar ordem da fonte.
4. **Escala inteligente:** respeitar fitScreen, fitWidth, fitHeight e original existentes; considerar a resolução do aparelho, não aumentar texturas enormes desnecessariamente.
5. **Fluxo Webtoon:** suavidade em rolagem longa, layout e mudanças de proporção sem saltos, descarte de imagens fora da viewport, deduplicação e limitação de prefetch.
6. **Stress de memória:** instrumentação que registre somente contadores locais ou tamanhos agregados, sem URLs privadas; medir no hardware com capítulos longos e offline.

**Aceite:** sem travamento/fechamento em capítulos longos representativos no iPhone, sem deslocamento de leitura, sem consumo de memória crescente não limitado, offline e modos paginados intactos. Não afirmar ganho de FPS/RAM sem medição.

## 9. R4 — Biblioteca, organização e histórico

- Ordenação por título, atualização, último acesso, data adicionada, quantidade de não lidos; critérios determinísticos no banco.
- Filtros separados para lidos/não lidos, concluídos/em andamento, baixados, categoria, fonte e idioma; combinação de filtros sem consulta remota para lista já salva.
- Capítulos duplicados: heurística por número, volume, nome normalizado/scanlator; **não apagar automaticamente**; oferecer visualização e escolha do usuário.
- Melhor marcador de último capítulo e progresso; múltiplos capítulos offline; continuidade ao migrar de fonte quando o capítulo tem correspondência confiável.
- Estatísticas locais opcionais: obras/capítulos lidos, tempo estimado **somente se realmente medido**, armazenamento e histórico; sem inventar tempo de leitura retroativo.
- Respeitar privacidade e evitar consultas a fontes durante abertura exclusivamente offline de itens baixados.

**Aceite:** testes SQLite de consultas, migração e idempotência; leitura offline sem escrever metadados incompletos; fluxo de backup/restore atualizado se esquema mudar.

## 10. R5 — Downloads e armazenamento avançados

**Já existe:** fila, pausar/retomar/priorizar, recuperação reiniciável, estados persistidos, armazenamento local e leitura offline.

**Futuro:**
- Opção de baixar próximos capítulos da Biblioteca ao atualizar, com confirmação, limites de espaço e rede.
- Política de retenção: preservar, apagar após ler, manter N últimos; **padrão deve ser não apagar automaticamente**.
- Informações de espaço previsto/real, falhas por página e tentativas controladas sem loop nem request excessivo.
- Se usar URLSession background: avaliar APIs efetivamente disponíveis no iOS12; não prometer downloads sempre ativos em segundo plano.
- Consistência de download parcial vs concluído; nunca oferecer como “offline completo” quando faltam páginas.

**Aceite:** sair/reabrir o app durante a fila, pausa/retomada, espaço insuficiente, desconexão, capítulo offline e exclusão reversível/confirmada; nenhum download perde histórico ou dados de Biblioteca.

## 11. R6 — Arquivos locais: CBZ/ZIP primeiro, EPUB depois

**CBZ/ZIP:**
- Integrar UIDocumentPicker iOS12, importação copy-in/sandbox, validar ZIP, evitar Zip Slip/path traversal, decompression bombs, arquivos gigantes e nomes duplicados.
- Ordenar imagens por índice/nome de forma previsível, preservar orientação/página dupla e integrar Library/Reader/downloads existentes sem source remota.
- Não assumir suporte RAR/CBR até escolher decoder compatível/licença apropriada.

**EPUB:** fase posterior e independente; parsing de container/OPF/spine/nav, imagens, XHTML e distinção entre livro textual e quadrinhos. Não fazer EPUB “funcionar” só renomeando ZIP.

**Aceite:** CBZ pequeno/grande, imagens ordenadas, nomes com Unicode, erro de arquivo malicioso, offline verdadeiro, backup/exportação com política clara e sem travamentos.

## 12. R7 — Segurança, integridade, manutenção e backup

- Fonte de terceiro deve continuar confinada a política por domínio HTTPS, limites de resposta, timeout/redirect, sem bypass ATS ou certificados.
- SHA256 pin do script verifica integridade do conteúdo baixado; avaliar **assinatura/editor/origem autenticada** futuramente se multi-publisher. SHA apenas confirma bytes esperados pelo catálogo, não identidade do autor.
- Reforçar isolamento de cookies/sessões e credenciais por fonte; não colocar tokens em logs ou relatórios.
- Diagnóstico de rede: diferenciar HTTP403/429/5xx, erro de transporte (-1009), parse inválido, URL inválida e arquivo local ausente sem fazer novas requisições escondidas.
- Backups portáteis atuais excluem arquivos de capítulos e scripts; antes de introduzir backup completo/importação/exportação, documentar custo, privacidade, espaço e rollback.
- Uso seguro de SQLite: transações consistentes em updates, jamais substituir metadata por placeholders, não perder categorias/histórico ao remover source.
- Estratégia de release: comparar DB/schema, backup e rollback para mudanças de dados. Suporte a downgrade deve ser descrito sem promessas de retrocompatibilidade não testada.

## 13. R8 — Recursos posteriores

- **Incógnito:** leitura sem atualizar histórico e progresso enquanto habilitado; comportamento explícito na UI.
- **Rastreadores:** desenhar mecanismo de login/autorização individual antes de integração. Nada de tokens nos repositórios.
- **Estatísticas:** derivadas de eventos reais, opt-in quando envolver métricas adicionais.
- **Temas/UX:** refinamento de layout, acessibilidade, fontes grandes e busca em Ajustes.
- **Sessão/login WKWebView:** somente interação permitida pelo site e pelo usuário; nenhuma solução genérica para sites que deliberadamente rejeitam clientes terceiros.

Não priorizar R8 à frente de estabilidade, fontes funcionais e descoberta.

---

## 14. Matriz de testes e aceite por tipo de alteração

| Tipo de mudança | Teste mínimo no CI | Teste físico recomendado |
|---|---|---|
| Só documento | Revisão humana/link/sem código | Não requer IPA |
| Script JS de fonte | mocks contratos + pin SHA256/manifest + caso de parse | Teste da fonte no Build36 existente, sem novo IPA |
| UI de navegação/filtros | Swift Debug+Release + testes de estado/paginação | Populares, Recentes, filtro, detalhe, voltar, modo offline |
| Runtime/bridge/source HTTP | Swift + testes de host/redirect/headers/timeout/decoding | Fonte real com domínio permitido e captura segura de erro |
| Leitor/cache | Swift + testes de escala/layout e regressão | Rolagem longa, mudança de capítulo, baixa RAM e offline |
| DB/download/backup | Testes de persistência/migração, crash/retry e restore | Mode avião, relançar app, histórico, restaurar backup |
| Local CBZ | ZIP validation/parsing, path traversal, arquivo grande | Importar via Files, ler/retomar e reabrir sem internet |

**Gates globais:** iOS mínimo 12.0, não expor conteúdo sensível, manter temas/leitor/biblioteca, preservar downloads existentes, CI para SHA exato, sem merge quando CI vermelho e sem chamar feature “validada no iPhone” sem feedback real.

## 15. Critérios de implementação para próximos PRs

1. Criar branch com escopo único e nome específico; commits pequenos e rastreáveis.
2. Antes de alterar API v1 ou SQLite, documentar compatibilidade, migração e rollback.
3. Nenhum “fix” que reduza TLS, amplie domínios sem evidência ou tente contornar restrição de acesso da fonte.
4. Adicionar testes para **caso que falhou**, não apenas happy path.
5. Para source real, testar formatos/HTML offline e só então validar no site permitido; minimizar número de requests.
6. Se mexer em código Swift, atualizar build number, script ci/verify_binary.sh e docs; distribuição IPA só após CI.
7. Se mexer em JS fonte, atualizar versão do adapter, SHA256 do catálogo e os testes de pin; não aumentar CFBundleVersion sem necessidade.
8. Abrir PR e aguardar checks completos, revisando logs de erro se falhar; squash merge main. Não entregar artifact antigo como se fosse build novo.
9. Registrar no PROJECT_STATE.md: novo comportamento, PR, SHA, CI e estado da validação física.
10. O usuário deve testar apenas o menor conjunto de ações útil para validar uma alteração, não fazer “beta test” extensivo sem necessidade.

## 16. Arquivos e referências concretos

**Código / CI**
- MangaReader12/UI/SourceBrowserViewController.swift — navegação, busca, detalhes; ponto inicial de R1.
- MangaReader12/UI/ReaderViewController.swift e ReaderPreferences.swift — leitor, cache, página, preload.
- MangaReader12/UI/LibraryViewController.swift e CategoryViewControllers.swift — Biblioteca e categorias.
- MangaReader12/UI/DownloadsViewController.swift, MangaReader12/Downloads/ChapterDownloadManager.swift — offline e fila.
- MangaReader12/Database/SQLiteDatabase.swift — Library, chapters, progress, download state.
- MangaReader12/Sources/SourceManifest.swift, RepositoryManager.swift — contrato e lifecycle de fontes.
- MangaReader12/SourceRuntime/JavaScriptSourceRuntime.swift — API JS/bridge.
- fixtures/keiyoushi-selected-repository.json e fixtures/keiyoushi-webtoons-en.js — fonte Webtoons EN 0.1.7.
- ci/test_m13a_js.cjs — testes de contrato dos adapters e proteção estrutural da rota offline.
- .github/workflows/build.yml — compilações/artefatos.

**Documentação existente**
- PROJECT_STATE.md — registro técnico/cronológico, mais atual que a auditoria histórica.
- docs/MIHON_FEATURE_AUDIT_IOS12.md — cobertura geral Mihon x iOS12.
- docs/M13_SELECTED_KEIYOUSHI_SOURCE_PORTS.md — inventário e prioridades das nove fontes.
- docs/M13A_SELECTED_SOURCES_TEST_GUIDE.md — roteiro de adaptação/QA de fontes.
- Histórico PR #45 (Webtoons EN 0.1.7), PR #46 (cache Build35), PR #47 (offline Build36).
- https://github.com/keiyoushi/extensions-source — upstream independente, nunca tratar como catálogo direto de scripts do iOS.

## 17. Como retomar exatamente este roadmap em outro chat

**Contexto a informar:**

    Continue o projeto MangaReader12 para iOS12 sem reiniciar.
    Repositório: AugustoArbulu/MangaReader12, branch main.
    Leia docs/HANDOFF_ROADMAP_MANGAREADER12_2026-11-01.md,
    PROJECT_STATE.md e docs/MIHON_FEATURE_AUDIT_IOS12.md.
    Build de referência validado inicialmente: 36; Webtoons EN 0.1.7.
    Confirme HEAD/PRs/CI atuais antes de executar qualquer mudança.
    Preserve main: branch → testes → PR → CI verde → squash merge.
    A prioridade de produto acordada é R1 (Populares/Recentes/filtros),
    em paralelo ao planejamento R2 (atualização supervisionada Keiyoushi).
    Não implemente funcionalidades não solicitadas nem declare suporte
    de fontes/recursos sem evidência real de teste no iPhone iOS12.5.8.

**Primeira ação sugerida quando o usuário disser "continue o roadmap":**
- Revisar este checkpoint e diferenciar pedidos novos da sequência anterior.
- Começar **R1-A** com desenho de capabilities opcionais + UI Populares/Recentes/Filtros e testes de compatibilidade v1; não alterar a extensão Webtoons por tentativa e erro.
- Preparar **R2-A** como documento/mapeamento de upstream em uma etapa independente, sem atualizar fontes automaticamente.
- Avançar com implementação **somente quando o usuário pedir continuar/desenvolver**, não por ter lido este handoff.

## 18. Não objetivos e riscos conhecidos

- Não executar extensões Android diretamente ou copiar o repositório inteiro do Keiyoushi.
- Não assumir que “Recentes” existe por o site ter “Trending” ou uma aba de ranking.
- Não assumir que um filtro local em 20 cards equivale a pesquisa em toda a base de uma fonte.
- Não assumir que cada versão nova do Keiyoushi é automaticamente compatível com iOS12.
- Não “corrigir” Comix/HotComics passando por bloqueios anti-bot, autenticação ou acesso negado.
- Não permitir que uma falha offline esconda uma regressão real, nem que leitura offline sobrescreva metadados de capítulos.
- Não afirmar que o Build36 foi testado por horas ou que existem métricas de RAM sem medição.
- Não realizar migração destrutiva, limpeza automática ou exclusão de dados como padrão.

---

### Estado final deste handoff

**Documento de planejamento somente.** R1–R8 continuam pendentes de implementação, exceto os fundamentos existentes claramente descritos. A referência validada permanece **Build36 + Webtoons EN 0.1.7**, com leitura offline corrigida e feedback positivo do usuário. O próximo trabalho de produto recomendado é **R1-A: descoberta de obras sem quebrar API v1**.
