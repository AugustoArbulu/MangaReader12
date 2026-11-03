# Comix C2 — resultado físico do Build 43 (iOS 12.5.8)

**Data do relato:** 2026-11-03  
**Ambiente:** MangaReader12 Build 43, iOS 12.5.8, WKWebView de navegação manual, `https://comix.to/`.  
**Origem:** relatório copiado pelo usuário a partir de Ajustes → Comix • teste do navegador, seguido de confirmação visual.

## Resultado reproduzido pelo usuário (evidência)

- `HTTP principal: 200`.
- `Resultado: A navegação WebKit terminou. Verifique visualmente se o site renderiza e se permite o acesso. Isso não comprova suporte à fonte.`
- **Confirmação visual explícita do usuário:** "A Comix ficou com a tela branca ou vazia no WKWebView do iOS 12.5.8."
- O relatório original dizia `Inspeção visual do conteúdo: a confirmar pelo usuário`; a confirmação posterior **substitui esse campo pendente**.
- Nenhuma leitura de lista de mangás, metadados ou capítulos foi obtida; **não foi demonstrada integração da fonte Comix**.
- O resultado documentado é apenas a navegação principal com HTTP 200 e encerramento pelo delegate, **sem renderização visual**.

**Classificação:** **C2 físico executado; resultado de compatibilidade NEGATIVO/INCONCLUSIVO quanto à causa.** Não equiparar HTTP 200 a funcionamento do site ou autorização para integração.

## O que este teste não demonstrou

- Não demonstrou que o JavaScript principal foi executado com sucesso, que assets CSS/JS/imagens foram aceitos ou que houve montagem da interface.
- Não demonstrou, isoladamente, incompatibilidade do WebKit do iOS 12 com uma sintaxe JavaScript específica.
- Não demonstrou, isoladamente, bloqueio WAF/anti-bot nem mensagem de recusa a aplicativos de terceiros.
- Não demonstrou que o browserContainer tem área visível e layout correto nesse modelo de aparelho.
- Não demonstrou paridade entre uma navegação no Safari e o WKWebView efêmero.

## Diagnóstico diferencial mínimo (sem insistência sobre a Comix)

| Hipótese | O que falta medir | Experimento permitido |
|---|---|---|
| Falha de layout ou zero altura do contêiner UIKit | `browserContainer.bounds` e `webView.bounds` com largura/altura positivas, sem gravar detalhes pessoais | Registrar métricas de layout em fixture offline, de forma visível ao usuário |
| WebKit não renderiza nem uma página simples | Capacidade de exibir HTML estático, sem acesso à internet | Carregar uma página **local** embutida com `loadHTMLString` após ação do usuário |
| Diferenças do motor do Safari no mesmo iOS | Renderização no Safari no **mesmo** iPhone/iOS 12.5.8 | Uma única comparação manual normal pelo usuário, sem automação nem mudança de identidade, apenas se desejar |
| Recursos específicos do site ou JS moderno | Necessidade de scripts/resources modernos que podem falhar sob iOS 12 | Não sondar recursos protegidos; pesquisar somente requisitos/documentação públicos e comparar resultado dos controles anteriores |
| Restrição do site a terceiros | Mensagem explícita ou documentação/termos que neguem integração | Se constatado, **interromper**; nunca procurar rota de evasão |

## Decisão técnica

1. **Nenhum Build 44 ou adapter Comix é autorizado por este resultado isolado**. O Build 43 permanece intacto; o Build 42 mantém pendência de QA físico CBZ separada.
2. Priorizar primeiro diagnósticos **offline** para confirmar que a apresentação UIKit/WKWebView funciona com uma fixture estática e que as dimensões do contêiner são positivas. Isso evita mais tráfego ao domínio da Comix.
3. Um teste de Safari normal no mesmo dispositivo, se voluntariamente realizado pelo usuário, pode separar incompatibilidade geral de diferenças entre WebViews, mas **não autoriza bypass** e não basta para provar suporte a uma fonte.
4. Só propor nova implementação quando o diagnóstico diferencial apontar uma causa solucionável e a integração for legítima, sem exigir contornar restrições ou alterar TLS.
5. Se houver mensagem explícita `Third-party apps are not supported` ou equivalente, encerrar a integração não autorizada. Se a impossibilidade de renderização iOS 12 for confirmada, registrar a limitação e manter as fontes existentes.

## Links internos

- C0: `docs/COMIX_IOS12_FEASIBILITY_PHASE0_2026-11-03.md`
- C2 protocolo: `docs/COMIX_IOS12_C2_WKWEBVIEW_BUILD43_TEST_PLAN_2026-11-03.md`
- Implementação: `MangaReader12/UI/ComixBrowserProbeViewController.swift`
- PR #61: https://github.com/AugustoArbulu/MangaReader12/pull/61
