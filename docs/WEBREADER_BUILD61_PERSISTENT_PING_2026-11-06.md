# Build61 — PING persistente no Chimera (somente leitura)

## Checkpoint físico anterior

Em 06/11/2026, a **Build60 SignedQA foi APROVADA no iPad iOS12.5.8**: o usuário instalou v1, atualizou para v2 via appinst (CLI mobile) e confirmou que o registro NSUserDefaults foi preservado. Não houve atualização do WebReader principal.

## Por que este laboratório

Para atualizar sem NewTerm a cada versão, a ponte precisa estar disponível continuamente. A Build61 verifica **somente a inicialização automática, reinicialização e acesso pelo app IPC Test**, sem abrir um canal de instalação. Um PONG não autentica o cliente nem autoriza appinst.

- Fonte C: ci/webreader_chimera_persistent_ping.c — escuta apenas 127.0.0.1:38971, recebe exclusivamente WRPING1 e responde WRPONG1, rejeita quaisquer outros comandos. Não possui instalação, leitura de IPA, shell nem spawn; em iOS exige mobile UID501 e recusa root.
- Plist: ci/com.example.webreader.pinglab.plist — launchd em /Library/LaunchDaemons, com UserName mobile, RunAtLoad, KeepAlive e ThrottleInterval 10. A instalação do pacote depende explicitamente da escolha do usuário, e o runtime do serviço não é root.
- Pacote: ci/package_chimera_persistent_ping_deb.py — DEB com binário assinado ad hoc (com.apple.private.security.no-container), LaunchDaemon e scripts postinst/prerm para carregar/descarregar o serviço. NÃO inclui WebReader .app nem appinst.
- CI: testes de 15 reconexões, PING fragmentado, rejeição de comandos, restart, permissões, assinatura, estrutura DEB e ausência de símbolos de instalação. O CI nunca instala o pacote no iOS.

## CI aprovado

GitHub Actions #42178651475 (https://github.com/AugustoArbulu/MangaReader12/actions/runs/42178651475) SUCCESS no commit 03f7697e8ced20b6f3b6fc8a005da9879b4a9fa2.

Artifact: WebReader-Chimera-Build61-PersistentPing-QA-iOS12, id 13484028052.
Arquivo: WebReader-Chimera-Persistent-PingLab-iOS12.deb.
SHA-256 do DEB: a9232fec96b789bf6c400ded015a63bd5733686abd655e8860a184159d4a5b57.
Auditoria independente do .deb com dpkg-deb --info e --contents aprovada; contém somente binário de diagnóstico e LaunchDaemon.

**Importante:** CI verde não comprova que launchd funciona no jailbreak físico.

## Teste físico combinado, quando autorizado

1. Parar qualquer helper antigo que ainda escute a porta 38971 no NewTerm.
2. Pelo Filza, transferir o DEB e instalar pelo gerenciador de pacotes jailbreak. É uma operação de instalação de sistema **que requer autorização explícita**; o pacote fica instalado até ser removido.
3. Reutilizar o WebReader IPC Test já existente (Build58/59/60), tocar em Testar ponte localhost (PING). Deve aparecer PONG e nenhuma IPA instalada.
4. Fechar IPC Test e NewTerm, abrir novamente e testar PING. Depois, se conveniente e sem interromper trabalho, testar após reinício do iPad + reativação do Chimera. Isso valida persistência separadamente do app.
5. Se falhar, não tentar usar appinst, nem tocar no WebReader principal.

Remoção: pelo gerenciador de pacotes do jailbreak, desinstalar com.example.webreader.pinglab. Como alternativa, dpkg -r com.example.webreader.pinglab com privilégios apropriados. O prerm descarrega o job.

## Ainda não há atualização dentro do WebReader

PING em localhost não atesta assinatura, identidade do aplicativo ou consentimento do proprietário. O helper deste laboratório **jamais pode receber comandos de instalação**. Para o atualizador definitivo, faltam: política independente do publisher e de confiança do release, autorização e consentimento resistentes a clientes locais não confiáveis, verificação de IPA/versão/Bundle ID pelo instalador, mitigação TOCTOU, e QA física end-to-end do WebReader verdadeiro com backup.

PR #90 permanece Draft na branch feat/chimera-updater-phase1-protocol-audit. Main e WebReader Build56 intocados.

## Build61 FIX1 — QA física do pacote anterior e correção (06/11/2026)

O usuário executou dpkg -i como root na versão 0.1.0 e recebeu:
- não conseguiu criar /usr/local/libexec/webreader-pinglab.dpkg-new: No such file or directory.
- O IPC Test Build59 respondeu TCP local connect(errno=61), consistente com serviço não iniciado.

Causa identificada no código de empacotamento: o data.tar.gz anterior tinha somente os dois arquivos, sem declarar os diretórios pais. O dpkg do Chimera não tinha /usr/local/libexec.

FIX1 (versão 0.1.1) acrescenta, antes dos dois arquivos, entradas de diretório root/wheel 0755 para /usr, /usr/local, /usr/local/libexec, /Library, /Library/LaunchDaemons; teste de CI simula extração em filesystem vazio. Binário de PING e plist permanecem inalterados.

CI aprovado: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42182040383 , commit 8bd69c0e9e297e74732ec1a3c10ce2fadd1f4379; artifact WebReader-Chimera-Build61-PersistentPing-FIX1-iOS12, ID 13485403309. Novo pacote: WebReader-Chimera-Persistent-PingLab-iOS12-FIX1.deb, SHA-256 dca3a571f433c4acbbae6377d7238705404be471932ce1d48d606dbbd0f8378a.

Auditoria independente: dpkg-deb --info mostra version 0.1.1; dpkg-deb --contents mostra cinco diretórios e dois arquivos; dpkg-deb --extract em pasta completamente vazia concluiu com binário e plist nos caminhos corretos.

Próximo teste no iPad: transferir somente o pacote FIX1 para /var/mobile/Documents; como root via NewTerm, executar:
    dpkg -i /var/mobile/Documents/WebReader-Chimera-Persistent-PingLab-iOS12-FIX1.deb
    dpkg -s com.example.webreader.pinglab

Somente se o status for install ok installed, testar PING no IPC Test Build59. Se a fase postinst/launchctl falhar, interromper e analisar; não mexer no WebReader principal. A correção estrutural da falha de diretório está validada, mas o FIX1 e o launchd ainda não foram testados fisicamente.

## Resultado físico parcial do FIX1 (06/11/2026)

Após transferir e instalar o pacote FIX1 0.1.1 pelo NewTerm (`dpkg -i`), o usuário confirmou que o **IPC Test Build 59 recebeu PONG** do serviço TCP local na porta 38971. Assim, o pacote e a inicialização do serviço passaram pela primeira verificação física, superando o `errno=61` anterior. Não foi compartilhada saída de `dpkg -s`, mas a comunicação PONG confirma que havia um listener ativo compatível naquele momento.

**Ainda pendente:** confirmar que o PING continua funcionando depois de encerrar totalmente NewTerm e IPC Test (independência do terminal) e, posteriormente, após reiniciar/reativar o jailbreak (persistência de inicialização automática). Nenhuma instalação de IPA foi executada por esse PING, e o serviço permanece exclusivamente de diagnóstico.
