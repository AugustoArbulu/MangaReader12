# WebReader Build70 — Fase DI: preflight privado 70 → 71, somente leitura

**Data:** 10/11/2026 (horário de Brasília); a CI pode ter timestamps em 11/11 UTC. Repositório `AugustoArbulu/MangaReader12`, branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. **Não fazer merge na `main`**. A Build70 continua instalada no iPad com biblioteca, favoritos, progresso e capítulos offline preservados, não modificados.

## Resultado confirmado antes da DI

- **DF:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42927165075 — **SUCCESS 3/3**: Linux 22 testes, macOS fixtures e análise dos **dois executáveis ARM64/iOS12 reais produzidos pelo Xcode16.4**. A lista de imports para o pequeno CLI de identidade aceitou somente `_getgroups` ou a grafia observada `_getgroups$DARWIN_EXTSN`; outros sufixos continuam bloqueados.
- **DH:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42927907053 — **SUCCESS 2/2**: Linux 22 testes negativos + 11 testes de regressão da DG; compilação **Build71 unsigned** com `CURRENT_PROJECT_VERSION=71`, iOS 12 e ARM64 no runner macOS, seguida da verificação de Info.plist, ícone e Mach-O. O aplicativo prévio ficou no RUNNER_TEMP e **nenhuma IPA foi criada, assinada, distribuída ou instalada**.
- DG já tinha **SUCCESS 2/2** no build completo do WebReader com botão de relatório `Darwin.getuid/geteuid/getgid/getegid` do próprio app. **Esse botão ainda não está instalado no iPad.**

Esses resultados não autenticam o futuro helper, não validam uma instalação ad-hoc na Build70 física e não dispensam backup/offline. A tarefa automatizada de monitorar DF/DH foi criada separadamente pelo usuário; não é alterada por esta fase.

## Lacuna que DI aborda

O antigo preflight `ci/build70_private_qa_ipa_preflight.py` exige **Build69 → 70** e o workflow `chimera-build70-owner-approved-one-shot-qa.yml` também mantém uma aprovação histórica específica para **um pacote Build70**. Alterar constantes nesse fluxo introduziria risco de confundir a identidade, checksum e consentimento originais com uma instalação futura. A DI cria **outra função auditora**, fixada no par **Build70 → Build71**, e **não cria workflow de entrega**.

## Código e contrato

- `ci/build70_di_build71_private_qa_preflight.py`: somente leitura. Exige basename `WebReader-Build71-iOS12-adhoc.ipa`, baseline inteiro **exatamente 70** (sem booleanos ou downgrade), checksum fornecido como arquivo externo de uma única linha em formato `sha256<dois espaços>nome\n`, sem maiúsculas nem caminhos extras. **Não autentica a origem do próprio arquivo checksum.**
- Reusa `inspect_ipa(..., require_exact_identity=True, return_snapshot=True)` para abrir **uma vez** o IPA por FD sem seguir symlink, conferir tamanho e SHA-256, contabilizar entradas ZIP e validar caminhos seguros. Usa **os mesmos bytes imutáveis em memória** tanto para conferir o Mach-O ARM64/iOS12/Info.plist quanto para `audit_code_signature_snapshot`.
- Em macOS, a auditoria nativa extrai o snapshot descartável em diretório temporário, chama `codesign --verify` e lê o entitlement efetivamente selado e o CDHash. O `application-identifier` conferido é `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`, valor histórico observado anteriormente no iPad; isso é **necessário, mas não suficiente** para provar compatibilidade com a Build70 atualmente instalada.
- O recibo `DI_SIGNED_QA_SNAPSHOT_HOST_ONLY_NOT_DISTRIBUTABLE` confirma somente integridade dos bytes, arquivo ZIP, Mach-O e assinatura ad-hoc **no host macOS**. Todos os flags `checksumSourceIndependentlyAuthenticated`, `physicalBuild70AppIdentityNewlyAttested`, `actualDeviceInstallabilityProven`, `finalInstallerConsumedSameBytesProven`, `publisherCryptographicallyAuthenticated`, `productionEditorialTrustConfigured`, `liveHelperPeerAuthenticated`, `libraryBackupValidated`, `libraryFavoritesProgressPreservedOnDevice`, `offlineChaptersVerifiedAfterUpgrade`, `ownerQADistributionApprovalRecorded`, `readyForPrivateQADistribution`, `readyForProductionRelease`, `githubReleasePublished`, `automaticUpdaterEnabled`, `installationAuthorized` e `installationPerformed` permanecem **false**.

**Limite importante:** a assinatura ad-hoc confirma a integridade local e o entitlement do bundle assinado, não quem publicou o arquivo, não uma assinatura editorial production-v2, não a autoridade do serviço Apple para instalar e não o consentimento do proprietário. SHA-256 fornecido junto ao pacote também não é prova independente de autenticidade.

## Testes adversariais

- `ci/test_build70_di_build71_private_qa_host.py`: suíte Linux/macOS que testa parsing exato do checksum, nome Build71, baseline exclusivamente 70, downgrade/upgrade, Bundle ID, plist de iOS13, symlink e substituição de arquivo, alteração após SHA, Mach-O de outra arquitetura, recibos adulterados e **um cenário explicitamente simulado de assinatura que ainda deixa todas as permissões de distribuição e instalação false**. Esse teste simulado NÃO é evidência de codesign Apple.
- `ci/test_build70_di_build71_private_qa_native.py`: macOS/Xcode16.4 compila programa ARM64 com minOS 12.0 em **pasta temporária**, assina ad-hoc com entitlement da fixture, gera **somente IPAs sintéticas temporárias** para testar o verificador Apple real e casos negativos: pacote sem assinatura, assinatura alterada, entitlement falso, Mach-O iOS13 disfarçado de plist iOS12, Build70/72 em vez de 71, checksum adulterado e baseline inválido. `TemporaryDirectory` elimina as fixtures após cada teste.
- `.github/workflows/chimera-build70-phase-di-build71-private-qa-preflight.yml`: Ubuntu para os testes host e macOS para os mesmos testes mais `codesign` nativo. **Sem `upload-artifact`, sem GitHub Release, sem IPA real e sem gatilho de instalação.** Os scripts antigas para entrega Build70/69 não foram modificados.

## O que ainda falta antes de QUALQUER QA física

1. Consentimento explícito do proprietário para preparar uma IPA da Build71, já que esta fase deliberadamente NÃO produz o pacote distribuível.
2. Verificar mais uma vez o identificador do aplicativo já instalado na Build70 — o valor em fixture pode não refletir um estado presente no dispositivo.
3. Assinar uma candidata construída a partir de commit congelado; registrar hash/CDHash; auditar o ZIP e bytes finais e verificar origem da transferência, sem publicar como Release editorial confiável.
4. Preservar e comparar biblioteca/favoritos/progresso e os downloads offline, inclusive teste real sem Wi-Fi antes e depois. Não prometer preservação apenas com Bundle ID igual.
5. Ter procedimento de rollback seguro, respeitando a limitação de re-download que apareceu nas builds anteriores.
6. Manter **separados** os requisitos de autenticação do helper, proteção do vault, controle do journal, identidade editorial production-v2 e consentimento local. Nem uma IPA de QA assinada ad-hoc habilitaria automaticamente `appinst`.

**Travas:** `static let productionPublicKeyX963: Data? = nil`; `static let independentlyProvisionedSPKISHA256: String? = nil`; `static let liveInstallationEnabled = false`. PR #90 Draft, `main` e Build70 física intactas.

**CI DI:** registrar resultados somente após a conclusão dos jobs; uma suíte host verde isoladamente não é aprovação para distribuição.
