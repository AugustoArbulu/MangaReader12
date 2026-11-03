# Asura Scans EN 0.1.1 — IDs estáveis de obras e capítulos

**Data:** 2026-11-03. **Tipo:** piloto source-only, sem nova IPA. Continua fora do catálogo principal.

## Problema resolvido nesta etapa
Segundo o upstream Keiyoushi, a API `/series` retorna um `slug` estável e uma URL pública `public_url`, cujo sufixo aleatório pode mudar. O piloto 0.1.0 usava diretamente `/comics/{public-slug}` como ID de obra e `/comics/{public-slug}/chapter/{number}` como ID de capítulo. Se o site renovar o sufixo, a Biblioteca pode interpretar capítulos antigos como novos e a leitura salva pode perder a correspondência com os IDs anteriores.

## Alterações `0.1.1`
- Toda nova obra descoberta pela API usa **ID canônico** `https://asurascans.com/series/{slug-da-api}`.
- Cada capítulo público usa **ID canônico** `https://asurascans.com/series/{slug}/chapter/{number}`.
- Os URLs de visualização continuam apontando para `https://asurascans.com/comics/{slug-publico}`; o mapa `slug-estável → URL pública atual` é armazenado **apenas no namespace de dados da fonte** via `Native.storageGet/storageSet`, sem cookies, credenciais, caminhos de imagens ou tokens.
- `details`, `chapters` e `pages` usam o mapa persistido. Em ausência de alias, tentam o caminho público `/comics/{slug}`, que poderá redirecionar ao nome atualizado; **não há bypass nem retries automáticos em erros de acesso**.
- Após uma resposta pública com `finalURL` válida, atualizam o alias registrado. Revisitando Populares/Busca, a API também atualiza o alias mantendo o mesmo ID.
- IDs antigos da versão experimental 0.1.0 em `/comics/` continuam reconhecidos para leitura, se já estiverem salvos. **Não** migra ou remove registros de Biblioteca automaticamente; se uma mesma obra foi adicionada antes de 0.1.1, pode aparecer duplicada como registro antigo e novo, e isso exigirá migração manual/assistida posteriormente.

## Testes offline
O teste `ci/test_asurascans_offline.cjs` cobre:
- `public_url=/comics/sample-comic-zx91a2b3`, `slug=sample-comic` → ID canônico `/series/sample-comic`.
- `Chapter 1` e `Chapter 2` preservam IDs `/series/sample-comic/chapter/{number}`, mas resolvem URLs públicas `/comics/sample-comic-zx91a2b3/chapter/{number}`.
- Um novo runtime (reinício do app) recupera o mapa persistido sem requerer nova consulta de catálogo.
- Um novo sufixo público `sample-comic-new12345` altera apenas `url`, mantendo ID de obra e capítulos estáveis.
- Compatibilidade de leitura com IDs antigos `/comics/`.
- Mantém a recusa de premium/early access, imagens em tiles, host externo, HTTP/403, redirecionamentos e parâmetros desconhecidos.

## Gaps ainda pendentes
1. **Ainda não validado no dispositivo**: formato real da API, HTML Astro e disponibilidade para iOS 12.5.8.
2. **Rotação de slug entre atualizações da Biblioteca**: se uma obra fica longos períodos sem ser buscada e o alias expira, o fallback público precisa ser confirmado no dispositivo; não assumir que o servidor redireciona em todas as situações.
3. **Capas e imagens** em CDNs externos continuam bloqueadas até evidência de hostname legítimo e revisão da allowlist.
4. **Imagens em tiles** precisam de decodificação CoreGraphics validada em uma fase nativa separada, incluindo downloads offline e limites de memória.
5. **Premium** continua não suportado; o piloto não usa credenciais.
6. **Filtros avançados** dependem de dados dinâmicos da própria Asura e de semântica específica para inclusão de gêneros; a interface genérica de exclusões da WeebCentral **não deve ser aplicada artificialmente** a uma API que não oferece exclusão remota.

## QA manual posterior
Depois de atualizar o catálogo experimental, verificar que `Asura Scans EN 0.1.1` carrega listagens públicas. Abrir **somente uma** obra pública, conferir título/detalhes/capítulos. Não tentar capítulos premium; se a leitura disser `tiled images` ou `CDN requires review`, tratar como limite conhecido e fornecer apenas o hostname seguro. Interromper diante de HTTP 403/429.
