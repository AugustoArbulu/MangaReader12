# WebReader — Fase 6B: kit de diagnóstico IPC separado (iOS 12.5.8 / Chimera)

**Data:** 2026-11-05  
**Repositório:** AugustoArbulu/MangaReader12  
**Branch experimental:** feat/chimera-updater-phase1-protocol-audit  
**PR:** #90 Draft, sem merge  
**Versão estável:** Build 56, permanece instalada e inalterada

## Objetivo simples

Comprovar em um iPhone com iOS 12.5.8 e Chimera que um
**aplicativo de diagnóstico separado** consegue conversar com
um **programa nativo separado, não privilegiado**, por um
socket UNIX local. O resultado esperado é PING/PONG.

Não há atualização de WebReader, IPA remota, assinatura de
releases, backup, instalação via appinst nem daemon privilegiado.
Esta etapa não utiliza appinst.

## Artefatos do GitHub Actions

O workflow da branch cria e valida três artefatos distintos:

1. **WebReader-IPC-Probe-iOS12-NONINSTALLER**: contém
   WebReader-IPC-Probe-iOS12-unsigned.ipa e seu SHA-256.
   Identificador **com.example.MangaReader12.ipcprobe**;
   nome no iPhone **WebReader IPC Test**.
2. **WebReader-Helper-Ping-iOS12-NONINSTALLER**: contém
   WebReader-Helper-Ping-iOS12, binário Mach-O arm64 com
   assinatura ad hoc de teste e SHA-256. É um executável
   de console, NÃO um .deb, nem uma extensão de jailbreak,
   nem deve ficar no bundle do WebReader.
3. **WebReader-TLS-Probe-iOS12-Experimental**: sonda HTTPS
   separada, existente de fases anteriores; não é necessária
   para o PING/PONG.

Os artefatos são uploads temporários de **GitHub Actions**,
não releases oficiais nem atualizações instaláveis a partir
da tela do WebReader. A IPA do diagnóstico é empacotada sem
assinatura de distribuição; a instalação física depende do
mecanismo já disponível no iPhone e de sua compatibilidade.

### Isolamento garantido por testes de CI

- WebReader principal: com.example.MangaReader12.
- Diagnóstico TLS: com.example.MangaReader12.httpsprobe.
- Diagnóstico IPC: com.example.MangaReader12.ipcprobe.

O app IPC mostra só a versão e seção HELPER LOCAL (DIAGNÓSTICO).
Não cria LibraryViewController/ExploreViewController nem agenda
BackgroundLibraryUpdateManager no lançamento. O app base segue
com a interface original. Ao reconstruir as três IPAs, a CI
confronta CFBundleIdentifier, CFBundleExecutable, CFBundleVersion
e hashes do executável, além de impedir que o helper C seja
injetado no bundle do app.

## Procedimento de QA física (APENAS depois da CI verde)

**Primeiro teste — sem binário auxiliar:**

1. No PC, abrir a execução GitHub Actions aprovada e obter
   o ZIP do artefato WebReader-IPC-Probe-iOS12-NONINSTALLER.
2. Extrair a IPA do ZIP. Ela tem o identificador ipcprobe;
   **não instalar a IPA principal denominada
   WebReader-iOS12-unsigned.ipa**.
3. Instalar o aplicativo diagnóstico separado usando o
   método já validado no aparelho (Chimera/AppSync/Filza).
   Não substituir nem remover a Build 56 original.
4. Abrir **WebReader IPC Test**, tocar **Testar helper de
   diagnóstico**. Como não foi iniciado um servidor, o
   esperado é "não encontrado (normal sem instalação)".
5. Tocar **Copiar pasta para o teste local**. O path é um
   diretório **WR dentro do container do app de diagnóstico**.
   Seu valor concreto vem do aparelho; não copiar caminhos
   arbitrários de outro aplicativo.

**Segundo teste — executável nativo não privilegiado:**

1. No PC, extrair WebReader-Helper-Ping-iOS12 do ZIP do
   artefato correspondente. Conferir o SHA-256 incluído.
2. Transferir o executável ao iPhone em um local de teste
   separado, sem instalar pacotes .deb nem modificar o
   WebReader principal.
3. Usar somente um terminal com usuário **mobile**, EUID
   diferente de zero. Conferir essa condição com `id -u`.
   **Se o terminal estiver como root (0), não executar**.
4. O arquivo precisa ter permissão de execução e assinatura
   aceitas pelo ambiente Chimera. A assinatura ad hoc gerada
   no macOS pode não ser suficiente no aparelho; qualquer
   falha deve ser registrada, não contornada por alterações
   indiscriminadas de segurança do sistema.
5. Executar o comando `/CAMINHO_DO_TESTE/WebReader-Helper-Ping-iOS12 selftest`
   somente como mobile; saída esperada:
   `WEBREADER_HELPER_SELFTEST_OK (non-root, no installer)`.
6. Para testar o socket, executar o mesmo binário com:
   `/CAMINHO_DO_TESTE/WebReader-Helper-Ping-iOS12 serve "/CAMINHO/COPIADO/WR"`.
   O processo imprime WRPING_READY e oferece janela de
   aproximadamente 60 s para o próximo passo.
7. No aplicativo **WebReader IPC Test**, tocar
   **Testar helper de diagnóstico** enquanto o processo
   aguarda. O resultado esperado é "PONG recebido;
   mesmo UID, NÃO autenticado". O programa do terminal
   encerra após uma única conexão.
8. Se aparecer "não encontrado", "não confiável" ou
   "conexão negada", copiar o texto do diagnóstico e
   relatar se `selftest` funcionou. Não tentar executar
   como root para forçar a comunicação.

Os paths são exemplos de formato e **não devem ser usados
literalmente**; dependem do sandbox e da transferência real.
Acesso de um processo externo à pasta do app no iOS12
não é garantido pelo CI macOS.

## Como interpretar resultados

- `selftest` OK + PONG OK: prova execução mobile do
  binário C e conectividade local com o app diagnóstico.
- `selftest` OK + falha PING: possível sandbox, UID,
  permissões/path ou disponibilidade do socket. Não é
  evidência de bloqueio do GitHub ou de instalação.
- `selftest` falha: antes de depurar IPC, identificar
  erro de execução, arquitetura, permissões ou assinatura
  do binário de console.
- PONG não autentica identidade de código, autorização
  de instalação, integridade de IPA ou origem do appinst.

## Próximas etapas somente após QA

Investigar IPC com autenticação forte de processo, cache
anti-replay e verificação de assinatura independentes,
permissões dos diretórios no Chimera, origem do appinst
e sua cópia temporária 0777, instalação de aplicativo
descartável e backup de dados reais.

**Bloqueios permanentes até aprovação explícita:** nenhum
helper rootful, nenhuma atualização automática, nenhum
`appinst` executado pelo app, nenhum Release de produção,
nenhuma chave de produção, nenhum merge na main e nenhuma
substituição da Build 56.
