# WebReader / Build 66 — prova isolada de sessão one-shot (07/11/2026)

Estado: **laboratório offline, SEM instalação e SEM autenticação de peer**.
Branch: \`feat/chimera-updater-phase1-protocol-audit\`, PR #90 Draft,
sem modificações em \`main\` ou na Build65 instalada.

## O que foi implementado

\`ci/build66_one_shot_diagnostic.py\` implementa somente uma máquina de
estados de **consistência do pedido**. Não usa IPC, sockets, download, código
privilegiado, \`appinst\`, shell ou funções capazes de instalar IPA.

- Um desafio de 16 bytes gerados criptograficamente vira um nonce hexadecimal
  minúsculo de 32 caracteres. O nonce é **público**, não é uma credencial e
  nunca autentica o processo que o apresenta.
- A sessão é válida no laboratório por 30 segundos por padrão, máximo 60,
  usando relógio monotônico. Um pedido, inclusive malformado, consome a
  sessão irrevogavelmente nesse processo; tentativas seguintes rejeitam replay.
- O protocolo aceito tem **somente** operação literal \`CHECK_ONLY\`. O parser
  exige campos exatos, UTF-8, JSON sem chaves duplicadas (inclusive escapes
  Unicode), payload de até 2048 bytes e versão literal 1.
- O pedido é comparado com referências que devem provir de uma verificação
  **independente e confiável** de manifesto assinado e bytes IPA: build
  estritamente superior ao instalado, digest do manifesto, digest da IPA,
  Bundle ID e \`application-identifier\`.
- Qualquer campo extra (ex.: \`ipaPath\`, \`install\`), opcode de instalação,
  hash divergente, nonce errado, expiração ou dupla tentativa é rejeitado.
- Um \`threading.Lock\` serializa a avaliação simultânea para evitar duas
  aceitações concorrentes na mesma sessão.
- Mesmo quando \`request_consistent=True\`, o resultado declara
  \`installation_authorized=False\`, \`installation_performed=False\`,
  \`peer_identity_authenticated=False\`,
  \`user_install_consent_verified=False\`. Não existe chamada de instalação.

\`ci/test_build66_one_shot_diagnostic.py\` testa a máquina de estados isolada:
nonce, expiração, replay, concorrência, downgrade, digests, JSON e injeções.

\`ci/test_build66_one_shot_signed_release_chain.py\` acrescenta integração
offline com o contrato v2: ECDSA temporária -> manifesto sintético assinado ->
IPA sintética com digest exato -> referência da sessão -> pedido de teste.
A assinatura de código dos fixtures Linux **não** é atestada nessa cadeia.
O resultado nunca equivale à autorização de um instalador.

CI: \`.github/workflows/chimera-build66-preflight.yml\` executa testes
relevantes em Linux, audita ausência de APIs privilegiadas e mantém o
\`liveInstallationEnabled = false\` no cliente Swift; a suíte macOS segue
validando \`codesign\` com fixtures e o verificador nativo Swift.

## Fronteiras ainda NÃO resolvidas

1. **Identidade do solicitante**: UID, PID, portas localhost, nome do socket,
   PING e pareamento HMAC não comprovam que o cliente é o WebReader correto.
   A assinatura ad hoc também não fornece cadeia Apple de identidade de autor.
   É necessário um mecanismo de identidade de peer e prova independente,
   testado fisicamente no Chimera/iOS12 antes de qualquer operação privilegiada.
2. **Consentimento do usuário**: não há canal de consentimento confiável ou
   ligação criptográfica desse consentimento ao arquivo exato. O campo
   \`CHECK_ONLY\` não representa permissão para instalar.
3. **Replay entre reinicializações**: o laboratório guarda o estado apenas na
   memória do processo. A proteção real requer estado persistente, antirrollback,
   sem aceitar como confiável estado gravável por um cliente não privilegiado.
4. **Origem editorial**: ainda não foi fornecida/chancelada pelo proprietário
   uma chave pública de release de produção. A chave pública de produção do
   cliente iOS continua \`nil\`. As chaves dos testes são descartáveis.
5. **TOCTOU na instalação**: o helper real precisará verificar novamente
   a assinatura, entitlements e SHA-256 do objeto imutável que será entregue ao
   instalador. A verificação no host não basta.
6. **Distribuição privada**: os Release assets de um repositório privado
   podem exigir autenticação, e um fluxo público de atualização requer decisão
   explícita do proprietário e política de publicação.

## Gate

Enquanto qualquer condição acima não estiver resolvida, o código de produção
deve manter \`WebReaderAppinstSocket.liveInstallationEnabled = false\`.
Não reutilizar a ponte PING/HMAC como instalador. Não publicar uma Build66
instalável, não usar helper root e não pedir novos testes físicos na Build65.

Próximo trabalho seguro: preparar uma especificação de autenticador do peer e
estado persistente de um helper **independente**, mantendo funções de
instalação e privilégios ausentes durante toda a QA de laboratório.
