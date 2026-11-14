# WebReader — Build 69 futura: Fases AS/AT/AU, bootstrap editorial e rotação segura

**Estado:** 09/11/2026 UTC — desenvolvimento da futura Build69, **sem IPA distribuída**, sem release ou canal publicado.  
**Branch:** `feat/chimera-updater-phase1-protocol-audit`, [PR #90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90), `main` intocada.  
**Referência física imutável:** Build68 aprovada no iPad iOS 12.5.8, biblioteca e capítulos offline preservados; IPA SHA256 `fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`, candidato `605f607b08d714d8eabfd3270516b77dfaf673e0`. Nenhuma alteração no iPad.

Este lote estende a [preparação AP–AR](WEBREADER_BUILD69_PHASES_AP_AQ_AR_PRODUCTION_RELEASE_OPERATIONS_2026-11-08.md), não a substitui.

## AS — verificar identidade do root antes de qualquer HTTPS

A verificação de assinatura ECDSA do manifesto já comparava o fingerprint SPKI com a chave pública. Porém, a propriedade `WebReaderProductionPublisherTrust.isProvisioned`, usada **antes de abrir URLSession**, só conferia que o pin parecia hexadecimal e que o ponto X9.63 parecia ter 65 bytes: uma configuração P-256 incompatível poderia permitir requisição de rede, para ser rejeitada só depois.

Corrigido:

- `WebReaderSignedReleaseTrustGate.observedP256SPKISHA256(for:)` agora verifica **ponto EC P-256 real com Security.framework/SecKeyCreateWithData**, suporte ao algoritmo ECDSA-SHA256 e calcula SHA-256 da estrutura **DER SPKI canônica** (prefixo P-256 + ponto X9.63 de 65 bytes), usando CommonCrypto.
- O verificador de manifesto reutiliza exatamente essa função, eliminando cálculo duplicado e discrepância futura entre a verificação na pré-rede e a verificação após resposta.
- `WebReaderProductionPublisherTrust.isCandidateReadyForReview` é uma **função pura** para testes/revisão: valida geração >=1, pin hexadecimal, revogações e igualdade criptográfica SPKI/pin. Seu retorno nunca ativa ou inscreve o trust root.
- `isProvisioned` invoca a função acima **somente com constantes compiladas e revisadas pelo proprietário**; a UI não fornece pin/chave por argumentos, preferência local, manifesto ou resposta HTTP. A verificação do root continua `false` no código de produção.

Teste Swift nativo: `ci/test_native_webreader_owner_trust_readiness.py`, com chave pública P-256 descartável e pin calculado independentemente via OpenSSL. Confere caso positivo somente em `isCandidateReadyForReview`, bloqueio de geração 0, pin errado, pin revogado, ponto 65 bytes inválido/off-curve, chave ausente e `isProvisioned=false` no aplicativo real. **Não faz request HTTP.**

## AT — revisão de bootstrap por material estritamente público

Novo módulo host-only `ci/build69_publisher_bootstrap_review.py`. Aceita **apenas chave pública PEM** e pin SHA-256 SPKI conferido **fora do manifesto e fora do mesmo canal não confiável**; exige geração inicial 1, baseline Build68+, revogações imutáveis e válidas. Reutiliza `prepare_public_key_handoff` da Fase R.

Exemplo de **revisão futura**, sem configurar o WebReader:

```bash
python3 ci/build69_publisher_bootstrap_review.py \
  --public-key /external/owner/public-release-p256.pem \
  --independent-spki-sha256 "$OWNER_CHECKED_PIN" \
  --trust-generation 1 --installed-build 68
```

O PEM deve estar fora do repositório, em arquivo regular, não symlink; a ferramenta compara a versão canônica SPKI e a representação X9.63 consumida no iOS12. **O operador deve obter `OWNER_CHECKED_PIN` de um canal independente confiável; a ferramenta só verifica igualdade técnica e não consegue atestar a independência da origem.**

O recibo informa explicitamente `productionKeyProvisionedInApp=false`, `ownerExplicitApprovalRecorded=false`, `sourceTreeChanged=false`, `publicationAuthorized=false`, `chimeraInstallationAuthorized=false` e `installationPerformed=false`. Não altera arquivos, `main`, publicação, iPad ou o instalador. Testes: `ci/test_build69_phase_at_owner_bootstrap.py` + `ci/test_build69_phase_as_at_owner_trust_policy.py`.

## AU — rotação de chave não é recuperação automática

Novo `ci/build69_owner_rotation_review.py` exige, para uma **rotação planejada**:

1. Chave pública antiga, correspondente ao pin anterior confiável.
2. Chave pública sucessora e **pin sucessor independente**, além das assinaturas da rotação.
3. Envelope ECDSA de rotação assinado pelas duas chaves (contrato da Fase X); claims de geração consecutiva, ativação em build futura, SPKIs corretos e revogações verificadas.
4. Nenhum pin revogado entre origem e destino, nenhuma troca para a mesma chave, nenhum downgrade e nenhuma aceitação de `ownerApproved=true` em payload como evidência de consentimento.

O recibo é **somente leitura** e retorna `successorTrustRootInstalledInApp=false`, `revocationsUpdatedOnDevice=false`, `ownerPublicationApprovalRecorded=false`, `automaticRecoveryFromRevokedKeyAllowed=false`. Testes `ci/test_build69_phase_au_owner_rotation.py` usam duas chaves efêmeras reais + uma terceira atacante; verificam falsos assinantes, pins errados, repetição de geração, revogação e claims extras.

**Recuperação de comprometimento:** se a chave antiga foi roubada/revogada, ela não deve autorizar sua própria sucessora por um manifesto remoto, nem deve ser ignorada a lista de revogações enviada por rede. Recuperação correta é **nova autoridade editorial aprovada fora de banda + binário revisado e instalado manualmente no iPad**, preservando a biblioteca e testando offline. A atualização automática pelo Chimera permanece fora do escopo.

## Política de custódia humana pendente

A chave privada genuína de releases **não foi gerada** e não deve ser colocada em PR, GitHub Actions, Github Secrets, IPA, diretório do projeto, Filza ou chat. Antes de aprovar o bootstrap real, o proprietário precisa estabelecer custódia em dispositivo externo protegido, backup de recuperação criptografado, autoridade para assinar, procedimento de revogação, fonte independente para comunicar o fingerprint público e checklist de revisão de código.

Recomendação operacional: ao obter o material público real, comparar o fingerprint SPKI SHA-256 com **um registro prévio independente**; não aceitar que a própria página do GitHub ou o manifesto anunciem a identidade confiável. Revisar separadamente o par de constantes `productionPublicKeyX963` e `independentlyProvisionedSPKISHA256` na **nova** IPA e testar a igualdade off-line. **Nenhum desses campos deve ser alterado nesta PR antes da autorização do proprietário.**

## Gates e resultados

| Gate | Situação |
| --- | --- |
| Verificador ECDSA v2 por canal | Implementado (Fases AO/AP) |
| Preflight host SHA/ZIP/code seal com IPA real | Implementado (AR); execução real sobre Build69 inexistente |
| Pré-rede chave real + SPKI + revogação | Implementado (AS), produção desabilitada |
| Revisão inicial de root público (sem inscrição) | Implementado (AT) |
| Revisão de sucessor/dupla assinatura (sem rotação) | Implementado (AU) |
| Chave editorial privada real sob custódia aprovada | PENDENTE |
| Pin público independentemente conferido para produção | PENDENTE |
| Nova Build iOS12 com trust root público revisado e QA física | PENDENTE |
| GitHub Release público e `main/updates/channel-production-v2.json` | NÃO AUTORIZADO / NÃO PUBLICADO |
| Instalação direta Chimera | BLOQUEADA — identidade peer, consentimento one-shot e antirreplay durável |

O workflow integrado `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml` inclui os testes AS/AT/AU, além dos anteriores, e compila Debug/Release ARM64/iOS12 **sem produzir IPA**. Um CI aprovado não significa validação física, publicação ou recuperação segura.

## Próximo marco

Manter Build68 como referência aprovada, branch experimental e PR #90 Draft. Próximo marco técnico recomendado: **auditoria final de bootstrap e UX do canal assinado sem provedor configurado**, depois preparar uma candidata manual de Build69 só quando a política editorial estiver aprovada e os testes de segurança integrais verdes. Publicar/alterar `main` requer autorização expressa. Não armazenar material privado real na conversa.
