# Build 49 — libwebp 1.6.0 no MangaReader12 iOS 12.5.8

**Data:** 2026-11-04. **Escopo:** infraestrutura nativa de imagem, exclusivamente para WebP além dos formatos existentes. **Asura EN permanece 0.1.2** e **WeebCentral EN permanece 0.1.6**. Branch do PR: `feat/build49-native-webp-decoder`.

## Evidência física do usuário (Build 48)

O leitor apresentou no capítulo de **Overgeared** (2/19 páginas): `The downloaded page is not a valid image. HTTP 200, formato=WebP, MIME=image/webp, bytes=245440, host=cdn.asurascans.com`.

O diagnóstico de capas Asura EN 0.1.2 confirmou **quatro respostas HTTP 200 `image/webp` do mesmo CDN**, com `UIImage=NÃO`:
- capa 1: 136.938 bytes
- capa 2: 525.788 bytes
- capa 3: 170.682 bytes
- capa de detalhes: 136.938 bytes

Detalhes, sinopse e lista de capítulos Asura foram fisicamente confirmados como funcionando no Build 47. **A causa demonstrada de imagens ausentes é falta de decodificação WebP no runtime iOS 12**, e não URL bloqueada ou API de detalhes. Não resolver via extensão falsa de arquivo nem tentativas de contornar bloqueios.

## Implementação

1. Compilação **libwebp 1.6.0** como biblioteca estática para iOS arm64 (`-DCMAKE_SYSTEM_NAME=iOS`, `CMAKE_OSX_DEPLOYMENT_TARGET=12.0`, SIMD e threading desativados para superfície de compatibilidade reduzida). Script `ci/prepare_libwebp_ios.sh`, fonte oficial `https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-1.6.0.tar.gz` com SHA-256 **`e4ab7009bf0629fd11982d4c2aa83964cf244cffba7347ecd39019a9e38c4564`**. Em produção é código vinculado no binário, não download em runtime.
2. Bridging header C `MangaReader12/Networking/MR12WebPBridge.h` importa `webp/decode.h`. Configuração de Xcode aponta para arquivos criados pelo script e `-lwebp`.
3. `WebPImageDecoder` em `MangaReader12/UI/MangaArtwork.swift` só executa libwebp quando os magic bytes são RIFF/WEBP. Primeiro valida `WebPGetInfo`; usa `WebPDecodeBGRAInto` com buffer Swift dimensionado e verifica a conclusão da decodificação. Máximo **20 MiB comprimidos**, **24.000.000 pixels** no leitor e **4.000.000 pixels** nas capas. Converte BGRA com alfa direto para **alfa premultiplicado** aceito pelo CoreGraphics e cria `UIImage` com buffer retido por `CGDataProvider`. Capas são reduzidas até 420 px para o cache quando necessário.
4. `ReaderImageLoader` usa o decodificador em três pontos: arquivo offline local, cache em disco e resposta online. Para PNG/JPEG mantém o decoder nativo `UIImage(data:)`; fluxos de URL e headers não mudaram.
5. `ChapterDownloadImageValidator` aceita WebP **somente se a decodificação integral for bem-sucedida**, para evitar marcar um arquivo truncado como concluído. A verificação PNG IEND e JPEG EOI do Build46, checagem de HTTP e Content-Type e escrita atômica continuam.
6. O texto exato `libwebp-COPYING.txt` do upstream v1.6.0 (BSD-3-Clause) é incluído nos **Resources** do app.

## Regressões

- CI `ci/test_build49_webp.py`: constrói o mesmo libwebp 1.6.0 para **host macOS** (separado do iOS), decodifica um WebP lossless real de 2×2 pixels com transparência, valida dimensões e resultado não-vazio, e exige falha de decodificação para payload parcial e HTML. Valida caminho C bridge, Xcode, limites de memória e pontos de chamada para capas/leitor/download.
- `ci/test_build46_download_integrity.py` executa o validador PNG/JPEG original com stub de WebP isolado (validação WebP verdadeira é coberta pelo teste C acima e compilação iOS).
- Mantém os demais contratos offlines, integridade, seletores Astro, segurança do transport, WeebCentral, CBZ, Swift build Debug/Release e verificações de minos iOS12.
- **QA física ainda necessária**: o CI macOS valida a biblioteca e o app compilado, mas não substitui leitura contínua no aparelho antigo.

## QA no dispositivo (após IPA Build49)

1. Instalar a IPA **Build 49 por cima do Build 48** usando Sideloadly; não desinstalar para preservar Biblioteca e Downloads.
2. Não reinstalar fontes: **Asura EN 0.1.2** e **WeebCentral EN 0.1.6** continuam.
3. Abrir Asura → Populares e conferir **três capas**; em detalhes verificar a capa da mesma obra.
4. Abrir o mesmo capítulo público de **Overgeared**; percorrer **todas as 19 imagens**, procurando páginas vazias e falhas após mudar modo `Páginas`/ `Webtoon`. Os limites de 24M pixels podem rejeitar imagens extraordinariamente grandes; reportar detalhes do erro se ocorrer.
5. Baixar um capítulo público pequeno em WebP. Aguardar `Concluído`. Ativar modo avião e percorrer a leitura offline completa.
6. Testar uma obra WeebCentral que já funcionava com JPEG/PNG (regressão), sem refazer extensivamente todos os capítulos.
7. Se alguma página tiver `tiles`, continuará sendo recusada pela fonte Asura: **não** confundir isso com suporte WebP, que é uma etapa distinta. Capítulos premium/protegidos permanecem fora de escopo.
8. Se o CDN retornar HTML, HTTP 403/429 ou imagens excessivamente grandes, não refazer requests repetidamente ou contornar proteções. Enviar o erro textual exato.

## Próximas limitações

- Nenhum recurso para imagens `tiles` da Asura está conectado; há protótipo separado em `ci/asura_coregraphics_tiles_probe.swift`.
- O downloader WebP decodifica uma vez para validar e o leitor decodifica novamente para exibir; em iPads de pouca memória, observar lentidão/terminação, não aumentar limites às cegas.
- Arquivos instalados antes desta build não são migrados nem apagados. A validade dos novos dados é verificada no download.
- Quando arquivos WebP físicos forem confirmados, avaliar se é necessário um caminho de redução para páginas excepcionalmente altas em vez de exceder 24M pixels.

## Referências
- API de decodificação WebP: https://github.com/webmproject/libwebp/blob/v1.6.0/doc/api.md
- Fonte e licença: https://github.com/webmproject/libwebp/tree/v1.6.0
- Build48 de diagnóstico: `docs/BUILD48_ASURA_MEDIA_DIAGNOSTICS_2026-11-04.md`
