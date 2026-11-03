# Comix para MangaReader12 / iOS 12 — Estudo de viabilidade, fase 0

**Data:** 2026-11-03  
**Escopo:** leitura de código e histórico público; **nenhuma requisição ao site Comix**, nenhuma alteração no adaptador ou leitor em produção.  
**Checkpoint:** Build 41 fisicamente relatado como funcional; Build 42 compilado, CI verde e IPA gerado, **ainda sem QA físico do usuário**.  
**Objetivo:** o usuário considera Comix a fonte de maior prioridade. Investigar integração legítima, sem repetição do experimento Android de 503/“Third-party apps are not supported”.

## 1. Evidência específica da Keiyoushi — 2026-11-03

Código-base lido em `keiyoushi/extensions-source`, `main`, arquivo
`src/en/comix/src/eu/kanade/tachiyomi/extension/en/comix/Comix.kt` (Git blob `6e57610b3f78c0566f14e479b61a3b63ee65e8c4`).
A implementação **não é um parser HTML/HTTP tradicional**:

1. `getPopularManga` e `getMangaListFromBrowse` navegam para browse com `runInWebView` e colhem dados da página viva; isso depende de JS do site e do WebView, não de um HTML estático.
2. `navigateForQueries` usa a navegação WebView e espera o documento terminar de analisar `script#initial-data`. Foi abordado no PR **#20384**, merged em 2026-10-25.
3. `getWebViewChapterList` usa a navegação em WebView e interação com a lista de capítulos (incluindo páginas e estados de conclusão). A coleta de nomes/grupos/votos foi alterada no PR **#20337**, merged em 2026-10-24.
4. `getPageList` e `getImageUrl` dependem de captura sequencial da **execução do leitor da página** em WebView com scripts, páginas virtualizadas e pausas. A URL de imagem pode nem estar conhecida quando o método de listagem retorna.
5. Android `BackgroundSurface` hospeda WebView fora da tela; `runInWebView` dispõe de pontes Android específicas, por exemplo `NativeWebViewApi` e ações de toque/swipe. Esse código Kotlin/Android **não é executável** num runtime iOS12.
6. O PR **#20159** (merged em 2026-10-19) declara que o próprio site recusava o cliente OkHttp e passou a utilizar um WebView para browse, search, detalhes, capítulos e páginas. O issue **#20134** documenta HTTP503 e a mensagem de não suporte a apps de terceiros.
7. Em 2026-11-03, **#20547** (“Comix: fetch the chapter list 100 per page”) está **aberto e não merged**; pretende reduzir a latência com menos páginas de capítulos, mas não altera por si só a incompatibilidade iOS/Android. **#19969** (“Delete Comix extension”) também está **aberto e não merged**; não afirmar que foi excluída do Keiyoushi.
8. Issue **#20486** relata regressão em Suwayomi v1.6.59 associada a WebView; ambiente/ponte incompatíveis podem bloquear a fonte mesmo fora do iOS.

Refs públicas:
- https://github.com/keiyoushi/extensions-source/blob/main/src/en/comix/src/eu/kanade/tachiyomi/extension/en/comix/Comix.kt
- https://github.com/keiyoushi/extensions-source/pull/20159
- https://github.com/keiyoushi/extensions-source/pull/20337
- https://github.com/keiyoushi/extensions-source/pull/20384
- https://github.com/keiyoushi/extensions-source/pull/20547
- https://github.com/keiyoushi/extensions-source/pull/19969
- https://github.com/keiyoushi/extensions-source/issues/20134
- https://github.com/keiyoushi/extensions-source/issues/20486

## 2. Diferença arquitetural no MangaReader12

- O contrato iOS das fontes em `MangaReader12/SourceRuntime/JavaScriptSourceRuntime.swift` roda JavaScript de extensão em **JSContext/JavaScriptCore** e usa uma ponte limitada para HTTP e seleção de HTML. As seis funções obrigatórias são metadata/popular/search/details/chapters/pages.
- Nosso `HTMLSelectorService` é um **WKWebView não persistente carregado com HTML vazio**, usado apenas para `DOMParser.parseFromString`. **Não executa JavaScript do site** nem compartilha a sessão real de uma página Comix.
- `HTTPClient` usa URLSession efêmera com allowlist HTTPS/domínios e verificação TLS padrão. Não assume acesso às sessões, tokens ou assinaturas do contexto browser.
- O projeto possui WKWebView de diagnóstico para MangaDex, mas não tem hoje uma ponte de navegação/retorno estruturado que replique as dependências de `runInWebView` do Comix.
- iOS 12 tem WebKit/WKWebView integrado ao sistema, potencialmente incapaz de executar alguns scripts atuais do site; compatibilidade **não pode ser afirmada sem teste no aparelho**.

Consequência: portar `Comix.kt` para JS ou traduzir seus seletores **não é suficiente**. Não inventar API de capítulos/imagens ou dizer que as URLs de página são estáticas.

## 3. Restrições obrigatórias

- **Não realizar solicitações a Comix automaticamente** nem alterar o repositório Android `mihon-comix-tweaks` nesta fase. Usar somente código público e testes offline.
- Sem engenharia de evasão de WAF/Cloudflare, sem CAPTCHA automatizado, fingerprint spoofing, apropriação de tokens/sessões ou modificações de headers para ocultar a identidade de app de terceiros.
- Não substituir TLS, allowlists ou política de redirects. Não armazenar nem expor cookies, credenciais ou URLs assinadas em logs.
- Não alegar suporte de Comix até aprovação técnica, evidência de acesso legítimo e QA real. Mensagem “Third-party apps are not supported” é motivo para **interromper a integração não autorizada**, não para insistir.

## 4. Próximos marcos (não implementados nesta fase)

**Comix C1 (offline):** arquivar as diferenças Android/iOS, comparar mudanças do upstream e reavaliar PR #20547 quando resolvido. Testes de contrato JS com fixtures locais, sem rede Comix.

**Comix C2 (iOS físico, apenas com ação do usuário):** um protótipo de **navegação comum WKWebView** para a página oficial, TLS padrão, uma navegação e sem scripts de automação. Verificar se renderiza no iOS12.5.8 e se o site permite esse uso. O teste não significa que as funções de extensão funcionam. Ao encontrar 403/503, CAPTCHA ou rejeição explícita, exibir o fato, não contornar.

**Comix C3 (apenas se autorizado/compatível):** pesquisar uma integração pública/documentada, ou adicionar um atalho para abrir no navegador oficial. Se o site autorizar integração e o WebKit for compatível, projetar um serviço de navegador por fonte com isolamento de origem e APIs limitadas, sob nova revisão de segurança e privacidade. Nenhuma interface com APK Android.

**Critério de parada:** ausência de acesso autorizado, incompatibilidade JS definitiva no WebKit iOS12, falta de metadados legítimos de capítulos/imagens ou conteúdo necessário indisponível por meio de rotas compatíveis; registrar limitação e preservar o Build42/Build41 sem “soluções” especulativas.

## 5. Status

- **Fase C0 concluída: auditoria somente leitura e plano de arquitetura.**
- Comix **não está funcionando como fonte de leitura no MangaReader12** e **nenhuma implementação Comix foi adicionada**.
- Esta documentação é a referência para iniciar C1/C2 depois do teste físico do Build42.
