# WebReader — Updater Chimera: Fase 5E, transações de revisão de uso único

**Data:** 2026-11-05  
**Branch experimental:** `feat/chimera-updater-phase1-protocol-audit` (PR #90 Draft)  
**Base física estável:** Build 56 em iOS 12.5.8, preservada na `main`

## Resultado e fronteira de confiança

A Fase 5D passou no GitHub Actions `41974713773`. Em seguida, a Fase 5E
implementou um **modelo em memória, somente no host**, para testar a
semântica de expiração, replay, cancelamento e isolamento do futuro protocolo
de revisão do helper.

Novos arquivos:
- `ci/webreader_helper_review_session.py`: `ReviewSessionLedger`
  (`begin_review`, `confirm_review`, `cancel_review`, `revoke_peer`).
- `ci/test_webreader_helper_review_session.py`: testes adversariais offline
  para repetição, expiração, conexão forjada, hash/build incorretos,
  capacidade/limite de memória, nonce reutilizado e desconexão.
- `.github/workflows/build.yml`: executa a nova suíte offline.

**Não existe serviço IPC, helper real, código rootful, instalação, download,
chave de produção, script de pós-instalação, invocação de appinst ou mudança
na Build 56** nesta fase. O resultado é apenas uma simulação de política.

## Invariantes modeladas

1. Cada conexão autenticada pelo **transporte nativo futuro** deverá receber
   um contexto opaco próprio. O `peer_context=object()` da suíte Python
   é apenas um marcador de teste; **não autentica o iPhone**. PIDs fornecidos
   pelo cliente ou strings arbitrárias não podem representar identidade.
2. Depois da análise do envelope JSON estrito da Fase 5D, o host simula
   a emissão de um challenge de **256 bits** gerado pelo servidor
   (`secrets.token_hex(32)`), exclusivo da conexão.
3. O challenge expira em **30 segundos** por padrão, admite apenas
   **uma confirmação** e é invalidado por cancelamento/desconexão.
   A semântica de tempo deve usar relógio monotônico **do servidor** no
   helper real; o `now` é injetado nos testes para simulação controlada.
4. A confirmação de revisão exige mesma sessão, build coincidente e
   digest SHA-256 coincidente com uma verificação **independente do helper**.
   O protótipo não tem tal verificador, apenas recebe um parâmetro
   chamado `independently_verified_digest`, que os testes simulam.
5. O nonce de correlação do cliente não é autenticação nem autorização;
   é retido por tempo limitado após consumo/cancelamento para rejeitar replay.
   O histórico tem limite superior para não crescer indefinidamente.
6. O objeto `ReviewAssessment` jamais possui permissão para instalação:
   `install_authorized` é uma propriedade somente leitura que retorna
   `False`, inclusive após uma revisão sem divergências.

## Ameaças não mitigadas por este protótipo

- Identidade criptográfica/credenciais de uma conexão IPC local real.
- Troca de processo, UID reutilizado, audittoken e verificação da assinatura
  de código do cliente no iOS12/jailbreak.
- Atualizações autenticadas com chave pública de produção independente no
  app e no helper; revogação e rotação de chave.
- Arquivo IPA no mesmo descritor do início ao fim: `openat`/`O_NOFOLLOW`,
  `fstat`, proteção contra hardlinks/TOCTOU, validação ZIP/Info.plist e
  integração com o instalador real sem comandos arbitrários.
- Aprovação humana explícita e efetiva em uma superfície confiável.
- Proveniência do `appinst` instalado no iPhone, funcionamento do AppSync,
  instalação idempotente e preservação do sandbox/arquivos offline.

**Critério de saída da Fase 5E:** CI da branch no HEAD exato deve passar.
Mesmo com CI verde, nenhuma permissão de executar `appinst` decorre disso.

## Próximas ações sugeridas

1. Inspecionar CI da Fase 5E e corrigir eventuais testes/compatibilidade.
2. Confrontar SHA-256 do executável dentro do `.deb` com o reportado
   diretamente de `/usr/bin/appinst` no iPhone, **somente leitura**,
   sem compartilhar o arquivo executável.
3. Obter cadeia independente de origem oficial antes de executar um
   componente privilegiado e revisar configuração Chimera/AppSync.
4. Criar, futuramente, um helper **separado** e testá-lo primeiro com app
   descartável, não com a Biblioteca real. Até lá, não publicar build nova,
   nem habilitar canal de produção ou merge.
