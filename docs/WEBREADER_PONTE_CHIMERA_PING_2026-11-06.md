# Ponte Chimera — primeiro teste real, sem instalar IPAs

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
- `WebReader-Chimera-Mobile-Ping-iOS12`: executável **somente PING/PONG**.
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
4. Copie o arquivo `WebReader-Chimera-Mobile-Ping-iOS12` para um local
   executável do iPhone usando Filza. Não renomeie nem modifique o binário.
5. No terminal do iPhone, usando o usuário **mobile** (nunca root),
   confira `id -u` (esperado: `501`). Com o caminho real onde copiou
   o binário, verifique:
   ```sh
   /CAMINHO/REAL/WebReader-Chimera-Mobile-Ping-iOS12 selftest
   ```
   Esperado: `WEBREADER_PING_ONLY: no IPA installation supported`.
   Se houver `Permission denied` ou `Operation not permitted`, informe
   o erro; não force permissões de root.
6. Ainda no terminal do usuário mobile, execute com **os caminhos reais**
   (o segundo argumento é a pasta WR copiada no passo 3):
   ```sh
   /CAMINHO/REAL/WebReader-Chimera-Mobile-Ping-iOS12 serve-once '/PASTA/WR/COPIADA'
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
