# WebReader Build70 — Fase CG, preparação offline da chave pública editorial

**09/11/2026.** Branch `feat/chimera-updater-phase1-protocol-audit`; PR #90 Draft. Build70 continua a referência física relatada como funcionando. As alterações CG são apenas host-side/QA; não geram IPA, não acionam o instalador e não modificam `main`.

## O que mudou e por que importa

A verificação real de uma IPA Build70 por manifesto de produção v2 foi aprovada na CI CE #42712666573. A CI AC–CF #42712990625 aprovou os dois jobs, incluindo o verificador Swift que *não aceita* a chave do usuário ou do manifesto: apenas futuras constantes compiladas e revisadas. A Build70 instalada ainda não contém uma chave pública editorial real.

CG acrescenta `ci/build70_owner_public_root_patch_preview.py`: operador fornece **apenas** um arquivo PEM **público**, armazenado fora do repo, e o fingerprint SHA-256 da representação DER SPKI, conferido por canal independente. Reutiliza o auditor rigoroso `review_owner_public_bootstrap` da fase AT.

O programa gera um único arquivo `.patch` **externo**, sem aplicá-lo ao repositório. Ele altera *somente na proposta*:
- `WebReaderUpdateChannel.productionPublicKeyX963` (ponto público P-256, 65 bytes);
- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256` (hash canônico);
- `WebReaderProductionPublisherTrust.productionTrustGeneration` (0 → 1).

As revogações continuam intocadas, a chave privada não é lida e `WebReaderAppinstSocket.liveInstallationEnabled = false` é requisito explícito. O gerador recusa fonte compilada inesperadamente alterada, projeto com versão diferente de 56, Build física inferior à 70, output no repo, symlink e output já existente. Cria o patch com permissão 0600, `O_EXCL` e `fsync` (nunca remove arquivo externo que não criou). O recibo declara expressamente `sourceTreeChanged=false`, `productionTrustActivated=false` e `installationAuthorized=false`.

### Exemplo futuro (não executar no GitHub Actions)

O proprietário mantém **a chave privada exclusivamente sob custódia local externa**, com backup criptografado e acesso restrito. Uma opção para gerar o par P-256 num computador sob seu controle, depois de instalar e verificar o OpenSSL, é:

```bash
openssl ecparam -genkey -name prime256v1 -noout -out /seguro/fora-do-repo/release-private.pem
openssl pkey -in /seguro/fora-do-repo/release-private.pem -pubout -out /seguro/fora-do-repo/release-public.pem
openssl pkey -pubin -in /seguro/fora-do-repo/release-public.pem -outform DER | openssl dgst -sha256
```

A chave **privada nunca deve ser enviada ao chat, GitHub, GitHub Actions, app iOS, Filza ou a qualquer repositório**. O fingerprint público deve ser registrado/confirmado fora da mesma fonte que distribuirá manifestos e assets.

Depois que o proprietário controlar seu material público e conferir o fingerprint de modo independente, o script de revisão pode ser usado:

```bash
python3 ci/build70_owner_public_root_patch_preview.py \
  --public-key /seguro/fora-do-repo/release-public.pem \
  --independent-spki-sha256 "$OWNER_CONFIRMED_SHA256" \
  --installed-build 70 \
  --output-patch /seguro/fora-do-repo/owner-public-root-review.patch
```

**Nada é inscrito automaticamente.** Um passo separado deve revisar o diff público, a origem da chave, o plano de revogação e o impacto na assinatura, então criar uma nova IPA experimental assinada, auditar o resultado e testar manualmente sem apagar downloads. O usuário já autorizou uso do GitHub para desenvolvimento, mas o cadastro efetivo de uma nova identidade editorial não é inferido de uma autorização genérica.

## Distribuição sem senha no iPad

O repositório `AugustoArbulu/MangaReader12` está **público** (verificado na API GitHub em 09/11/2026). O atual código de manifesto aceita `https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/updates/channel-production-v2.json` e a IPA com nome `WebReader-BuildN-iOS12-adhoc.ipa` em Release tag `buildN`. **Ainda não publicamos esse manifesto nem um Release de produção**.

**Verificação real pelo GitHub API em 09/11/2026:** o repositório está público, o endpoint `/releases` retornou lista vazia e `main/updates/channel-production-v2.json` retornou HTTP 404. Portanto não há atualização editorial de produção disponível ao app neste momento. Criar essa publicação só será adequado depois de revisar a chave pública real e o manifesto assinado.

Artifatos temporários Actions (como as IPAs 69 e 70 de teste) não substituem um release estável: expiram e não têm o mesmo endereço canônico. O WebReader poderá consultar o Release público sem token do GitHub **quando** o manifesto v2 estiver publicado e a chave pública editorial estiver embutida no app.

## Testes e bloqueios

- `ci/test_build70_owner_public_root_patch_preview.py` cobre chave P-256 efêmera, patch de somente dois arquivos, no-write à árvore, hash incorreto, PEM privado, baseline inválido, output symlink, output dentro do repo, output já existente e corrida `O_EXCL`.
- [CI AC–CG](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42718943078): Python/Linux e compilações iOS12/Mac.
- [CE IPA70 real](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42712666573): SUCCESS.
- [AC–CF produção fail-closed](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42712990625): SUCCESS 2/2.

**Continua pendente:** chave editorial privada real sob custódia do proprietário, aprovação e compilação do pin público na próxima IPA, Release permanente e manifesto v2, testes de iOS12, identidade do peer no helper, proteção de replay e consentimento seguro. O script CG não assina nada nem autoriza install. Nenhuma alteração à biblioteca ou aos downloads do iPad.
