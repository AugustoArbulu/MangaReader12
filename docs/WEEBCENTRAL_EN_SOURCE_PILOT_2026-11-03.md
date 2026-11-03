# WeebCentral EN — adaptação experimental Source API v1 (offline)

**Data:** 2026-11-03  
**Objetivo confirmado pelo usuário:** WeebCentral e Asura como **duas fontes completas**, com busca, Biblioteca, atualizações de capítulos e downloads offline, seguindo os recursos já existentes no MangaReader12.  
**Nesta etapa:** somente o adaptador **WeebCentral**, sem migração de fontes existentes, sem alterações Swift, sem solicitações ao site, sem APK Android.

## Referência pública

- Keiyoushi: https://github.com/keiyoushi/extensions-source/tree/main/src/en/weebcentral
- Fonte: `src/en/weebcentral/src/eu/kanade/tachiyomi/extension/en/weebcentral/WeebCentral.kt`.
- Filtros: `src/en/weebcentral/src/eu/kanade/tachiyomi/extension/en/weebcentral/Filters.kt`.
- Declaração de origem: `src/en/weebcentral/build.gradle.kts`, `https://weebcentral.com`, `ContentWarning.MIXED`.
- A implementação JavaScript é **não oficial**. Não utiliza APK, Kotlin ou interface Android durante a execução.

## Arquitetura

O arquivo `fixtures/keiyoushi-weebcentral-en.js` implementa seis métodos de `source`:

| Contrato | Origem conceitual | Resultado esperado |
| --- | --- | --- |
| `metadata` | Manifesto WeebCentral EN | Identidade de fonte |
| `popular(page)` | `/search/data` com ordenação Popularity | Cards e paginação |
| `search(query,page,filters)` | `/search/data` com texto e offset | Cards e paginação; filtros avançados **não portados** |
| `details(id)` | Página `/series/{id}/{slug}` | Título, autor, artista, gêneros, status, descrição, capa |
| `chapters(id)` | `/series/{id}/full-chapter-list` | Lista de capítulos com IDs persistentes |
| `pages(chapterId)` | Rota `/images` com visualização `long_strip` | URLs de páginas permitidas e headers normais de Referer |

Também expõe `browseCategories` (Populares e Recentes) e `browse` como integração opcional de descoberta. O restante do produto (Biblioteca, feed de atualizações, leitor e downloads) usa a infraestrutura atual do app **se** os seis métodos funcionarem no iPhone.

O adaptador usa `Native.httpRequest` e `Native.htmlSelect`, exatamente como os pilotos M13-A; o HTML não executa scripts do site. Evita seletores `:has` / `:contains`, que não têm suporte garantido no WebKit antigo.

## Segurança e limitações conhecidas

1. O domínio de origem é **somente** `weebcentral.com` e `www.weebcentral.com` para pedidos de catálogo e capítulos, HTTPS padrão. URLs externas, HTTP e redirects inesperados falham, sem reintentos.
2. Capas e páginas externas ao domínio são rejeitadas **até confirmar quais hosts de imagens a fonte usa legitimamente**. Esta é uma lacuna explícita de compatibilidade: não registrar uma fonte como funcional antes de QA de CDN e leitura. Não inventar hosts ou abrir domínio geral.
3. A implementação não acessa site protegido, não controla CAPTCHA, não modifica TLS, user-agent, cookies, fingerprint ou autenticação.
4. `GET /search/data` aceita 32 cards por página conforme Keiyoushi; a paginação de continuar depende da existência do botão retornado no HTML. Isso não foi validado contra HTML vivo.
5. Em detalhes, os dados são extraídos por rótulos textuais comuns de campos HTML; a semântica exata dos rótulos e a imagem de capa ainda dependem de QA físico. Não declarar cobertura de filtros avançados.
6. A taxa de requisições do upstream é limitada; o adaptador deve ser usado apenas por testes manuais de baixa frequência quando o acesso for autorizado. Não alterar o `HTTPClient` nem introduzir bypass.
7. Sem nova IPA: a fonte está disponível **somente por um catálogo piloto separado**, `fixtures/weebcentral-pilot-repository.json`, com SHA-256 fixado. Não entra no catálogo principal nem é marcada como funcional. A instalação deve ser manual/opt-in **após CI verde e merge**; serve exclusivamente para obter evidência de compatibilidade no iPhone.
8. O manifesto piloto marca `nsfw: true` por cautela, pois o upstream declara `ContentWarning.MIXED`; isso não implica que todo título contenha material adulto.

## QA físico 0.1.0 — resultado e revisão 0.1.1 (2026-11-03)

**Evidência do usuário em iOS 12.5.8:** Populares mostra títulos, mas **nenhuma capa**; detalhes também sem capa; ao abrir capítulo, o adaptador retorna `Source failed: No permitted page-image hosts found; CDN requires review`. Portanto, **listagem, rota da obra e chegada até o leitor funcionam parcialmente**. Não afirmar que a imagem foi bloqueada pelo servidor: a própria versão 0.1.0 eliminava URLs fora de `weebcentral.com` (e também produzia a mesma mensagem se o seletor não retornasse imagens).

**Adaptação 0.1.1:** manter a lista de domínios estrita, sem tentar baixar hosts desconhecidos; incluir `coverDiagnostic` opcional com **apenas hostnames** nos cards; tratar `data-src` e `data-original` antes de placeholder `src`; separar os erros de zero elementos, URL ausente e hostname externo. Se apenas parte das páginas for permitida, **falhar o capítulo inteiro** em vez de permitir download/leitura incompleta.

**Novo teste após atualizar a fonte (não precisa de nova IPA):** atualizar o repositório piloto em Explorar e instalar/atualizar `WeebCentral EN (experimental)` para versão `0.1.1`. Abrir **um capítulo já listado**. Copiar o texto do erro: se contiver `Blocked image hostnames: exemplo.tld`, reportar somente esses hostnames. Se apontar `no page images matched` ou `No usable HTTPS image URL`, investigar seletor/atributo sem tocar na allowlist. Não fornecer URL de imagem completa, caminhos, query, cookies ou credenciais. **Não** continuar a repetição de requests se aparecer 403/429 ou recusa do serviço.

**Depois do relato:** somente incluir um domínio externo de CDN após confirmar sua vinculação à fonte e revisar a política de segurança do cliente HTTP. Permanecem pendentes testes reais de leitura integral, capas, atualização de capítulos e download offline. A Asura permanece fora do escopo deste patch.

## QA físico 0.1.1 e ajuste 0.1.2 — seletor Jsoup/WebKit (2026-11-03)

**Relato novo do usuário, iOS 12.5.8, fonte 0.1.1:** as capas continuam ausentes, e a abertura de um capítulo retornou `Source failed: WeebCentral: no page images matched the chapter HTML selector`. A requisição de capítulo alcançou a fase de parsing, porém a extração de páginas retornou zero elementos.

**Causa encontrada no código da adaptação:** o Keiyoushi usa Jsoup `section[x-data~=scroll] > img`. Em **Jsoup**, `[attr~=regex]` significa expressão regular. Em **CSS/WebKit**, `[attr~=word]` significa uma palavra separada por espaços. Copiar literalmente o seletor alterou sua semântica. Para o parser DOM do iOS, a versão 0.1.2 usa `section[x-data*="scroll"] > img`, que faz a comparação de substring do atributo. A correção é fundamentada nas semânticas documentadas dos dois parsers, mas **ainda precisa de teste físico**; não implica automaticamente que os URLs/imagens funcionarão.

**Diagnóstico sem novos pedidos HTTP:** o mesmo retorno HTML do capítulo agora é avaliado também com seletores estruturais que contam `section[x-data*="scroll"]`, imagens aninhadas nesse container e imagens da página inteira. Se não houver imagem direta, o erro informa somente as três contagens — nunca HTML, caminho, token, cookies ou URLs assinadas. Não usar HTML de outras seções como fallback automático, pois isso poderia misturar imagens que não são páginas do capítulo.

**Capas e CDNs:** exemplos públicos de HTML da WeebCentral, mantidos em outros projetos, identificam `temp.compsci88.com` servindo capas em WebP e fallback JPEG; um fixture de páginas identifica `hot.planeptune.us` servindo PNG. A revisão 0.1.2 **adiciona exclusivamente esses dois hosts** à allowlist do catálogo, sem permissões genéricas para CDNs externos. Prioriza o `<img src="...jpg">` de fallback para capas no iOS 12, porque o decodificador nativo de WebP não é garantido nesse sistema. Evidências:
- https://github.com/tiagohs/hqr-comics-reader/blob/main/sources/weebcentral/src/commonTest/kotlin/com/tiagohs/hqr/sources/weebcentral/WeebCentralSourceTest.kt
- https://github.com/serplay/manhwa-downloader/blob/main/server/src/sources/fixtures/weebcentral_search.html
- https://github.com/readah/lnreader-ios/blob/main/Services/Sources/Native/WeebCentralSource.swift

Os exemplos são **fixtures históricas públicas**, não resposta HTTP recente da WeebCentral. Os domínios poderão mudar; essa atribuição precisa de verificação no iPhone. O parser agora aceita também `section#chapter-images > img`, identificado nos exemplos, além do seletor `x-data` compatível com CSS.

**Teste recomendado:** atualizar manualmente o catálogo piloto e instalar a fonte `WeebCentral EN (experimental)` versão **0.1.2** pelo mesmo endereço HTTPS; a compilação do app/IPA não precisa mudar. Em Populares, verificar as **capas JPEG** e abrir uma obra. Em seguida abrir **um capítulo já visível**: testar se todas as páginas aparecem e se é possível percorrer até o fim, sem download ainda. Se indicar `Blocked image hostnames`, enviar apenas o hostname; se indicar `no direct chapter images`, enviar as contagens. Não insistir se houver HTTP 403/429/aviso de bloqueio. Somente depois de visualização completa testar um download pequeno, atualização na Biblioteca e uso offline. Nenhum funcionamento foi declarado validado por esses testes offline.

## Testes offline

`node ci/test_weebcentral_offline.cjs` valida: seis funções obrigatórias + descoberta; formato de resultados, URLs, contagem/paginação, ordenação, campos de detalhes, IDs estáveis, ordem/scanlator dos capítulos, imagens, ausência de hosts externos, rejeição de URLs não HTTPS, resposta 403 sem retry, rejeição de redirect externo. Estes testes usam HTML simulado e não constituem prova de funcionamento real.

## Critérios de QA físico (somente após aprovação do candidato)

1. Em iOS 12.5.8, após aprovação do PR/CI, abrir `Explorar → + → Inserir URL HTTPS` e adicionar o catálogo piloto: `https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/weebcentral-pilot-repository.json`. Instalar manualmente **WeebCentral EN (experimental)**, sem alterar Biblioteca Webtoons.
2. Abrir a lista Popular: anotar erro HTTP, títulos e se as capas aparecem. Em caso de 403/429/rejeição, **interromper** sem contornar.
3. Buscar título permitido, abrir detalhes, capítulo e verificar URLs HTTPS. Em caso de CDN legítima ausente na allowlist, registrar **somente o hostname**, sem cookies/URLs assinadas, e passar por revisão.
4. Baixar um capítulo pequeno e confirmar leitura offline após modo avião/reinício; atualizar capítulos da Biblioteca e examinar o feed de Atualizações.
5. Se houver qualquer mudança de estrutura HTML, registrar o erro, corrigir com fixture pública/permitida e repetir offline antes de novo teste remoto.

## Asura — próxima etapa separada

A Asura mantém API JSON, propriedades do Astro embutidas no HTML e imagens de capítulos potencialmente divididas em tiles. Precisa de um adaptador e testes próprios; não usar este código nem declarar que a Asura já está implementada.

**Status final desta fase:** candidato source-only de WeebCentral com catálogo experimental separado e checksum; **nenhum recurso de acesso remoto ou download fisicamente validado**. Não confundir testes offline com liberação de uso em produção.
