# WebReader/MangaReader12 — Fase E: csops_audittoken × LOCAL_PEERTOKEN

Data: 2026-11-07 (UTC)
Branch exclusiva: \`feat/chimera-updater-phase1-protocol-audit\`  
PR #90 Draft, base \`main\`. Nunca mesclar sem aprovação.
Build65 iOS12.5.8 no iPad: estável, biblioteca e leitura offline já aprovadas.

## Objetivo

Investigar, SEM INSTALAÇÃO, se um token recuperado do kernel via
\`getsockopt(SOL_LOCAL, LOCAL_PEERTOKEN)\` pode ser usado por
\`csops_audittoken(pid, CS_OPS_CDHASH, ... token)\` em um **processo filho
controlado**. Medir se o kernel rejeita (a) token cuja versão de processo foi
alterada e (b) token do filho apresentado com o PID do próprio processo pai.

Não obter/verificar a identidade do WebReader real. Não adquirir privilégio.
Não conectar ao serviço Build61 PING, helper, \`appinst\`, IPA ou cliente Swift.

## Fundamentação

- XNU \`bsd/sys/codesign.h\` declara \`csops_audittoken\` e \`CS_OPS_CDHASH=5\`,
  e o código \`kern_proc.c\` compara PID e versão do processo recebidos no token
  com o processo encontrado. Alguns cabeçalhos históricos/reempacotados
  restringem operações disponíveis para a variante audit-token. Por isso,
  teste de runtime é necessário.
  https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_proc.c
  https://github.com/apple/darwin-xnu/blob/main/bsd/sys/codesign.h
- \`LOCAL_PEERTOKEN\` é uma observação do kernel no socket, ao contrário de
  strings declaradas pelo cliente. Porém, obter token ≠ autenticar
  publicador/CodeDirectory/instalação e não implica suporte do iOS 12.
- Os testes macOS NÃO demonstram disponibilidade/igualdade de comportamento
  no Chimera iOS 12.5.8, onde assinatura ad hoc, permissões e sandbox diferem.

## Entrega (código e testes)

| Arquivo | Função |
| --- | --- |
| \`ci/webreader_chimera_csops_token_probe66.c\` | Binário CLI não-root, apenas \`selftest\`, socket efêmero com filho controlado, \`LOCAL_PEERTOKEN\` e \`csops_audittoken\` via dlsym. Não imprime PID, token, CDHash ou caminhos pessoais. |
| \`ci/test_chimera_csops_token_probe66.py\` | Compila o C no macOS, executa quatro rodadas e obriga saída estrita sem autorização. |
| \`ci/build66_csops_capability_report.py\` | Parser exato de 7 linhas, sem assumir autenticidade do relatório. |
| \`ci/test_build66_csops_capability_report.py\` | 29 cenários de negação, resultado inseguro, truncamento, linhas falsas e vazamento de informações. |
| \`ci/package_chimera_csops_token_probe66.py\` | DEB opcional, **somente** um executável CLI, sem postinst, daemon ou appinst. |
| \`ci/test_chimera_csops_token_probe66_deb.py\` | Audita estrutura DEB, ARM64, iOS mínimo 12.0, codesign ad hoc, entitlements mínimos, ausência de spawn. |
| \`.github/workflows/chimera-build66-csops-probe.yml\` | CI Linux (teste de relatórios) e macOS (4 rodadas + compilação iOS12 + pacote). |

### Semântica da saída

Há sete linhas: header; \`UNIX_PEERTOKEN\`; \`CSOPS_TOKEN_BINDING\`;
3 linhas \`SECURITY_...\` sobre **presença** de símbolo; footer
\`FINAL_INSTALL_AUTHORIZATION=DENIED\`.

- \`MUTATION_REJECTED\`: chamada original foi aceita e tanto o token com
  versão modificada quanto a combinação token do filho/PID do pai foram
  rejeitados naquele ambiente de ensaio.
- \`MUTATION_ACCEPTED_UNSAFE\` ou \`CROSS_PID_ACCEPTED_UNSAFE\`: prova
  **negativa** de binding, nunca interpretar como autorização.
- \`CALL_DENIED\`, \`SYMBOL_MISSING\`, \`TOKEN_FIELDS_UNAVAILABLE\` ou
  \`NOT_TESTED\`: não há prova suficiente. Não mudar permissões para forçar sucesso.
- O parser retorna sempre \`webreader_peer_authenticated=False\`,
  \`publisher_authenticated=False\`, \`ios12_runtime_verified=False\`,
  \`installation_authorized=False\` e \`installation_performed=False\`.

A chamada \`csops_audittoken\` não imprime o resultado CDHash (mesmo em sucesso)
e nunca aceita PID fornecido pelo usuário: o PID do filho foi obtido do token,
o PID adversarial é o do próprio pai. Nenhum processo de terceiro é consultado.

## Estado da validação

**Workflow #2**, ID \`42341839243\`: **SUCCESS** com 28 cenários originais.
Foram observadas quatro respostas \`UNIX_PEERTOKEN=NONZERO\` e
\`CSOPS_TOKEN_BINDING=MUTATION_REJECTED\` em macOS não-root; compile iOS12
ARM64 e pacote DEB foram aprovados.

**Workflow #8**, ID \`42341928278\`: reexecução adiciona o ensaio com PID do
pai controlado e o 29º teste de saída. Confirmar resultado final em CI antes
de tratar como novo baseline. O trabalho anterior permaneceu aprovado.

Artefato inicial CLI-only aprovado na execução #2:
\`WebReader-Build66-CSOpsTokenProbe-CLI-only-iOS12\`, ID \`13562130682\`.
Contém \`WebReader-Chimera-CSOpsTokenProbe66-iOS12.deb\` e checksums;
não é uma IPA do WebReader nem foi instalado no dispositivo.

## Próximos gates

1. Avaliar **opcionalmente e com consentimento** execução não-root do CLI
   independente no iPad Chimera; validar código de saída e sete linhas, sem
   incluir dados pessoais. Não exigir que usuário instale ou execute nada agora.
2. Com suporte runtime comprovado, estudar como a identidade de código em
   execução poderia ser vinculada ao token da conexão e a uma raiz de confiança
   confiável no próprio helper. Um CDHash ad hoc isolado não autentica publicador.
3. Verificar estratégia de consentimento de instalação independente do cliente,
   e objeto IPA privado e imutável revalidado no helper. Sem esses gates,
   não existir helper privilegiado ou auto-instalação.
4. Se o iOS12 negar csops por política, manter fallback manual Filza ou
   somente download + validação da IPA no app.

**Travas de produção:** \`WebReaderAppinstSocket.liveInstallationEnabled=false\`;
\`productionPublicKeyX963=nil\`; PR #90 permanece Draft; \`main\` intocada;
sem construir IPA instalável Build66 e sem prejudicar biblioteca/arquivos da 65.
