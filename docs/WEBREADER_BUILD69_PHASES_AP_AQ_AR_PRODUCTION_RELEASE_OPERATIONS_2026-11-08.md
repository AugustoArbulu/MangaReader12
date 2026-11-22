# WebReader — Build 69 futura, fases AP/AQ/AR: preparação operacional de releases assinados

**Estado:** 08/11/2026, fase de engenharia (nenhuma publicação, instalação ou chave gerada).  
**Repositório:** `AugustoArbulu/MangaReader12`; branch `feat/chimera-updater-phase1-protocol-audit`; PR [#90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). **Não alterar `main` sem nova autorização expressa.**  
**Referência física:** Build 68 instalada e aprovada pelo proprietário no iPad iOS 12.5.8; biblioteca e capítulos offline preservados. IPA aprovada SHA-256 `fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`, commit candidato `605f607b08d714d8eabfd3270516b77dfaf673e0`. Não substituir o arquivo nem reutilizar o hash para uma IPA nova.

## O que mudou — sem ativar produção

- **AP — verificador de referência separado por canal:** `ci/webreader_update_manifest.py` passou a aceitar `expected_channel="production"` *somente se explicitamente solicitado*, exigindo **schema v2**. O padrão continua `development`. `ci/build66_signed_release_preflight.py` propaga a exigência ao cruzamento com uma única cópia auditada da IPA. Uma assinatura ECDSA válida de desenvolvimento é rejeitada como produção e vice-versa.
- **AQ — preparador offline de envelope:** `ci/prepare_signed_webreader_update.py` aceita `--channel production` somente com `--schema-version 2`, `--installed-build` explícito >=68 e `--independent-spki-sha256`. O PEM público deve concordar com o fingerprint SHA-256 do DER SPKI recebido *antes*, por uma autoridade/canal independente. Continua a exigir IPA ad hoc com `codesign` nativo macOS, mesma identidade instalada, caminhos fora do repositório, chave privada protegida e saída 0600 que não sobrepõe arquivo existente. **Não publica nem provisiona a chave no WebReader.**
- **AR — auditor de lançamento com dupla ligação:** `ci/build69_production_release_preflight.py` lê um manifesto de produção já assinado, a chave pública e o fingerprint confiável; exige assinatura v2 `production`, canal de URL fixo, build superior, SHA-256/tamanho e ZIP/Info.plist da **mesma IPA**, depois exige `codesign` nativo sobre o snapshot verificado. O recibo registra os hashes e deixa **todos** os campos de aprovação, publicação e instalação como `false`. Não acessa internet e não chama o Chimera.

## Decisão de custódia editorial pendente — ainda requer o proprietário

A autoridade editorial é o proprietário do projeto, não o GitHub Actions nem o próprio manifesto. A chave **privada** de produção P-256 deve ser gerada/protegida **fora** do repositório e do CI, em um ambiente controlado pelo proprietário (preferencialmente dispositivo/mídia offline com cópia de recuperação criptografada e separada). Estabelecer antes da primeira assinatura:

1. Qual dispositivo/offline vault mantém o material privado; quem pode assiná-lo; como revogar acesso; onde guardar a recuperação, sem compartilhar a senha no chat.
2. Um registro **fora do repositório** da chave pública SPKI, fingerprint SHA-256 do **DER canônico**, geração `1`, data de adoção, evidência de duas conferências independentes (idealmente segunda máquina ou mídia já confiável).
3. Um processo de assinatura manual sob custódia do proprietário. Não carregar chave privada no GitHub Secrets, PR, Actions artifact, IPA, app bundle, comentários, histórico de shell compartilhado ou chat. Chave de testes jamais passa a produção.
4. Plano de revogação/rotação e recuperação. A Build 68 não dispõe de root de confiança para aceitar atualização remota de chave. Não confiar em revogação enviada exclusivamente pelo manifesto/host comprometido.
5. Atestação final do operador conferindo hash/pin com a cópia offline antes de qualquer release. É um procedimento administrativo, não uma propriedade que o script consiga provar sozinho.

**Ponto de bootstrap:** a Build 68 já instalada contém `productionPublicKeyX963=nil` e `independentlyProvisionedSPKISHA256=nil`. Mesmo que um manifesto de produção seja publicado agora, **essa build não poderá autenticá-lo ou descobrir uma atualização assinada**. Será necessária **primeiro** uma build revisada com a chave pública e pin conferidos independentemente, instalada manualmente pelo Filza após QA física, antes de receber atualizações assinadas. Esta fase **não** realiza esse provisionamento.

## Ensaio controlado no macOS, sem publicação

Depois que *o proprietário* tiver decidido a custódia, criado a chave real fora do repositório e separado um candidato QA efetivamente auditado (Build >68), executar localmente, **nunca no workflow automático**, com caminhos externos:

```bash
python3 ci/prepare_signed_webreader_update.py \
  --schema-version 2 --channel production --installed-build 68 \
  --ipa /external/approved/WebReader-Build69-iOS12-adhoc.ipa \
  --private-key /offline/private/release-p256.key \
  --public-key /offline/public/release-p256.pem \
  --independent-spki-sha256 "$OWNER_VERIFIED_SPKI_SHA256" \
  --notes-file /external/approved/notes.json \
  --published-at 2026-11-08T22:00:00Z \
  --output /external/staging/channel-production-v2.json
python3 ci/build69_production_release_preflight.py \
  --public-key /offline/public/release-p256.pem \
  --independent-spki-sha256 "$OWNER_VERIFIED_SPKI_SHA256" \
  --manifest /external/staging/channel-production-v2.json \
  --ipa /external/approved/WebReader-Build69-iOS12-adhoc.ipa \
  --installed-build 68
```

`OWNER_VERIFIED_SPKI_SHA256` **não** deve ser preenchido pelo valor anunciado no GitHub Release, no próprio manifesto nem na mesma fonte da chave sem verificação independente. O exemplo é instrução operacional futura; **não há IPA Build69, chave real, fingerprint confiável ou manifesto assinado produzidos nesta entrega**. O comando de preparo só funciona com uma IPA real compatível, já assinada ad hoc; um ZIP sintético é recusado pela auditoria nativa.

## Matriz de aprovação para a futura publicação

| Gate | Critério objetivo | Situação |
| --- | --- | --- |
| A — titularidade | Proprietário define custódia, revogação e operação offline | **PENDENTE** |
| B — root de confiança | Fingerprint público do SPKI verificado independentemente + X9.63 public key revisada | **PENDENTE** |
| C — bootstrap manual | Binário QA iOS 12 com root de confiança embutido; testes físicos sem perda de biblioteca | **PENDENTE** |
| D — pacote | IPA com versão maior que a instalada, mesma identidade, entitlements, SHA e assinatura ad hoc nativa | **PENDENTE** |
| E — envelope | Manifesto `production` v2 ECDSA vinculado aos bytes da IPA e URL exata da Release | **PENDENTE** |
| F — revisão | Preflight offline macOS com recibo e segunda verificação humana | **PENDENTE** |
| G — autorização | Aprovação explícita do proprietário para criar Release público e alterar `main/updates/channel-production-v2.json` | **NÃO CONCEDIDA** |
| H — distribuição | Publicação atômica planejada: asset imutável `buildN`, feed assinado apontando para a mesma IPA | **NÃO EXECUTADA** |
| I — instalação automática | Identidade independente do peer Chimera, consentimento one-shot, antirreplay durável e bytes imutáveis | **BLOQUEADO** |

O fluxo de publicação, quando e somente quando aprovado, deve disponibilizar primeiro um **asset imutável auditado**, conferir SHA após upload e só depois publicar o manifesto assinado que referencia exatamente aquele SHA. Nunca promover automaticamente um artefato do GitHub Actions para Release e nunca substituir bytes sob o mesmo nome/versão. Se qualquer checagem falhar, não alterar `main` nem executar `appinst`.

## Validação de engenharia e limites

- `ci/test_build69_phase_ap_aq_ar_production_rehearsal.py` usa chaves P-256 **descartáveis** e IPA **sintética** para testar assinatura verdadeira, rejeições cruzadas dev/prod, v1 em produção, pin incorreto, IPA alterada, baseline antiga, URLs e ausência de privilégio.
- Um teste da camada nativa utiliza **mock** de `codesign` apenas para validar o contrato do orquestrador; outro teste exige recusa do ZIP sintético quando o auditor nativo real é acionado. **Não** interpretar mock como autenticação de uma IPA real.
- O workflow `chimera-build69-phase-ac-af-integrated-qa.yml` passou a rodar a suíte AP–AR no Linux juntamente com regressões existentes, e mantém compilação Swift Debug/Release ARM64/iOS12 em macOS **sem empacotar IPA**.
- Um eventual CI verde prova apenas os testes realizados, **não** QA física, custódia segura efetiva, presença de root em produção ou instalação segura.

## Estado a preservar no próximo avanço

`WebReaderUpdateChannel.productionPublicKeyX963=nil`; `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`; `productionTrustGeneration=0`; `WebReaderAppinstSocket.liveInstallationEnabled=false`. Build68 aprovada e intacta. Build69 somente experimental, sem IPA distribuída. PR #90 continua Draft; `main` permanece intocada. Biblioteca e capítulos offline não foram acessados. **Nenhuma autorização para publicação foi solicitada nem presumida.**
