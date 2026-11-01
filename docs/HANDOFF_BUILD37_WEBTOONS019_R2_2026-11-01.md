# HANDOFF — Build 37 + Webtoons EN 0.1.9 + Monitor Keiyoushi

**Data:** 2026-11-01  
**Projeto:** AugustoArbulu/MangaReader12 — leitor iOS12 inspirado no Mihon  
**Finalidade:** documentar a sessão longa após o usuário confirmar que o Build36 lê downloads offline e autorizar avançar bastante durante a noite.  
**Regra:** não reiniciar o projeto; confirmar o estado de main e de CI antes de novas alterações. Branch/PR/CI verde/squash merge; nunca escrever diretamente em main.

## 1. Resumo executivo do checkpoint

### Base confirmada no dispositivo

- iOS de teste: 12.5.8.
- Baseline funcional: **Build36 + Webtoons.com EN 0.1.7**.
- Usuário confirmou: capas, detalhes, capítulos, leitura online, download, armazenamento e leitura offline; a correção da falha -1009 do Build36 foi fisicamente confirmada.
- Testes de stress prolongado/RAM não foram medidos. Webtoons motion toon continua fora do escopo.
- Nada disso equivale a validação das outras fontes ou dos recursos novos abaixo.

### Três entregas integradas a main nesta sessão

1. **PR #49 / commit ad881b850923423af5646eaf7371862bcd096a9d:** Build37 e fonte inicial Webtoons EN 0.1.8. Novo menu UIKit Explorar para seções de ranking/gênero/Recentes opcionais, fallback para fontes v1 antigas e controle de respostas obsoletas. Fonte Webtoons separa Populares, Tendências, Originals, Canvas, sete gêneros e acaba com paginação falsa dos rankings.
2. **PR #50 / commit d0b02d23d896d1eebd04c14493b332ac4000136a:** R2-A, monitor **somente de leitura** de 9 fontes Keiyoushi + 3 motores compartilhados. Workflow semanal/manual produz relatórios comparando commits upstream com baseline revisável; não altera fontes.
3. **PR #52 / commit 0d35a8e5412b69d55b0c4310bbe98e46e26766eb:** Webtoons EN **0.1.9**, modo **Recentes (Originals do dia)**. A rota foi verificada no código Keiyoushi Webtoons.kt: lista Originals do dia local com ordenação por atualização. É atualização JS/catálogo, **não exige novo IPA**.

**PR #51** foi encerrado sem merge por conflito documental causado pelo PR50; conteúdo reaplicado integralmente em branch limpa e integrado via PR52. Não há necessidade de reabrir PR51.

## 2. Novo IPA nativo

- Build 37: CFBundleVersion 37, mínimo iOS12.0, compilações Debug e Release em Xcode 15.4/macOS14, auditoria iOS12 e testes JS aprovados.
- Artifact da CI do PR #49: run 41285729859, upload MangaReader12-iOS12-M0.
- Arquivo IPA unsigned extraído e conferido na sessão: MangaReader12-Build37-iOS12.ipa, aproximadamente 15.96 MiB.
- Hash verificado por SHA256: 9c553923736daa4ab1e5291de8053cfcf717f2e15726d0060848293c138ca1ab.
- Instalação via Sideloadly preservando bundle/data container. Se a instalação remover dados, NÃO reinstalar destrutivamente antes de backup e diagnóstico.
- A fonte deve ser atualizada separadamente pelo catálogo para **Webtoons EN 0.1.9**. Apenas instalar o IPA não atualiza automaticamente a fonte já instalada.
- Não existe Build38 nesta sessão, nem obrigação de testar o monitor no iPhone.

## 3. Funcionalidades do Build37 — R1-A, R1-B e início R1-D

### 3.1 Menu de descoberta

- SourceBrowserViewController tem cabeçalho UIKit Explorar: seção selecionada.
- Em source antiga sem recurso opcional browseCategories(), o app mantém popular() e search() do contrato original.
- SourceBrowseCategory tipado: id, title e kind = ranking / genre / latest; valida formato e limita volume de opções. Os seis métodos originais metadata/popular/search/details/chapters/pages não mudaram.
- Uma seção extra é consultada via browse(id,page) **apenas após seleção explícita**.
- Um request antigo não pode sobrescrever resultados de categoria nova: requestEpoch / pendingReload. Paginação deduplicada por ID.
- Se uma source não anuncia latest, o item de Recentes fica desabilitado em vez de simular atualização recente com trending.

### 3.2 Webtoons EN 0.1.9

- Populares chama apenas ranking/popular; page 2 não muda secretamente para outra categoria.
- Outras categorias: Tendências, Originals e Canvas em endpoints de ranking fixos. Primeira página somente, sem falsa paginação.
- Filtros por uma categoria de gênero por vez: Romance, Fantasia, Ação, Drama, Comédia, Suspense, Mistério. São páginas oficiais de gênero do Webtoons, mas os seletores ampliados para card_list/genre_list ainda **não foram fisicamente verificados**. Pode haver lista vazia ou mudanças reais de DOM.
- Recentes (Originals do dia): endpoint /en/originals/<weekday>?sortOrder=UPDATE, com dia local Sunday→Saturday. **Não** inclui necessariamente Canvas, todas as séries ou todos os dias. Um GET e hasNextPage=false.
- Busca por texto, detalhes/capas/capítulos/reader, domínios HTTPS e downloads permanecem no contrato existente.
- Webtoons EN 0.1.9 SHA256 pin no catálogo: d6b0956b88b3a8fcde19ab013178b22044479d9c693df37775dd096920ac3041.
- CI tem mocks de cada rota, recusa de categoria não suportada, ausência de página artificial, integridade SHA, fallback v1 e ordem segura das imagens. **Mocks não reproduzem o HTML vivo no iPhone.**

## 4. Monitor do Keiyoushi — R2-A

- Arquivos: .github/workflows/keiyoushi-upstream.yml, ci/monitor_keiyoushi_upstream.py, ci/keiyoushi-upstream-baseline.json e ci/test_monitor_keiyoushi_upstream.py.
- Execução agendada: segunda 07:17 UTC, best-effort do GitHub Actions; também manual via Actions > Review Keiyoushi upstream changes.
- API pública Github, latest commit por diretório, comparação com baseline fixo de 2026-11-01; publica relatório Markdown e JSON como artifact por 30 dias e job summary.
- A lista inclui nove fontes selecionadas e Iken/Madara/YiiMadara. Não monitora todas as outras dependências do Keiyoushi.
- Zero solicitações aos sites de mangá; zero execução de APKs/Kotlin, zero bypass, zero atualização automática de JS/IPA/DB e nenhum push.
- Mudança upstream resulta em status review (necessita leitura humana do diff). Falha de API resulta em error e job falho, não em status de sucesso fictício.
- Os testes offline da ferramenta foram adicionados ao workflow normal do Build37, então entram no gate de compilação.
- Docs auxiliares: docs/R2_KEIYOUSHI_UPSTREAM_MONITOR_2026-11-01.md.

## 5. Checklist físico objetivo quando o usuário acordar

**Antes:** se possível preservar os downloads existentes e não apagar o app; instalar Build37 sobre Build36, abrir Explorar e atualizar Webtoons EN para 0.1.9 pelo catálogo. Fechar/reabrir a tela da fonte após a atualização.

1. **Populares:** abrir Webtoons EN → Explorar: Populares. Aparecem obras e capas? Rolar até o fim não muda para outro ranking sozinho?
2. **Tendências / Originals / Canvas:** tocar no cabeçalho Explorar, selecionar cada seção. Os títulos mudam coerentemente? As capas aparecem? Lista vazia/erro HTTP?
3. **Gêneros:** testar Romance, Fantasia e Ação (pelo menos). Listas têm obras? Cada card abre detalhes e capítulos? Se lista vazia, registrar qual gênero exatamente.
4. **Recentes (Originals do dia):** conferir se a opção está disponível, se lista obras e se ao trocar de seção não exibe resultados da seção antiga. Essa seção não é global de todos os dias/Canvas.
5. **Busca:** buscar um título conhecido, abrir detalhes, retornar à lista, cancelar a busca, mudar de gênero rapidamente enquanto carregando. Conferir se o app não mistura resultados.
6. **Leitura online:** abrir 1 capítulo, rolar várias imagens, voltar e trocar capítulo; comparar com o funcionamento do Build36.
7. **Modo avião:** abrir um capítulo previamente baixado pela aba Downloads e pela Biblioteca; verificar páginas, progresso e retorno à lista sem erro -1009. Não baixar novamente só para testar.
8. **Persistência:** fechar e reabrir app, conferir categoria/busca selecionada se aplicável, histórico, progresso e dados dos capítulos. A persistência de seleção de categoria não é exigência atual; o progresso de leitura é.

### Ao reportar falhas

Informar App37, iOS12.5.8, Webtoons EN 0.1.9, categoria/tela exata, se era online/offline, qual botão pressionou, mensagem literal HTTP/transporte (se houver), e print quando possível. Não compartilhar URLs com tokens, cookies, headers de autenticação ou credenciais.

**Importante:** em caso de falha nova no leitor ou nos downloads, reverter ao último Build36 funcional, mantendo arquivos locais e backup. Não apagar dados para “consertar” antes do diagnóstico. Site fora do ar/403 não prova bug do app.

## 6. Próximo roadmap após QA

- R1: corrigir apenas gêneros confirmadamente problemáticos pelo feedback iOS12, enriquecer a semântica/paginação real e então adicionar filtros múltiplos/status/sort em fontes que **suportem** essas consultas.
- R2: verificar manualmente primeiro relatório upstream, discutir diferenças relevantes, portar próximas fontes por engines compartilhados e testar sem burlar restrições de site.
- R3: melhorias do leitor (páginas duplas, crop de margens, escala, ações) só depois de confirmar regressões de Build37.
- R4+: Biblioteca com filtros avançados, downloads avançados, CBZ/ZIP, integridade, recursos opcionais. Roadmap completo segue no handoff original.

## 7. Regra para a próxima sessão

- Leia este arquivo + docs/HANDOFF_ROADMAP_MANGAREADER12_2026-11-01.md + PROJECT_STATE.md.
- Reconfira o HEAD atual de main, a versão da fonte instalada no teste e os PRs #49/#50/#52.
- **Aguardar o relato físico** antes de declarar o Build37 estável; nunca assumir que gêneros/Recentes funcionam no aparelho só porque CI passou.
- Não alterar diretamente main nem inventar host/filtro/endpoint. Branch separada, teste e CI verde para cada correção necessária.
- Não reabrir PR51; PR52 integrou integralmente a versão 0.1.9.
