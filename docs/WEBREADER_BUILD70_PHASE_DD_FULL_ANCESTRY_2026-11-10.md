# WebReader Build70 — Fase DD: auditoria de todos os ancestrais do journal (host-only)

**Data:** 10/11/2026. **Repositório privado:** `AugustoArbulu/MangaReader12`. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90:** Draft, sem merge. `main`, GitHub Releases, Build70 instalada no iPad iOS12.5.8, biblioteca, favoritos e capítulos offline **não modificados**.

## 1. Diferença material em relação à DC

A Fase DC inspecionou somente o trecho `base/wr-dc-private/state/wr-da-review.lock` a partir de um diretório base **presumido** confiável. Os testes host rejeitam symlinks no próprio anchor e descendentes, mas isso **não garante** que algum componente ancestral de `base` seja genuíno, imutável ou inacessível ao cliente. Um pai transitável, mas alterável, pode trocar a subárvore inteira depois da análise, ou introduzir um symlink no caminho.

A Fase DD implementa uma verificação de metadados POSIX **somente leitura**, começando no descritor do diretório raiz `/` e percorrendo **todos os componentes do pathname literal do fixture**, por chamadas sucessivas a `openat` com `O_DIRECTORY|O_NOFOLLOW|O_CLOEXEC`. A cada abertura, compara `fstat` do FD com `fstatat(AT_SYMLINK_NOFOLLOW)` do nome sob o pai aberto, e exige metadados conservadores. Ao contrário de DC, um symlink em qualquer ancestral intermediário é recusado.

**O código nunca considera uma análise positiva motivo para instalar.** Os metadados continuam transitórios: entre um `stat` e o consumidor real, o proprietário do pathname, um helper com o mesmo UID, ou root ainda pode fazer alterações.

## 2. Implementação

Novos artefatos:
- `ci/build70_dd_full_ancestry.h` — contrato de recibo `WR_DD_Receipt`, status e campos de autoridade sempre false.
- `ci/build70_dd_full_ancestry.c` — auditor C de caminho completo, sem rede, socket, escrita, criação, remoção, instalação, `appinst` ou `LSApplicationWorkspace`.
- `ci/test_build70_dd_full_ancestry.py` — suíte host Linux/macOS com pasta de teste descartável criada no HOME do runner, cobrindo ancestrais graváveis e symlinks, journal, modos de diretórios/lock, alegação de UID e falsificação posterior.
- `.github/workflows/chimera-build70-phase-dd-full-ancestry.yml` — testes host para Ubuntu e macOS, checagem dos hard stops da Build70 e compilação cruzada de um **objeto ARM64 com iOS 12.0 como target mínimo**, sem binário de helper distribuível.

### Regras do auditor

1. O `config_base` é **exclusivamente uma configuração do harness** (não é enviado pelo app). Exige string absoluta, no máximo 1024 bytes, componentes de até 255 bytes; rejeita `.`, `..`, componentes vazios, `//` e barra final. **Não** utiliza `realpath` nem reescreve o caminho por symlinks.
2. Inicia pelo `open("/")` e percorre todos os componentes por `openat(parent, component, O_NOFOLLOW|O_DIRECTORY|O_CLOEXEC)`. Conferência `fstat` × `fstatat` reduz substituições triviais entre nome e FD, mas **não garante permanência após retorno**.
3. Diretórios ancestrais só são aceitos no **laboratório host** se pertencem ao UID 0 ou ao EUID do processo observador, e não admitem escrita por grupo/outros (inclusive o caso world-writable com sticky bit, como `/tmp`). Esta é **uma política conservadora experimental**; o app com o mesmo EUID ainda pode trocar diretórios seus.
4. As subpastas fixas `wr-dd-private/state` devem ter dono EUID da inspeção e modo **exato 0700**.
5. O lock fixo `wr-da-review.lock` exige arquivo regular, dono EUID, tamanho zero, modo exato **0600**, um único hardlink e concordância nome↔inode no momento da consulta.
6. Se existir **qualquer objeto** no nome `wr-da-check.pending`, retorna `WR_DD_QUARANTINED`, sem abrir ou seguir o objeto. Se faltar marcador e a cadeia for aceitável, retorna `WR_DD_HOST_METADATA_REVIEWED`, **não** autorização.
7. `claimed_client_uid` é um número de laboratório, não uma credencial do kernel. Rejeita 0 e UID igual ao EUID do auditor, mas um cliente malicioso poderia alegar um UID fictício — portanto a própria estrutura deixa `ios12_client_identity_proven=false`.

O recibo `WR_DD_Receipt` mantém **false** para `ios12_client_identity_proven`, `ios12_helper_identity_proven`, `ios12_app_write_access_denied`, `independently_protected_storage_attested`, `powerloss_or_rollback_safe`, `post_review_immutability_proven`, `editor_signature_trusted`, `owner_consent_verified`, `installation_authorized` e `installation_performed`. Nenhum valor computado pelo host altera essas travas.

## 3. Testes e contraexemplos

Os cenários de teste incluem: auditoria positiva apenas de metadados, marcador legítimo/partial/vazio/corrompido, symlink ou diretório como marcador, symlink em ancestral **antes da âncora**, anchor symlink, subdiretórios symlink, lock symlink/hardlink, modos de diretórios ou lock inadequados, lock com bytes inesperados, UID declarado igual ao do helper, UID alegado arbitrário e pathname com `../` ou `//`.

Dois contraexemplos impedem promover o resultado:
- **Mesmo UID apaga marcador depois da inspeção**. A próxima leitura volta a parecer limpa. Isso demonstra que auditar metadados não substitui um serviço com posse realmente independente.
- **Mesmo UID troca um ancestral depois da inspeção**. A nova árvore, com modos aparentemente corretos, também produz uma observação limpa. Sem isolamento real contra o app e reabertura/consumo sob custódia, uma validação `O_NOFOLLOW` não basta.

Os testes operam somente sobre diretórios sintéticos, sem tocar dados do iPad, biblioteca, backups ou releases. Diretórios world-writable e group-writable são rejeitados mesmo quando os diretórios finais usam 0700.

## 4. Limites específicos de iOS12/Chimera

- Não existe helper persistente instalado, `launchd`, socket, UID de helper físico, assinatura de serviço ou entitlements verificados. A Fase DC tem apenas um diagnóstico de `getuid/geteuid/getgid/getegid` do próprio processo, que não identifica o peer.
- O resultado `LOCAL_PEERTOKEN=TOKEN_UNAVAILABLE AUTHORIZATION=DENIED` de testes físicos prévios continua obrigatório; nenhuma alegação de UID em um frame `WRCHK2\n` pode servir como autenticação.
- iOS 12 pode possuir detalhes diferentes de sandbox, FS APFS e permissões. Compilar uma função POSIX para ARM64/iOS12 **não prova que o sistema autorizará ou isolará o futuro helper**.
- O teste percorre um pathname em um instante e fecha todos os FDs depois. Isso não prova que um arquivo revisado será o mesmo consumido pelo `LSApplicationWorkspace` ou `installd`. A revisão do `appinst` upstream mostrou a possibilidade de segunda cópia por pathname; a compatibilidade do binário instalado no iPad não foi medida.
- Mesmo uma identidade de helper diferente não prova proteção contra ações de root, rollback de estado, reinícios de serviço não supervisionados ou alterações posteriores de diretórios confiados.
- O fluxo editorial production-v2, fingerprint público conferido fora do chat, consentimento real do proprietário e proteção do arquivo até instalação continuam **gates independentes**. Não existe `install` habilitado.

## 5. Decisão e próxima etapa

Usar o resultado como **inventário técnico do que ainda precisa ser comprovado**, não como mecanismo de atualização. O próximo experimento que realmente pode reduzir a incerteza é um diagnóstico físico **somente leitura e sob aprovação**, comparando o UID efetivo e a capacidade de acesso a um diretório protegido real de um *helper independente*. O teste deverá ser isolado dos diretórios de WebReader e MangaReader12 e não terá nenhum acesso de escrita a IPAs, biblioteca, favoritos ou dados offline. Ainda assim, o diagnóstico não autorizará instalar automaticamente.

Uma arquitetura de helper final exige: caminho fixo controlado pelo serviço, processo/entitlements isolados do app, reconciliação do journal sem reset por cliente, limites globais, publisher-pin verdadeiro, origem fixa, SHA-256 e code seal da IPA, consentimento individual, assinatura editorial e provas do consumidor Apple. Não substituir essas provas por uma bateria de CI.

**Travas:** `WebReaderAppinstSocket.liveInstallationEnabled=false`, `WebReaderUpdateChannel.productionPublicKeyX963=nil`, `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. Nenhuma publicação de IPA/DEB/Release ou instalação na DD.

**CI DD:** preencher somente após consultar jobs e logs finais Linux/macOS/cross-compile. Não afirmar sucesso sem observação.
