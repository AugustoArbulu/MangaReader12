# Build 48 — Asura: diagnóstico seguro de capas e páginas inválidas (iOS 12.5.8)

**Data:** 2026-11-04  
**Situação de QA:** usuário confirmou que Asura EN 0.1.2 no Build 47 carrega **título, sinopse, detalhes e lista de capítulos**. No entanto, **capas continuam ausentes**; abrir um capítulo exibe `The downloaded page is not a valid image.`. Não foi validado o formato real dos bytes retornados pelo CDN.

## O que podemos concluir do erro
No `ReaderImageLoader.finish`, quando o request retorna HTTP 2xx, o leitor tenta `UIImage(data: response.data)`. O erro exato ocorre quando esse método devolve `nil`. Isso **não comprova** que o arquivo seja WebP: pode ser HTML retornado com HTTP 200, AVIF, conteúdo corrompido ou qualquer formato não decodificado. O parser Astro e a listagem funcionam, portanto não voltar a mexer neles sem nova evidência.

A extensão Android Keiyoushi Asura tem tratamento de `tiles` e usa decodificação Android. O iOS 12 não oferece necessariamente os mesmos formatos. O protótipo CoreGraphics já existente recompõe tiles *apenas em testes*, e não está conectado ao app. **Não habilitar tiles ou premium com base apenas nesse relatório.**

## Código Build 48 (somente diagnóstico; sem bypass)
1. `MangaReader12/UI/MangaArtwork.swift`: enum `ImageResponseDiagnostics` classifica magic bytes **PNG, JPEG, GIF, WebP, AVIF, HEIC, PDF, HTML, XML, JSON-like, empty, unrecognized**. Também normaliza Content-Type (só estrutura segura MIME), count de bytes, HTTP status e hostname permitido em relatório. Não usa o conteúdo do body, URLs completas, paths, query strings, cookies ou dados de autenticação.
2. `MangaReader12/UI/ReaderViewController.swift`: quando há **HTTP 2xx, mas UIImage não consegue decodificar**, mensagem passa a incluir `HTTP 200, formato=..., MIME=..., bytes=..., host=...`. O mesmo leitor, cache, limites e tratamento de erros são preservados. Nenhuma requisição extra.
3. `MangaReader12/UI/SourceBrowserViewController.swift`: habilita **Testar capas** para `kei.asurascans.en`, reaproveitando o diagnóstico de Webtoons, com até **três capas visíveis e uma capa de detalhes** por ação explícita do usuário, sem loops/retries. Botão superior **Testar capas** e swipe em obra individual **Testar capa**. Relatório agora inclui assinatura do arquivo (`formato`) além de tipo MIME, HTTP e resultado do `UIImage`. Captura `coverDiagnostic` da Asura 0.1.2 a partir do mesmo snapshot de catálogo; não faz requests extras para descobrir URL.
4. O diagnóstico específico `inspectDetailsCover` continua exclusivo da Webtoons, sem executar métodos indisponíveis na Asura.
5. **Build 48**: `CURRENT_PROJECT_VERSION` e rótulo em Configurações sincronizados. Atualização IPA necessária; **fonte Asura permanece 0.1.2**, não há motivo para repiná-la ou alterar CDN sem dados físicos.

## CI
`ci/test_build48_image_diagnostics.py` extrai o código Swift real e usa `xcrun swift` para testar PNG/JPEG/WebP/AVIF/HTML/JSON sintéticos. Rejeita a inclusão de token ou path/query no relatório. Também exige a ligação do novo erro ao leitor e a ativação do teste de capa para a Asura. Rodam igualmente os testes anteriores de parser Astro Build47 e de integridade ImageIO Build46, a compilação Debug/Release e os contratos da WeebCentral.

## Teste físico mínimo pós-IPA
1. Instalar **Build 48 por cima do Build 47**, sem desinstalar. Manter **Asura EN 0.1.2**.
2. Abrir **Explorar → Asura → Populares → Testar capas**. Copiar relatório, enviá-lo sem qualquer URL completa, cookies ou tokens.
3. Abrir a mesma obra do teste Build47, selecionar **um único capítulo público**. Enviar texto integral da nova mensagem `The downloaded page is not a valid image. HTTP ..., formato=..., MIME=..., bytes=..., host=...`.
4. Se mostrar `formato=WebP` com `MIME=image/webp`, confirmou formato a implementar (decoder WebP compatível com iOS12, sujeito a limite de memória), **não** trocar extensão da URL por .jpg sem evidência.
5. Se `formato=HTML`, investigar HTTP 200 com página de erro/anti-hotlink, mas **não** contornar WAF/autenticação.
6. Se `HTTP 403/429`, interromper. Se `formato=unrecognized`, continuar investigação a partir do host e MIME; não inventar detalhes sobre o payload.
7. Capítulos premium/tiles continuam **fora de escopo** e não devem ser testados repetidamente; verificar WeebCentral 0.1.6 só após o diagnóstico central.

**Resultado esperado:** separar causa do formato, resposta inesperada ou host sem modificar sessão de navegação, dados offline, confiança TLS ou limites de acesso. **Esta versão diagnostica; não promete que a Asura já renderize imagens.**
