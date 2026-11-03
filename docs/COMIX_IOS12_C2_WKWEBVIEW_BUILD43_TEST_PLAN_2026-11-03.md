# Comix C2 — WKWebView manual no iOS 12.5.8 (Build 43)

> **Resultado físico registrado — 2026-11-03:** o usuário confirmou **HTTP principal 200** e **navegação WKWebView concluída**, porém a **página permaneceu branca/vazia** no iOS 12.5.8. A compatibilidade visual da Comix **não foi comprovada**, e nenhuma fonte Comix é considerada funcional. Detalhes e próximos controles offline em [COMIX_IOS12_C2_BUILD43_PHYSICAL_RESULT_2026-11-03.md](COMIX_IOS12_C2_BUILD43_PHYSICAL_RESULT_2026-11-03.md). Este documento abaixo permanece como **protocolo histórico**, não como pendência de primeira execução.

**Data:** 2026-11-03  
**Repositório:** `AugustoArbulu/MangaReader12`  
**Origem técnica:** `docs/COMIX_IOS12_FEASIBILITY_PHASE0_2026-11-03.md`  
**Estado:** implementação C2 proposta no Build 43; **CI e teste físico não substituem um ao outro**.

## Objetivo e limites

Apenas verificar se a homepage pública da Comix funciona como página web comum no WKWebView instalado no aparelho iOS 12.5.8. O site é iniciado **somente por toque explícito do usuário** em Ajustes → Comix • teste do navegador → Abrir comix.to no WKWebView.

O endereço inicial `https://comix.to/` e o espelho `https://comix.ws/` constam no `src/en/comix/build.gradle.kts` do Keiyoushi, consultado em 2026-11-03. O aplicativo abre somente o primeiro endereço. Navegações principais fora desses domínios/subdomínios ou fora de HTTPS são canceladas; não são alterados pedidos de subrecursos do site.

Configuração: `WKWebViewConfiguration`, `websiteDataStore = .nonPersistent()`, WebKit e ATS/TLS do sistema, JavaScript padrão do site. **Sem** URLSession independente, automação, JS injetado, ponte nativa, CAPTCHA automático, retries automáticos, modificação de user-agent, cabeçalhos, TLS ou cookies. Não há adaptador Comix e o resultado **não** é uma leitura de capítulos.

O relatório do app exibe o alvo inicial constante, status HTTP da **resposta principal** quando disponível, falha WebKit por domínio/código e breve estado de navegação. Não extrai texto/DOM, cookies, login, histórico ou URLs de capítulos/imagens, nem guarda sessão durável. O WebKit pode solicitar recursos de terceiros necessários ao funcionamento normal do site.

## Teste físico — Build 43

1. Primeiro, preserve o Build 42/backup atual como referência. A compilação e os testes automatizados não provam comportamento em iOS 12.5.8.
2. Instale o IPA de Build 43 gerado pelo CI **após** aprovação da branch e verificação de regressões. Abra o app e confirme que Biblioteca, Leitor e Downloads continuam visíveis.
3. Desligue o acesso à internet ou ative modo avião. Abra **Ajustes → Comix • teste do navegador**. Verifique se a tela diz “Nenhuma conexão foi iniciada”, sem carregar o site. Retorne; volte à tela.
4. Reative a rede e toque **uma vez** em **Abrir comix.to no WKWebView**. Observe a renderização como usuário normal, sem navegar por páginas em busca de endpoints.
5. Toque **Copiar resultado** e informe: versão iOS, Build, texto de relatório e descrição visual (homepage, carregamento incompleto, página em branco, desafio, 403/503, aviso de não suporte a terceiros, etc.). Não envie cookies, dados de sessão, credenciais ou URLs assinadas.
6. Em caso de 403/429/500/503, bloqueio explícito a terceiros, erro WebKit/TLS ou página que não renderiza, **pare o teste** e registre o estado. Não usar bypass, espelhos alternados para insistir, scripts injetados ou testes automatizados. O relatório não deve ser interpretado como liberação de acesso.
7. Caso o navegador carregue a homepage, isto **só prova navegação web**. Avaliar eventual integração requer revisão nova de autorização, dados públicos/documentados e compatibilidade do site com WebKit antigo. A fonte Comix continua ausente.

## Teste paralelo obrigatório — Build 42

Usando o botão de importação de Arquivos locais, selecione um **CBZ pequeno com JPEG/PNG**, confirme leitura, feche o app, ative modo avião e reabra capítulo e histórico. Verifique persistência após reinício. A importação ainda não suporta WebP, RAR/CBR, ZIP criptografado, nem inclusão desses arquivos no backup. Um problema neste fluxo deve ser tratado como regressão independente da Comix.

## Aceite

- O código é compatível com deployment iOS 12.0 e compila no toolchain Xcode 15.4.
- Entradas de Ajustes permitem iniciar um navegador não persistente **apenas após ação do usuário**.
- HTTP e erros WebKit são exibidos com metadados mínimos, sem inspeção de payload.
- Não há alteração de runtime JS, parser, cliente HTTP, leitor de páginas, credenciais, backups ou anti-bot.
- `ci/test_comix_c2_contract.py` passa juntamente com os testes já existentes.
- **Aceite físico C2:** o usuário relata o comportamento observado no iOS 12.5.8. Mesmo com homepage visível, não marcar a Comix como fonte funcional.

## Próxima decisão

Se WKWebView do iOS 12 não funcionar ou o site negar acesso a aplicativos de terceiros, encerrar a integração e documentar a limitação; eventualmente avaliar um atalho transparente para o navegador oficial se isso for permitido. Se houver navegação legítima e compatível, prosseguir apenas para uma nova fase de pesquisa, sem assumir que o adaptador WebView Android possa ser portado.
