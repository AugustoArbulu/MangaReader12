# Build 56 — fontes por obra e novidades da Biblioteca

**Data:** 2026-11-04. **Base física:** Build 55 aprovada preliminarmente pelo usuário no iOS 12.5.8. **Branch:** `feat/build56-source-attribution-updates`. Produto chama-se **WebReader**, identificador legado `com.example.MangaReader12`. iOS mínimo **12.0**. Não editar a main diretamente.

## A. Fonte de cada obra (solicitação explícita do usuário)

- O modelo SQLite existente `LibraryMangaRecord` já contém `sourceID` e `sourceMangaID`, então **não houve migração nem mutação de registros**.
- Lista da Biblioteca mostra `Fonte: {nome do manifesto}` junto às informações já presentes (status, não lidos, fixada, categorias e offline). O ícone oficial Keiyoushi (Build 55) aparece sobre a capa quando há mapeamento de asset.
- Grade exibe uma pequena linha dedicada com nome da fonte e ícone oficial, aumentando altura do cartão sem esconder título ou indicadores de leitura.
- Ficha de detalhes exibe o nome da fonte e ícone; funciona também durante `Carregando detalhes…`. Aba Atualizações identifica a origem de cada obra.
- Os nomes são resolvidos **uma vez por atualização local** usando `SourceLifecycleManager.installedSources()`, nunca por título, nome parecido, scrape, favicon remoto ou chamada HTTP por célula.
- A obra com source ausente **permanece** na Biblioteca e mostra `Fonte indisponível ({sourceID})` para evitar atribuição incorreta. A mesma obra de fontes diferentes continua com IDs, histórico e dados distintos.
- Fontes mapeadas usam `UIImage(named:)` da Build 55. Fontes sem asset mantêm nome visível, mas não recebem imagem de outra fonte por adivinhação.

## B. Atualizações: novidade vs capítulo não lido

- `UpdateFeedStore` mantém o formato original dos eventos `updates.feed.v1`. Novo `UserDefaults.stringArray` separado, `updates.feed.acknowledged.v1`, registra quais *eventos detectados* já foram vistos; não altera capítulos, progresso nem o banco.
- Identidade de evento agora é length-delimited por `sourceID, sourceMangaID, sourceChapterID`, sem colisões de separador.
- Aba Atualizações: controle **Novas/Todas**, gesto **Vista** numa entrada nova e ação **Marcar vistas** com confirmação. Abrir uma novidade marca apenas o evento como visto, **não** o capítulo como lido.
- `Novas` mostra somente eventos pendentes; `Todas` mantém o histórico e diferencia `Novo` de `Vista`. A preferência da aba é salva no UserDefaults.
- Itens já vistos não desaparecem do armazenamento; falhas de rede não fabricam eventos. Feed máximo 200 eventos; reconhecimentos são limitados ao feed atual.
- Não foi criada segunda aba Updates nem processo automático de verificação/requests extras.
- Acknowledgements ainda **não** fazem parte do backup portátil, que preserva seu formato atual; registrar essa lacuna para evolução específica futura, não alterar restore de maneira arriscada nesta build.

## Testes e critérios de aceite

- `ci/test_build56_library_updates.py` compila/executa com `swiftc` os **tipos Swift reais** do feed e da atribuição da Biblioteca: dedup, duas fontes do mesmo título, eventos distintos de mesmo capítulo em outra fonte, vistos persistentes, histórico preservado, novos eventos após marcar vistos, identidade não ambígua e compatibilidade com feed antigo.
- No CI, manter os testes de WebP, capa/ícone, filtros, leitor, backup, SQLite, Debug/Release para iOS12 e geração da IPA Build56 não assinada.
- QA física: instalar sobre Build55 pelo mesmo método de assinatura, sem desinstalar; testar **Biblioteca lista/grade**, obras de Asura e WeebCentral com títulos iguais, ficha de detalhes e Atualizações; conferir que `Novas` e `Todas` funcionam e `Marcar vistas` não muda contadores de não lidos; testar leitura offline e source removida/desativada.
- Não alegar funcionamento físico sem relato do usuário.

## Próximo roadmap
- Build57 downloads: expandir lote de até cinco já existente, feedback/cancelamento seguro e retry isolado, sem reimplementar a fila.
- Build58: leitor, páginas duplas/corte de margens limitados em memória.
- Build59: melhoria do ciclo de fontes, monitoramento passivo Keiyoushi.
- AVIF ainda **não decodificado**, Comix continua investigação isolada sem bypass.
