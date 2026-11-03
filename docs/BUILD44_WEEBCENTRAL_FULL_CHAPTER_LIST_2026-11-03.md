# Build 44 — correção da lista de capítulos interrompida em 200

**Data:** 2026-11-03

## Evidência física

No iOS 12.5.8, WeebCentral EN 0.1.2 abre capítulos e renderiza as imagens. Em *One Piece*, aparecem somente capítulos de 998 até 1197 — exatamente **200 entradas**.

## Causa no código

O HTMLSelectorService nativo (MangaReader12/SourceRuntime/JavaScriptSourceRuntime.swift) usava o limite genérico de 200 resultados em toda consulta DOM executada via WKWebView/DOMParser. A rota de lista de capítulos da WeebCentral retorna os capítulos numa única página HTML; o parser selecionava apenas os 200 primeiros. Assim, o corte é causado pelo aplicativo e **não comprova** a ausência de capítulos antigos no site.

## Mudança Build 44

- Capítulos: até **4000 resultados** na extração HTML.
- Páginas de leitura: até **1500 resultados**; evita o mesmo truncamento quando há mais de 200 imagens.
- Outros seletores permanecem com teto de 200, reduzindo impacto no iOS 12.
- Acima do teto de capítulos ou imagens o parser **falha explicitamente**, sem fingir que a lista parcial está completa.
- Proteções existentes preservadas: entrada HTML até 3 MiB e retorno serializado até 4 MiB. Mesmo abaixo de 4000 capítulos, a saída pode exceder o teto e falhar com erro em vez de perder entradas.
- Nenhuma alteração do script WeebCentral, catálogo, allowlist de domínios, downloads existentes ou rotina de requests ao site.
- Xcode build Debug/Release incrementado de 43 para 44.

## Testes automatizados, offline

O arquivo ci/test_build44_chapter_selector.cjs extrai e executa o JavaScript do próprio parser nativo, com DOM sintético: lista de **1197 capítulos** preservada da primeira à última entrada; **350 páginas** preservadas; listagem comum mantém 200; mais de 4000 capítulos e mais de 1500 imagens geram falha explícita; limites de memória e numeração Build 44 verificados.

**Os testes offline não provam o número real de capítulos que o servidor retorna atualmente.**

## Protocolo físico iOS 12.5.8

1. Instalar a IPA não assinada do **Build 44** pelo Sideloadly, re-assinada normalmente. **Não desinstalar o app previamente**, para evitar perda de dados locais.
2. Manter WeebCentral EN 0.1.2 já instalada (o catálogo não precisa mudar).
3. Abrir novamente *One Piece*, aguardar a lista completar e verificar se aparecem capítulos **anteriores ao 998**; anotar intervalo inicial/final e quantidade.
4. Abrir **um** capítulo antigo que aparecer e conferir imagens; não é necessário testar dezenas de capítulos.
5. Se a lista continuar limitada a 200, a investigação seguirá para resposta HTML do servidor, outra camada de truncamento ou cache, sem assumir que o site não possui capítulos antigos.
6. Interromper tentativas se houver HTTP 403/429 ou recusa explícita de acesso.

## Estado atual

- WeebCentral 0.1.2: **capítulos e imagens confirmados pelo usuário**.
- Build 44: **correção nativa validada no iOS 12.5.8 — o usuário confirmou que One Piece mostra o capítulo 1 como mais antigo**.
- Atualização de Biblioteca e download offline com esta fonte: **ainda sem QA físico**.
