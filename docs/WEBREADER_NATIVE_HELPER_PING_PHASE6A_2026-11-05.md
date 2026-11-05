# WebReader — Fase 6A: comunicação REAL com helper separado (PING/PONG)

Data: 2026-11-05
Repositório: AugustoArbulu/MangaReader12
Branch: feat/chimera-updater-phase1-protocol-audit
PR: #90 — Draft, sem merge.
Base estável: Build 56, iOS 12.5.8, preservada na main.

## O que foi criado

Depois de muitas fases de auditoria, a Fase 6A implementa pela
primeira vez dois clientes de IPC NATIVOS para uma troca funcional
e mínima com um processo separado:

- ci/webreader_helper_probe.c — programa POSIX (macOS/Linux/iOS 12 ARM64),
  sem privilégios e explicitamente incapaz de executar instalação.
  Opera com dois comandos locais de linha de comando: "serve" e "probe".
  Serve uma única conexão UNIX-domain SOCK_STREAM, lê SOMENTE
  os 8 bytes ASCII "WRPING1\n", e responde SOMENTE "WRPONG1\n".
  Recusa execução com EUID 0 (root); não chama appinst, shells,
  posix_spawn, LSApplicationWorkspace, dpkg nem outras operações.
- MangaReader12/Core/WebReaderHelperPingProbe.swift — cliente nativo
  de diagnóstico compatível com iOS12. No toque manual, cria pasta
  curta "WR" sob NSHomeDirectory() do sandbox e tenta conversar
  com o socket "wrp.sock" por UNIX-domain. Valida tipo de arquivo,
  proprietário, permissões e mesmo UID no peer (getpeereid).
  Resultado distingue não encontrado, caminho inseguro, falha
  de conexão e PONG. Um PONG NÃO autentica assinatura do processo,
  identidade do helper rootful ou permissão para instalar uma IPA.
- MangaReader12/UI/WebReaderAppUpdatesViewController.swift — a tela
  experimental Ajustes > Atualizações do WebReader recebe seção
  "HELPER LOCAL (DIAGNÓSTICO)" com botões "Testar helper de diagnóstico"
  e "Copiar pasta para o teste local". A função não ativa download,
  instala um helper, inicia processos, extrai arquivos ou utiliza
  privilégios de jailbreak.
- ci/test_webreader_helper_probe.py — compila o C e testa
  separadamente servidor/cliente nativo POSIX no host,
  PING/PONG real, processo único, recusa de comandos arbitrários,
  socket ocupado, diretório inseguro/symlink e entrada malformada.
- ci/test_native_webreader_helper_ping.py — no macOS, compila
  exatamente o mesmo código Swift do app com Foundation e
  conecta de verdade ao processo C separado. Testa helper ausente,
  PONG real e socket falso.
- .github/workflows/build.yml — testes rodados no macOS-14;
  também compila o utilitário C como Mach-O ARM64 iOS 12,
  sem assinatura ou instalação e publica artefato CI
  **WebReader-Helper-Ping-iOS12-NONINSTALLER** na branch.
- ci/test_app_updates_screen.py — protege a UI contra enablement
  acidental de instalação, confere estrutura Xcode e a ligação
  explícita ao diagnóstico somente-leitura.

## Contrato byte a byte

Processo do WebReader:
  PING: [W R P I N G 1 LF] — 8 bytes.
Servidor:
  PONG: [W R P O N G 1 LF] — 8 bytes.

Não existe opcode de instalação, argumento de shell, execução,
escrita em IPA, handshake de atualização ou autenticação de
assinatura. Uma mensagem diferente simplesmente encerra o
servidor de uma conexão sem responder.

Servidor e cliente abrem apenas diretórios de mesma UID e
permissão sem acesso de grupo/outros (modo 0700 no teste).
O socket usa modo 0600 e é verificado via lstat/getpeereid.
A segurança da conta de usuário não é equivalente à
autenticação forte de processo da futura instalação.

## Fluxo do teste físico FUTURO (não executar agora)

1. CI precisa primeiro aprovar host C, Swift, compilação ARM64
   iOS12 e a IPA diagnóstica de bundle ID separado.
2. O usuário poderá testar o aplicativo diagnóstico isolado,
   sem substituir a Build 56.
3. Abrir Ajustes > Atualizações do WebReader > Testar helper
   gera a pasta "WR" no container do app. Sem servidor o
   resultado esperado é "não encontrado".
4. Um executor confiável, rodando SOMENTE como usuário mobile
   (NUNCA root), precisa obter o caminho correto da tela
   "Copiar pasta..." e iniciar o pequeno programa C com:
   WebReader-Helper-Ping-iOS12 serve /caminho/absoluto/WR
5. Ainda dentro do mesmo ambiente e com o socket ativo,
   tocar em Testar helper; o resultado esperado é PONG
   recebido, explicitamente rotulado NÃO autenticado.
6. O programa C encerra após um PING ou 3 s sem conexão;
   não permanece residente nem instala nada.

O passo 4 não foi testado em iPhone; permissões do sandbox de
iOS12/Chimera, codificação ARM64, disponibilidade do getpeereid
e execução como mobile ainda precisam de validação física.
Por isso não declarar "helper funcional no iPhone" antecipadamente.

## Riscos conhecidos e limites

- O socket fica no sandbox da app. Dependendo da política de
  sandbox e do contexto de execução do terminal jailbreak,
  um processo externo mesmo com UID mobile pode não alcançar
  esse diretório; esta limitação precisa de teste real.
- Um processo malicioso do mesmo UID que consiga criar o
  socket pode devolver o PONG correto; esta verificação é
  um diagnóstico de conectividade, NÃO autenticação do cliente
  ou servidor futuro. **Jamais usar o PONG para autorizar
  atualização, instalação ou conceder privilégios.**
- O futuro helper de instalação deve ser um componente
  separado, com autenticação forte de peer, manifesto assinado
  com chave própria pinada, IPA ZIP/Info.plist auditada no
  mesmo arquivo que será consumido, proteção TOCTOU,
  confirmação do usuário e recuperação/backup testados.
- O appinst 2.1.1 ainda apresenta a questão de uma segunda
  cópia para pasta temporária solicitada como 0777.
  O risco precisa ser resolvido e sua origem autenticada
  antes de integração privilegiada.
- Nenhuma IPA foi instalada, nenhuma lib de privilégio
  foi adicionada ao WebReader. A versão do app continua 56
  na branch e a main preservada.

## Gatilho para próximo estágio

**CI verde no commit exato do PR #90**. Se houver erros no C,
Swift ou Xcode, corrigir antes de solicitar teste no iPhone.

Depois, quando necessário, testar APENAS o bundle diagnóstico
isolado e a conexão PING/PONG. Sem instalação de updates,
Build 57, release de produção, chave real ou merge.
