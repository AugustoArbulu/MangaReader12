# Ponte Chimera — primeiro teste real, sem instalar IPAs

## Diagnóstico PING após `WRAPPINST_READY` — 06/11/2026

O usuário criou a pasta `WR` com permissão 0700 (antes ela não existia).
O helper assinado com `no-container` executou `selftest` corretamente.
Em seguida, no NewTerm 2 (`UID 501`), mostrou `WRAPPINST_READY`.
O usuário **tocou no botão Testar ponte appinst (PING) dentro dos 60 s**.
O WebReader IPC Test exibiu **Conexão ou resposta do instalador rejeitada**,
e o terminal retornou ao prompt normal sem informar a causa.

A mensagem do aplicativo corresponde ao resultado genérico `.rejected`;
não prova que a conexão chegou ao servidor (pode falhar na análise local
do diretório/socket, no cheque do peer, no `send`/`recv` ou no cabeçalho).

### Próximo arquivo de diagnóstico — somente um componente

Artifact **WebReader-Chimera-Mobile-PING-DIAG-iOS12** no novo run
`.github/workflows/chimera-mobile-ping.yml`.

- Helper diferente: `WebReader-Chimera-Ping-DIAG-iOS12`.
- Segue compilado como `WEBREADER_PING_ONLY` e assinado com um único
  entitlement `com.apple.private.security.no-container`.
- Depois de `WRAPPINST_READY`, agora mostra um dos códigos:
  - `WRDIAG: NO_CONNECTION`: ninguém chegou a ser aceito no socket
    durante a janela de 60 segundos.
  - `WRDIAG: ACCEPTED_CONNECTION`: a conexão chegou ao servidor.
  - `WRDIAG: PEER_REJECTED`: UID/peer não autorizado.
  - `WRDIAG: PING matched; PONG send OK`: protocolo foi respondido.
  - `WRDIAG: request header not PING`: cabeçalho incorreto.
  - `WRDIAG: REQUEST_FINISHED: result=0`: servidor finalizou sem erro.

**Instrução física mínima:** o WebReader IPC Test já está instalado e a
pasta `WR` já existe; não reinstalar IPA ou fazer `mkdir`.
Copiar só `WebReader-Chimera-Ping-DIAG-iOS12` pelo WebDAV para
`/var/mobile/Documents/` (não usar `ldid -S`). Em NewTerm 2 mobile:

```sh
/var/mobile/Documents/WebReader-Chimera-Ping-DIAG-iOS12 serve-once '/var/mobile/Containers/Data/Application/F6C7F694-9BEB-432B-936B-FC8B3AA95A50/WR'
```

Quando aparecer `WRAPPINST_READY`, tocar uma vez em
**Testar ponte appinst (PING)** dentro de 60s; fotografar a tela do
NewTerm com as linhas `WRDIAG` após o processo encerrar.
Ainda não instala IPAs, não chama `appinst`, não altera a Build56.

---


## Atualização do teste após o diagnóstico físico `zsh: killed`

Em 06/11/2026, o usuário testou o helper anterior em NewTerm 2 no iPad
iOS 12.5.8 / Chimera. O processo foi morto com `zsh: killed`
antes de imprimir `selftest`, inclusive após `ldid -S` manual.
O comando `ldid -h` exibiu CDHash válido, mas não comprovou que a
assinatura contivesse entitlements.

A nova versão usa arquivo **com nome diferente**, para não reutilizar
o executável previamente testado:
`WebReader-Chimera-Mobile-Ping-Entitled-iOS12`.

Diferença: assinamos o helper externo de diagnóstico com exatamente
`com.apple.private.security.no-container = true`, sem concessão de root,
plataformização ou chamadas ao instalador. Em testes independentes com
iOS 12/Chimera, esse entitlement foi necessário para iniciar binários
CLI fora do sandbox. Isto é uma **hipótese**, ainda sem comprovação
física neste iPad. A CI audita o entitlement EMBUTIDO na assinatura,
e proíbe `posix_spawn` e `/usr/bin/appinst` no helper PING.

**Se o aplicativo IPC Test já está instalado** (é o caso atual):
não instale novamente a IPA. Basta copiar **apenas** o arquivo
`WebReader-Chimera-Mobile-Ping-Entitled-iOS12` do novo ZIP para
`/var/mobile/Documents/` via WebDAV/Filza e testar no NewTerm como
UID 501, com o único comando:
```sh
/var/mobile/Documents/WebReader-Chimera-Mobile-Ping-Entitled-iOS12 selftest
```
Esperado: `WEBREADER_PING_ONLY: no IPA installation supported`.
Se aparecer `zsh: killed` novamente, **pare**; a assinatura, política
de execução e toolchain precisam de mais análise. Não refaça
`ldid -S` no arquivo novo: isso substitui a assinatura que contém
`no-container` por outra sem entitlements.

O entitlement `no-container` dá ao processo acesso além de um
container de aplicativo. Por isso ele está limitado ao helper móvel
independente, que só atende PING/PONG, e não deve ser aplicado ao
WebReader principal nem a um daemon com privilégios de root.

Fonte de hipótese: relato experimental no Chimera, iOS 12.5.x,
https://gist.github.com/ebowwa/0c6b5795d9a570046a1feb56f03e05e3

---


Data: 06/11/2026. Projeto: WebReader iOS 12.5.8.

## O que o teste anterior comprovou

O aplicativo de teste **WebReader appinst Test Build 2**, executado com
UID/EUID 501, recebeu **EPERM (1)** em `lstat`, `access(X_OK)` e,
principalmente, `posix_spawn("/usr/bin/appinst", ["--help"])`.

**Conclusão:** a execução direta de `appinst` a partir do sandbox
deste app está bloqueada. Isso não significa que o `appinst` instalado
esteja com defeito ou que não funcione no terminal/Filza.

O próximo caminho é uma ponte externa ao sandbox, inicialmente executada
como usuário **mobile (UID 501)**. Não utilizar root.

## Um ZIP com os dois componentes necessários ao primeiro teste

GitHub Actions → artefato **WebReader-Chimera-Mobile-PING-Kit-iOS12**.

- `WebReader-IPC-Probe-iOS12-unsigned.ipa`: aplicativo **WebReader IPC Test**,
  independente da Build 56, com opção de copiar a pasta WR e
  **Testar ponte appinst (PING)**.
- `WebReader-Chimera-Mobile-Ping-Entitled-iOS12`: executável **somente PING/PONG**.
  Sua compilação exclui o código de instalação e não contém chamada a
  `appinst`; executa fora do sandbox do aplicativo.
- `.sha256`: integridade de cada arquivo. Os dois arquivos estão no
  **mesmo ZIP**, sem necessidade de baixar vários artefatos.

**O primeiro teste requer abrir um terminal UMA VEZ para iniciar o
componente externo.** Ainda não há serviço instalado de forma permanente.
Não confundir isso com o funcionamento esperado da versão final, que
deverá dispensar terminal em atualizações normais.

## Procedimento de teste PING sem instalação

1. Com a CI verde no commit atual, baixe o ZIP, extraia-o no PC.
2. Instale **somente** a IPA `WebReader-IPC-Probe-iOS12-unsigned.ipa`
   com seu método já funcional no Chimera/AppSync Unified. É um app
   distinto; **não** substitua a Build 56 principal.
3. Abra **WebReader IPC Test** e toque em **Copiar pasta do socket (Chimera)**.
   Essa é a pasta `WR` específica do contêiner do app de teste.
4. Copie o arquivo `WebReader-Chimera-Mobile-Ping-Entitled-iOS12` para um local
   executável do iPad usando Filza; NÃO reexecute `ldid -S` neste binário.
5. No terminal do iPad, usando o usuário **mobile** (nunca root),
   confira `id -u` (esperado: `501`). Com o caminho real onde copiou
   o binário, verifique:
   ```sh
   /CAMINHO/REAL/WebReader-Chimera-Mobile-Ping-Entitled-iOS12 selftest
   ```
   Esperado: `WEBREADER_PING_ONLY: no IPA installation supported`.
   Se houver `Permission denied` ou `Operation not permitted`, informe
   o erro; não force permissões de root.
6. Ainda no terminal do usuário mobile, execute com **os caminhos reais**
   (o segundo argumento é a pasta WR copiada no passo 3):
   ```sh
   /CAMINHO/REAL/WebReader-Chimera-Mobile-Ping-Entitled-iOS12 serve-once '/PASTA/WR/COPIADA'
   ```
   Esperado: `WRAPPINST_READY`. Deixe o terminal aberto.
7. Dentro de 60 segundos, volte ao **WebReader IPC Test**, toque em
   **Testar ponte appinst (PING)** e copie o relatório para o chat.
   Esperado: **Ponte mobile respondeu PONG**. A ponte para após um
   único pedido; para repetir o teste é necessário iniciá-la novamente.

**Se o teste não conseguir acessar um socket, não instale IPAs usando
essa ponte.** O relatório determinará se o bloqueio é de permissões,
sandbox, assinatura do executável ou comunicação.

## O que esse PING comprova — e o que não comprova

- Um PONG indica que o aplicativo conseguiu conversar com um processo
  externo, como usuário mobile, por socket local.
- O PING **não chama `appinst`**, não modifica outros aplicativos e não
  executa nenhuma instalação.
- O próximo passo, se funcionar: preparar a versão instaladora restrita,
  testando **primeiro um aplicativo descartável**, com confirmação e
  preservação de dados antes de atualizar a Build 56.
- Mais tarde, instalar a ponte uma única vez com inicialização
  automática. Esse processo **ainda não está implementado**.

A IPA e o binário ARM64 são compilados experimentalmente com Xcode 16.4.
A compatibilidade real com iOS 12.5.8, o sandbox e a execução ad hoc
só podem ser confirmados no iPhone. A Build56/main continuam intactas.
