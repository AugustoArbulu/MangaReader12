# WebReader — MVP de instalação por appinst via socket mobile (iOS 12)

Data: 2026-11-05. Branch: feat/chimera-updater-phase1-protocol-audit. PR #90 Draft.
Stable Build 56/main: PRESERVADAS, nenhuma instalação feita no iPhone.

## O que já está ligado no código

Fluxo: GitHub Releases público -> verificar release/asset/sha256 ->
baixar IPA -> inspeção ZIP, Info.plist e identificador -> confirmação
explícita na UI -> solicitação por socket Unix -> bridge C como mobile
-> hash novamente -> /usr/bin/appinst via posix_spawn, sem shell.

Arquivos:
- MangaReader12/Core/WebReaderAppinstSocket.swift: cliente iOS12.
- MangaReader12/UI/WebReaderAppUpdatesViewController.swift: botão
  Instalar atualização (Chimera), visível apenas após IPA validada;
  alerta de confirmação e relatório de erro/sucesso.
- ci/webreader_appinst_bridge.c: executável mobile, comandos selftest,
  inspect, install-confirmed (CLI) e serve-once (socket). Recusa root.
- ci/test_native_webreader_appinst_socket.py: integração real cliente
  Swift/servidor C em macOS com FAKE appinst; nunca instala aplicativos.
- ci/test_webreader_appinst_bridge.py: testes da CLI com FAKE appinst.

## Protocolo reduzido

- Socket wri.sock, sob a pasta WR do container de dados do app.
- Servidor iniciado como usuário mobile, um único pedido, espera 60s.
- PING exato WRPING1 + LF -> PONG exato WRPONG1 + LF.
- Pedido de instalação: WRINST1 + LF, comprimento do caminho de
  16 bits big-endian, caminho absoluto UTF-8 <= 1024 bytes,
  SHA-256 minúsculo (64 bytes) e confirmação literal I-CONFIRM-INSTALL.
- Resposta após execução: WRDONE1 + LF ou WRFAIL1 + LF.
- Cliente e servidor verificam que o peer tem o mesmo UID.
- Servidor exige IPA do MESMO container de dados que hospeda seu
  socket, nome WebReader-build<N>-UUID.ipa, propriedade, tamanho,
  SHA-256 e início ZIP PK. Ele não recebe executáveis por IPC.

## O que NÃO está pronto

- O bridge não é instalado ou iniciado automaticamente. Será preciso
  iniciar o comando serve-once como mobile para cada tentativa.
- A comunicação não autentica a assinatura do processo: mesmo UID
  não é prova de identidade do app. Não usar como daemon root.
- A ponte reabre a IPA por caminho antes do appinst e o appinst faz
  sua própria cópia. A integridade fim a fim não foi provada.
- O SHA enviado pelo app não equivale a assinatura independente;
  a origem do release pessoal é HTTPS/GitHub.
- Nenhum GitHub Release de atualização do WebReader foi publicado.
- Nenhum teste físico em iOS12.5.8/Chimera foi realizado.
- Não atualizar a Build56 principal antes de backup e ensaio com
  aplicativo descartável, com autorização do usuário.

## Primeira validação física sugerida: APENAS PING, sem instalação

1. Com CI do HEAD verde, no PC baixar os artefatos de Actions
   WebReader-IPC-Probe-iOS12-NONINSTALLER e
   WebReader-Appinst-Bridge-iOS12-MOBILE-PREVIEW.
2. Instalar SOMENTE a IPA independente WebReader IPC Test, nunca a
   IPA principal Build56, que possui o mesmo identificador do leitor.
3. Na IPA WebReader IPC Test, tocar Copiar pasta do socket (Chimera).
   A pasta copiada é o valor real do telefone, terminando em /WR.
4. Transferir a bridge C por método já validado (p.ex., Filza).
   Em terminal funcionando como UID mobile, não root (id -u != 0),
   executar bridge selftest; o resultado apenas indica se /usr/bin/
   appinst existe, sem chamá-lo.
5. No mesmo terminal mobile, executar:
   /CAMINHO/Bridge serve-once '/CAMINHO/COPIADO/WR'
   O programa deve indicar WRAPPINST_READY.
6. Em até 60s tocar Testar ponte appinst (PING) na IPA diagnóstica.
   Resultado esperado: PONG recebido, sem instalação. O serviço
   encerra após uma conexão; para novo teste, reiniciar serve-once.
7. Enviar no chat o relatório da tela Copiar relatório do helper.

Atenção: caminhos exemplificativos acima não são caminhos reais.
Os caminhos de sandbox, execução ad hoc e acesso do processo mobile
dependem do Chimera, portanto o sucesso não é garantido até o teste.

## Etapa seguinte

Depois de PING confirmado no iPhone: teste controlado usando um
aplicativo descartável, nunca o WebReader principal. Depois, um
processo mobile persistente para dispensar o terminal a cada
atualização, mantendo confirmação explícita no aplicativo.

Status: implementação experimental no PR #90, sem merge e sem Release.