# WeebCentral EN 0.1.4 — gêneros ausentes nos detalhes

**Data:** 2026-11-03. **Escopo:** somente adaptador JavaScript e catálogo experimental. **Não exige Build 46 nem nova IPA.**

## Evidência física
No iOS 12.5.8, usuário confirmou funcionamento aparente dos filtros gerais da WeebCentral **0.1.3** no **Build 45**, mas relatou que o painel **Detalhes** das obras não apresentava gêneros.

A UI nativa de detalhes, em `MangaReader12/UI/MangaArtwork.swift`, já apresenta `manga.genres` no campo `genresView`. Portanto, o problema está na extração de metadados do adaptador, e não em uma falta de suporte do layout.

## Causa
O parser 0.1.3 reconhecia somente rótulos em singular e pontuados, por exemplo `Tag: Fantasy`, mas um fixture público da WeebCentral de *One Piece* mostra:
- `<strong>Author(s): </strong>` com o autor em um link;
- `<strong>Tags(s): </strong>` com links individuais `?included_tag=Action` e `?included_tag=Shounen`;
- `<strong>Type: </strong>` com link `?included_type=Manga`;
- `<strong>Description</strong><p>...` sem dois-pontos.

A extensão Keiyoushi já extrai esses gêneros pela leitura dos links, não pela reconstrução de frases.

Referências públicas:
- https://github.com/keiyoushi/extensions-source/blob/main/src/en/weebcentral/src/eu/kanade/tachiyomi/extension/en/weebcentral/WeebCentral.kt
- https://github.com/tiagohs/hqr-comics-reader/blob/main/sources/weebcentral/src/commonTest/kotlin/com/tiagohs/hqr/sources/weebcentral/WeebCentralSourceTest.kt

## Correção
- `source.details` seleciona separadamente links de `included_tag=` e `included_type=` dentro da seção de metadados, preservando cada nome de gênero/tipo e eliminando duplicações.
- Lê rótulos de `<strong>`, reconhecendo `Author(s)`, `Tags(s)`, `Tag(s)` e variantes, além de descrição sem dois-pontos.
- Extrai a descrição do parágrafo da segunda seção para evitar confundir outros campos.
- Quando o HTML não contém links canônicos, usa **somente etiquetas explicitamente declaradas** nos campos rotulados como `Tag(s)`, `Tags(s)` ou `Type` — não deduz gêneros por título, capa ou conteúdo.
- Mantém os seis métodos obrigatórios, filtros gerais 0.1.3, lista de capítulos, extração de páginas, allowlist dos três hosts e validação HTTPS. **Nenhum pedido adicional ao site.**

## Testes offline
`node ci/test_weebcentral_offline.cjs` inclui fixture de detalhes no formato publicado para *One Piece* e verifica:
- `genres` contém exatamente `Action`, `Shounen`, `Manga` (links individuais);
- `author`, `status`, `description`, `cover` e alias preservados;
- links duplicados não causam repetição de gênero;
- formatos sem links, com `Tags(s): Romance, Fantasy`, têm fallback seguro;
- sem novas requisições; restante dos testes de paginação, filtros remotos, imagens, URLs, 403 e SHA-256 do catálogo permanece válido.

## QA físico necessário
1. No **Build 45**, abrir **Explorar → Repositórios** e atualizar o catálogo experimental WeebCentral (mesma URL já instalada).
2. Atualizar a fonte para **WeebCentral EN 0.1.4** (nenhuma IPA nova).
3. Abrir **One Piece → Detalhes** e verificar os gêneros esperados (`Action`, `Shounen`, `Manga`) e a descrição.
4. Abrir mais uma obra, preferencialmente com vários gêneros, para confirmar que cada etiqueta aparece separada.
5. Confirmar que capítulos e imagens continuam carregando e que os filtros gerais 0.1.3 seguem funcionando.
6. Se gêneros ainda estiverem ausentes, reportar apenas a obra e se a descrição/status aparecem. Nenhum HTML privado, URL assinada ou token é necessário.

**Status:** compatibilidade de parser coberta por fixtures offline; **QA físico de gêneros ainda não foi confirmado**.
