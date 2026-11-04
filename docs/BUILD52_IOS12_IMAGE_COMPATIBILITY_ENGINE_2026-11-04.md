# Build 52 — Compatibility Engine de imagens (iOS 12.5.8)

Data: 2026-11-04. Base fisicamente testada: Build 51 / PR #81. Branch: `feat/build52-ios12-image-compatibility-engine`.

## Resultado técnico
- Centraliza o caminho de imagens em `ImageCompatibilityDecoder.cover/page`, usado tanto pelo leitor online como offline e pela Biblioteca.
- Mantém libwebp 1.6.0 original, SHA-pinned, sem solicitações extras a Asura/WeebCentral.
- Para WebP de páginas acima de 24 milhões de pixels, usa o decoder escalável com buffer externo BGRA de saída, limite 24M pixels/32.768 px. Em vez de descartar uma página inteira, cria cópia reduzida para visualização; não modifica o arquivo original baixado.
- Para JPEG/PNG/GIF/HEIC suportado pelo ImageIO presente no iOS12, faz verificação de assinatura, integridade ImageIO, dimensões e orçamento de pixels **antes** de decodificar. Imagens grandes são decodificadas para resolução limitada com ImageIO, sem fallback não limitado via UIImage(data:).
- Limites por entrada: 20 MiB comprimidos e até 128M pixels de origem / 100.000 px em cada eixo; até 24M pixels de saída no leitor ou 420 px por lado para capas.
- AVIF permanece **detectado, mas não decodificado**. Não afirmar compatibilidade AVIF antes de compilar libavif + AV1 e realizar teste físico. PDF/HTML/JSON também não são usados como páginas.
- Não modifica transporte URLSession, TLS, cookies, allowlists, Cloudflare, premium, downloads salvos, registros SQLite ou caminhos dos arquivos.

## Validações
- `ci/test_build52_image_engine.py` compila o helper Swift real de dimensionamento e testa página alta, capa 5MP, limites e entradas inválidas.
- `ci/test_build49_webp.py` preserva decodificação C real WebP e testes de segurança anteriores, mais novo wiring do leitor.
- Pipeline iOS 12 com Debug, Release e IPA não assinada.
- QA física necessária para confirmar escala de WebP longos, JPEG/PNG grandes e ausência de páginas cortadas. Não alterar `main` até CI passar.

## Riscos e próximos passos
- Alguns WebP com 100M+ pixels ou largura/altura acima dos limites continuam recusados por segurança.
- Decodificação de WebP de 24M pixels pode consumir cerca de 96 MiB só no buffer BGRA; medir no iPad antes de elevar o teto.
- Para AVIF usar implementação de codec estático verificada, dependências com hash, licenças e limites claros. Sem isso, apenas diagnóstico — não falsa promessa.
- Voltar ao roadmap acordado (backup de favoritos fixados, seleção múltipla de capítulos e Biblioteca com atualização) após estabilização da infraestrutura de compatibilidade.
