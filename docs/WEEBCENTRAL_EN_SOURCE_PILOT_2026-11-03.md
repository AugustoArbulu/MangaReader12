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
7. Sem nova IPA: scripts podem ser distribuídos por catálogo **apenas após revisão, SHA-256 do arquivo e autorização do teste físico**. Este PR não adiciona a fonte ao catálogo principal.

## Testes offline

`node ci/test_weebcentral_offline.cjs` valida: seis funções obrigatórias + descoberta; formato de resultados, URLs, contagem/paginação, ordenação, campos de detalhes, IDs estáveis, ordem/scanlator dos capítulos, imagens, ausência de hosts externos, rejeição de URLs não HTTPS, resposta 403 sem retry, rejeição de redirect externo. Estes testes usam HTML simulado e não constituem prova de funcionamento real.

## Critérios de QA físico (somente após aprovação do candidato)

1. Em iOS 12.5.8, instalar a fonte por um catálogo isolado de testes com script hash fixado, sem alterar Biblioteca Webtoons.
2. Abrir a lista Popular: anotar erro HTTP, títulos e se as capas aparecem. Em caso de 403/429/rejeição, **interromper** sem contornar.
3. Buscar título permitido, abrir detalhes, capítulo e verificar URLs HTTPS. Em caso de CDN legítima ausente na allowlist, registrar **somente o hostname**, sem cookies/URLs assinadas, e passar por revisão.
4. Baixar um capítulo pequeno e confirmar leitura offline após modo avião/reinício; atualizar capítulos da Biblioteca e examinar o feed de Atualizações.
5. Se houver qualquer mudança de estrutura HTML, registrar o erro, corrigir com fixture pública/permitida e repetir offline antes de novo teste remoto.

## Asura — próxima etapa separada

A Asura mantém API JSON, propriedades do Astro embutidas no HTML e imagens de capítulos potencialmente divididas em tiles. Precisa de um adaptador e testes próprios; não usar este código nem declarar que a Asura já está implementada.

**Status final desta fase:** candidato source-only de WeebCentral, CI/contrato offline; **nenhum recurso de acesso remoto ou download fisicamente validado**.
