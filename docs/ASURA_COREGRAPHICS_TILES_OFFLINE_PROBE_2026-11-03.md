# Asura Scans — protótipo offline de imagens em tiles (CoreGraphics, iOS 12)

**Data:** 2026-11-03. **Status:** prova de conceito isolada, **não incluída no aplicativo nem liberada para leitura/armazenamento**.

## Problema
A extensão Keiyoushi AsuraScans identifica parte das imagens de capítulos com `tiles`, `tile_cols` e `tile_rows`, normalmente uma grade 4×5. O bitmap recebido contém blocos em posições permutadas. O `scrambledImageInterceptor` Android executa um mapeamento: para cada índice de bloco de origem `w`, mover o bloco para o índice de destino `tiles[w]`.

A fonte experimental Asura 0.1.1 para MangaReader12 **recusa essas imagens**, evitando páginas embaralhadas ou downloads ilegíveis. A solução definitiva precisará reproduzir essa transformação no iOS 12, mas não podemos habilitá-la sem validar resultado, consumo de memória e armazenamento offline.

## Protótipo desenvolvido
Arquivo `ci/asura_coregraphics_tiles_probe.swift`. Este arquivo roda somente como teste no CI e não compõe a IPA.

- Entrada: `CGImage`, matriz `tiles`, número de colunas e linhas.
- Validação estrita: permutação completa e sem índices repetidos, colunas/linhas 1–16, até **80 blocos**, dimensões divisíveis, largura/altura <=32.000 e área <=40 milhões de pixels.
- Usa `CGImage.cropping(to:)` e contexto bitmap RGBA `CGContext`, com mapeamento de índices do upstream Android.
- Inclui testes sintéticos com quatro cores distintas, troca de colunas, troca de linhas e identidade 4×5; não baixa conteúdo real da Asura nem manipula dados do usuário.
- Falha com `nil` para permutações inválidas, excesso de dimensões ou inconsistência estrutural, sem tentar adivinhar/reparar blocos.
- Executado por `xcrun swift ci/asura_coregraphics_tiles_probe.swift` em macOS com Xcode 15.4.

## O que falta para integração no app
1. Teste do usuário indicando páginas públicas da Asura que de fato usam tiles e hostnames de mídia legitimamente associados à fonte. Sem esses dados, não abrir CDNs arbitrários.
2. Definir `Page` com campos opcionais `tiles`, `tileCols`, `tileRows` e preservar compatibilidade `Codable` com todos os downloads antigos e fontes atuais.
3. Integrar decodificação em **dois caminhos**: ReaderImageLoader (leitura online/cache) e ChapterDownloadManager (arquivos offline), com garantia de que a imagem armazenada/entregue é a mesma reconstituída corretamente.
4. Escolher serialização PNG/JPEG no armazenamento, pois iOS 12 não tem suporte universal a WebP. Controlar largura/altura, custo temporário de bitmap e memória.
5. Testes de imagens sintéticas multi-pixel, orientação e dimensões não divisíveis, além de testes de recuperação, pausa/retomada e cache de páginas com tiles.
6. Novos gates de CI e teste físico em um **build nativo separado**. Não habilitar em produção só porque o protótipo executa.
7. Conteúdo premium permanece fora de escopo. Reordenar tiles de imagem pública não autoriza acessar páginas restritas.

## Segurança/escopo
Nenhum request direto ao site, script de terceiros em WebView, headers de autenticação, cookies ou contorno de CAPTCHA. Prova puramente geométrica com cores geradas offline.

**Resultado pretendido:** identificar se o algoritmo pode ser implementado de forma determinística e limitada no iOS 12, sem afetar o leitor existente.
