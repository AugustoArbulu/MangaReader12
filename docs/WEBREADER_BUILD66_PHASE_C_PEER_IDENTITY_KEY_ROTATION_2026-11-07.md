# WebReader — Build 66 / Fase C: autenticidade do peer e política de rotação de chaves
**Data:** 2026-11-07 UTC  
**Escopo:** pesquisa de segurança em host, sem instalação, sem helper privilegiado  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`  
**PR:** #90, Draft, base `main`  
**Versão física preservada:** Build 65 (iOS 12.5.8), biblioteca e capítulos offline sem alterações

## Entrega em lote

A Fase C acrescenta três verificações isoladas e suas suítes de testes à auditoria da Build 66:

| Código | Função | Resultado autorizado |
| --- | --- | --- |
| `ci/build66_peer_evidence_policy.py` | Analisa relato JSON não confiável sobre transporte, PID, UID, HMAC, nome e identidade ad hoc | **DENIED** em todos os casos |
| `ci/build66_release_key_rotation_lab.py` | Simula candidata à rotação P-256 com duas assinaturas — chave antiga pinada e nova chave — e geração crescente | **Somente revisão**, não muda chave |
| `ci/build66_peer_capability_report.py` | Lê exatamente 4 linhas do diagnóstico Build 63 para classificar observações TCP/UNIX | **Observação apenas**, sem identidade |
| `ci/test_build66_peer_evidence_policy.py` | 28 testes de falsificação, ausência de prova, campos extra e JSON malformado | Nenhuma elevação |
| `ci/test_build66_release_key_rotation_lab.py` | 26 testes de continuidade criptográfica, geração, assinatura, chave errada e injeção | Nenhuma rotação real |
| `ci/test_build66_peer_capability_report.py` | 19 testes de relatórios, permissões negadas, status inesperado e texto falsificado | Nenhuma elevação |

O teste `ci/test_chimera_peer_probe63.py` foi atualizado para passar o texto emitido pelo binário C nativo macOS ao parser novo. O teste avalia o comportamento do **macOS**, não a disponibilidade de APIs no iOS 12.5.8.

## Resultado de verificação

- GitHub Actions `WebReader Build66 IPA Preflight Security QA`, **#88**, run `42340063625`:
  - Etapa Linux: **SUCCESS**, 238 testes Python (soma das suítes).
  - Etapa macOS: **SUCCESS** no run #88; o verificador Swift Security.framework, a checagem nativa de instalação bloqueada, os testes codesign e quatro rodadas reais do diagnóstico Build63 em macOS passaram. Em cada rodada: TCP e UNIX `PEER_PID=MATCH` com `AUTHORIZATION=DENIED`.
- Suíte anteriormente aprovada `#73` (run `42339159926`) já confirmou as verificações nativas Swift do instalador bloqueado e do Security.framework.
- O laboratório é inteiramente offline com chaves efêmeras, arquivos sintéticos e relatórios de diagnóstico. Nenhum comando de instalação é invocado.
- O projeto em produção permanece com `liveInstallationEnabled = false` e `productionPublicKeyX963 = nil`.

## Matriz de identidade / admissibilidade

| Evidência | O que demonstra | O que **não** demonstra |
| --- | --- | --- |
| Loopback TCP responde PONG | Rede local/processo respondeu | Ser o WebReader |
| PID via getsockopt | Metadado de processo observado | Código/assinatura vinculados sem race |
| UID mobile | Identidade de usuário do processo | App exclusivo; múltiplos processos podem compartilhar UID |
| HMAC de código temporário | Posse do segredo de pareamento | Autor legítimo do aplicativo e sua assinatura |
| Mesmo Bundle ID / entitlement ad hoc | Strings/estrutura compatíveis | Publicador inequívoco no jailbreak |
| `auditTokenClaimed=true` em JSON | Apenas alegação de um solicitante | Um audit token entregue e verificado pelo kernel |
| `PEER_PID=MATCH` no Build63 | Correspondência em teste efêmero controlado | Atestação do WebReader real em iOS12 |

O avaliador **nunca** retorna `requester_authenticated=true`, `installation_authorized=true` ou `installation_performed=true`. Mesmo todos os campos autorrelatados como verdadeiros continuam rejeitados.

### Compatibilidade iOS12 e uso de API

- A Build63 anterior mediu PID do peer no macOS com `LOCAL_PEERPID` e opção privada `TCP_PEER_PID`. O diagnóstico no Chimera real **ainda não foi comprovado**.
- O código-fonte de Security da Apple adverte explicitamente que `SecCodeCreateWithPID` sofre race e recomenda identificação por audit token: https://github.com/apple-oss-distributions/Security/blob/main/OSX/libsecurity_codesigning/lib/SecCode.cpp
- No código-fonte Apple analisado, `SecCodeCreateWithAuditToken` / `SecCodeCreateWithXPCMessage` aparecem em um bloco `#if TARGET_OS_OSX`. Isso **não autoriza** presumir disponibilidade no iOS12 nem portar um serviço macOS para Chimera sem ensaio.
- A documentação Apple de `SecCodeCopyGuestWithAttributes` descreve atribuição de código ao guest e seus possíveis erros, mas não comprova viabilidade no iOS12: https://developer.apple.com/documentation/security/seccodecopyguestwithattributes
- Portanto, nenhum processo adquire privilégio via PID/UID/HMAC/audit-token autorrelatado. Autenticação do peer **continua bloqueador** para appinst.

## Rotação editorial P-256 — ensaio sem ativação

O laboratório recebe `current_generation`, `installed_build`, chave pública antiga, chave pública nova e um hash SPKI SHA-256 **previamente pinado por meio confiável**. Exige:

1. Chaves EC P-256 válidas; impressão digital da chave antiga igual ao pin independente.
2. `fromSPKI` e `toSPKI` compatíveis com as duas chaves; mudança efetiva da chave.
3. `generation == current_generation + 1` e `activateAtBuild > installed_build`.
4. Payload JSON exato e duas assinaturas ECDSA SHA-256, verificadas sobre os mesmos bytes.
5. Nenhum campo extra (como `install`), assinatura ausente, geração velha ou algoritmo alternativo.

Saída permanece `production_key_rotated=false`, `independent_operator_review_required=true`, `revocation_checked=false`, `installation_authorized=false`.

**Limites:** a geração é fornecida por um host de testes, não ancorada em armazenamento não-retrocedível do helper; a chave antiga comprometida poderia assinar uma substituição maliciosa; assinatura dupla sozinha não constitui aprovação independente nem política de revogação. Nenhum pin de produção foi criado, exportado ou instalado na Build65.

## Próximo gate real

1. **Capacidade física do dispositivo:** validar, em teste observacional opcional e isolado, se o iOS12.5.8/Chimera disponibiliza um vínculo de identidade de código **derivado do kernel/descritor IPC**, não de PID consultado posteriormente. Não escalar privilégios para fazer diagnóstico funcionar.
2. **Autenticidade do solicitante:** provar que a identidade é do app esperado e está criptograficamente vinculada ao canal, sem confiar em Bundle ID/HMAC/claims declarados pelo cliente.
3. **Custódia de chaves:** definir procedimento de release público ou autorizado, chave privada off-repo, pin independente de produção, rotação e revogação aprovadas pelo proprietário.
4. **Proteção do helper:** armazenamento protegido não gravável pelo cliente, epoch/rollback, nonce one-shot com consentimento verificável e conferência independente dos bytes realmente encaminhados para instalação.
5. **Fallback:** se não houver autenticação independente praticável no Chimera, manter atualização manual pelo Filza ou IPA verificada/exportada no app, sem appinst automático.
6. **QA de dados:** preservar a biblioteca e downloads offline da Build65; não desinstalar o aplicativo antes de atualização, não distribuir build de teste sem evidências completas.

**Proibições mantidas:** sem modificar `main`, sem liberar PR #90 de Draft, sem IPA nova para o iPad, sem helper root, sem download/instalação pelo laboratório, sem chave de release de produção e sem reconectar os serviços PING Build61/63 ao `appinst`.
