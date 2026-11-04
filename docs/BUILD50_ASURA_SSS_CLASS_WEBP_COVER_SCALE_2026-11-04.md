# Build 50 — Asura: capas WebP de resolução alta, decodificação reduzida

**Data:** 2026-11-04. **Fonte Asura EN:** 0.1.2 (sem mudança). **Build anterior:** 49.

## Evidência física (SSS-Class Suicide Hunter)

O usuário confirmou que Asura voltou a funcionar após integração do libwebp, exceto capas de duas obras. Uma é **SSS-Class Suicide Hunter**. O diagnóstico da capa (na lista e nos detalhes) retornou:

- iOS: 12.5.8, Build 49, Asura EN experimental
- Host autorizado: `cdn.asurascans.com`
- URL reconhecida pelo adaptador e recebida no modelo Swift, sim
- HTTPS HTTP **200**, `image/webp`, **525.788 bytes**, formato WebP para capa da lista e dos detalhes
- `UIImage=NÃO` é diagnóstico do **decoder nativo antigo do iOS 12**. Isso não testa o libwebp vinculado no Build49, nem prova que os bytes são inválidos

### Hipótese técnica e limitação concreta

O Build49 usa `WebPImageDecoder.image(from: data, maxPixels: 4_000_000)` para **alocar e decodificar a capa inteira**, rejeitando capas de origem acima de quatro milhões de pixels, e só depois reduz o desenho para no máximo 420 px. O diagnóstico não incluía dimensões, então **a imagem específica de SSS-Class Suicide Hunter ainda não foi medida**. A limitação é real e pode explicar o comportamento. Não aumentar o teto de memória para contornar: decodificar uma capa diretamente para resolução pequena.

## Implementação

- `MR12WebPBridge.h`: novo helper C `MR12WebPDecodeScaledBGRA`, via `WebPDecoderConfig` + `use_scaling = 1`, buffer externo BGRA de no máximo 420 x 420 pixels, sem imagens de saída parciais. Verifica ponteiros, limites de tamanho, largura/altura e stride; `WebPFreeDecBuffer` após decodificação integral.
- `WebPImageDecoder.dimensions(of:)`: obtém as dimensões pelos headers WebP, sem alocar pixel buffer; limita 20 MiB de entrada, largura/altura de até 16.384 e fonte de até 64M pixels.
- `WebPImageDecoder.thumbnail(from:)`: calcula dimensões reduzidas preservando a proporção original, decodifica via helper C no buffer Swift de <=420x420 BGRA, premultiplica alfa e cria CGImage seguro em iOS12. **Não passa pela decodificação full-size de 4M pixels**.
- `CoverImageLoader.decodeCover`: usa `thumbnail` para WebP na listagem, nos detalhes e nas capas em cache. PNG/JPEG seguem com ImageIO. O pipeline de páginas online/offline e integridade de downloads permanece **inalterado**.
- `SourceBrowserViewController`: relatório manual `Testar capa(s)` para WebP passa a inspecionar dimensões e testar o **mesmo decoder de miniatura usado pelo app**. Campo `decodificador-app=SIM/NÃO` substitui a conclusão enganosa `UIImage=NÃO`; não imprime URL completa, query, token nem dados da resposta.
- Numeração do app **Build 50**; iOS 12.0 deployment target mantido.

## Teste automatizado CI

`ci/test_build49_webp.py` mantém o teste da libwebp real e amplia com **WebP RGBA válido de 2.500 x 2.000 px (5 milhões)** gerado **offline** pela libwebp. Valida o decoder C escalando para 420 x 336 BGRA, preservação da cor e alfa, rejeição de payload truncado, HTML e tamanho inválido de buffer. Compilação Xcode de integração iOS12 Debug/Release. Não faz requests ao site, não baixa imagens reais do usuário.

## QA físico mínimo

1. Instalar a IPA Build50 sobre o Build49, sem desinstalar; fonte Asura EN permanece 0.1.2.
2. Em **SSS-Class Suicide Hunter**, confirmar capa da listagem e detalhes. Se continuar vazia, deslizar a obra e escolher `Testar capa`; enviar `dimensões=...` e `decodificador-app=...`, além do HTTP/MIME.
3. Testar a segunda obra afetada e informar seu nome.
4. Confirmar 1–2 capas que já carregavam anteriormente. Não é necessário repetir o teste completo de Overgeared se a leitura continuou estável.
5. Se a capa real ultrapassar 64M pixels/16.384 px ou continuar inválida, não remover limites sem análise; o diagnóstico mostrará se o decoder falhou sem expor a URL.
6. Sem alterações nos controles de premium, tiles, sessão, headers, WAF, TLS, IP ou repositórios. Nenhum request adicional em background.

**Limite da evidência:** o teste CI prova o algoritmo com WebP de 5MP gerado localmente. Somente o dispositivo pode confirmar o resultado da obra específica.
