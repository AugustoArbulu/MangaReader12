# Build 46 — validar imagens antes de marcar downloads offline como completos

**Data:** 2026-11-03. **Escopo:** infraestrutura nativa de downloads; beneficia WeebCentral, Webtoons.com e fontes públicas da API v1.

## Diagnóstico
O `ChapterDownloadManager` já exigia HTTP 2xx, controle de tamanho por `HTTPPolicy` e gravação atômica no sandbox. Contudo, um servidor/CDN poderia responder **HTTP 200 contendo uma página HTML** de erro, captcha ou indisponibilidade, e o gerenciador salvaria os bytes como `page-00000.bin`, avançaria o progresso e eventualmente marcaria o capítulo como concluído. O leitor usa `UIImage(data:)`, logo falharia depois em modo offline.

Isto é um risco genérico de integridade, **não evidência de que ocorreu na WeebCentral**.

## Mudança Build 46
- Adicionado `ChapterDownloadImageValidator.canStore(data:headers:)` dentro do mesmo arquivo nativo e sem alterações de API pública.
- Rejeita corpo vazio, `Content-Type` textual/JSON/XML (comparação sem diferenciar maiúsculas e minúsculas) e arquivos que `ImageIO` não reconhece como imagem **completa**.
- Usa `CGImageSourceCreateWithData` e `CGImageSourceGetStatusAtIndex`, sem renderizar bitmaps inteiros no download, reduzindo carga de memória no iOS 12. Como o ImageIO pode reconhecer PNGs incompletos pelo cabeçalho, exige também o chunk final `IEND` do PNG e o marcador `EOI` perto do fim do JPEG.
- O download rejeitado recebe o erro claro `ChapterDownloadError.invalidImagePayload`, muda para estado `failed` pela rotina existente e **não incrementa o número de páginas gravadas**.
- A fila e retomada persistente existentes continuam inalteradas. Não mexe em arquivos de capítulos já finalizados.
- A etapa de leitura online permanece com a validação existente do próprio leitor (`UIImage(data:)`).
- Código nativo Build 46 com `CURRENT_PROJECT_VERSION` e interface de Configurações sincronizados.
- O fix do parser de 4.000 capítulos/1.500 páginas do Build 44 e os filtros da WeebCentral do Build 45 permanecem.

## Testes de CI (sem conexão à internet)
`python3 ci/test_build46_download_integrity.py` extrai o **código Swift real** entre marcadores do arquivo nativo, compila e executa com `xcrun swift` em macOS:
1. Constrói um PNG 1 × 1 real em memória, com CRC e zlib.
2. Aceita PNG completo com `image/png` e também quando Content-Type está ausente.
3. Rejeita HTML (incluindo um erro textual recebido com HTTP 200) ou JSON.
4. Rejeita arquivo vazio e PNG truncado.
5. Verifica que a validação ocorre **antes** da gravação do arquivo.
6. Verifica a consistência da numeração Build 46.

As demais suítes do pipeline continuam incluindo filtros, catálogo, runtime, fontes, segurança Comix e parser de CBZ.

## QA físico após disponibilizar IPA
1. Instalar Build 46 **sobre** o Build 45, sem apagar o aplicativo (para preservar Biblioteca/Downloads).
2. Na WeebCentral EN 0.1.5, selecionar um capítulo público e pequeno, usando a opção **Baixar**, e verificar progresso e estado `Concluído` em Downloads.
3. Ativar modo avião e abrir **o capítulo baixado**, passando por todas as páginas. A abertura em modo avião depende de o capítulo estar realmente concluído.
4. Pausar e retomar um download de teste, sem repetir muitos pedidos ao site.
5. Se aparecer `página inválida`, informar erro/hostname da mídia e interromper sem contornar restrições.
6. Não testar Asura premium nem imagens embaralhadas enquanto o decodificador nativo não estiver implementado e validado.

**Status:** integridade estrutural e de conteúdo validada em fixture local; disponibilidade/funcionamento físico pendentes de teste do usuário.
