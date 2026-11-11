# WebReader — Fase DW: identidade da IPA Build70 ARQUIVADA e comparação com Build71

**11/11/2026.** Branch `feat/chimera-updater-phase1-protocol-audit`; PR #90 Draft. `main` não modificada; nada instalado no iPad; nenhum download offline, favoritado ou progresso do usuário foi aberto ou alterado.

## Evidência histórica REAL recuperada

O GitHub Actions run **42705903886**, de 09/11/2026, produziu o artifact de QA **13713972242**, denominado `WebReader-Build70-OwnerApproved-iOS12-QA-Filza`. Seu prazo de expiração informado é **23/11/2026**. O ZIP de artifact tem seis membros: IPA, checksum, dois relatórios de preflight, proveniência e resumo do packager. O arquivo NÃO é uma GitHub Release pública.

Durante esta fase, os bytes originais da IPA arquivada foram recuperados através da integração do GitHub e inspecionados diretamente em memória (sem instalar ou extrair para o iPad). Resultados reproduzidos:

| Item do artifact original | Valor conferido |
| --- | --- |
| Nome da IPA | `WebReader-Build70-iOS12-adhoc.ipa` |
| Tamanho | **17.845.463 bytes** |
| SHA256 integral da IPA | `526291cc77203c3881e5f3f1c75904e8863dbde3b3bd9df7e1185c3229fb4fc1` |
| Bundle ID do Info.plist embarcado | `com.example.MangaReader12` |
| Build do Info.plist embarcado | **70** |
| iOS mínimo | **12.0** |
| Executável | `MangaReader12` em Mach-O 64-bit ARM64 |
| CodeDirectory/CDHash: 20 bytes de SHA-256 | `e0de7f55a2684da7507c3a862247480bd05c39bd` |
| Entitlement XML real extraído de `LC_CODE_SIGNATURE` | `AR5SFJC432.com.example.MangaReader12.AR5SFJC432` |
| Commit original indicado no recibo | `ae931abb725977a417a1fcb20b79c82af825dd55` |

O hash do CodeDirectory foi recalculado a partir do **blob real do executável** e coincidiu com os valores do recibo histórico. O entitlement foi extraído diretamente da posição assinada no Mach-O, e não apenas copiado do texto do recibo. Isso comprova o conteúdo **desses bytes arquivados**, não a integridade global de todas as páginas do selo, a identidade editorial ou a identidade do aplicativo hoje instalado no iPad. O `codesign --verify` nativo macOS continua sendo uma etapa separada.

## Comparação com a Build71 completa já validada no laboratório

A Fase DV no commit `c75f1b2c44225f9c1dd4dbc32643ebb9b14bdb41` passou Linux/macOS no run **43058925136**. O log Apple registrou a compilação do aplicativo **completo** para ARM64/iOS 12, `codesign` ad hoc e DI/DK/DS sobre uma IPA de Build71 **temporária, já destruída**.

Metadados auditados dessa IPA sombra:
- Build: **71**; Bundle ID: **com.example.MangaReader12**; mínimo iOS: **12.0**; arquitetura ARM64.
- SHA256 da IPA sombra: `b4b4880171e21ea6dbebb2ac877fe2af4849a71885165ac61cd920de96d582d0`, tamanho **17.850.028 bytes**.
- CodeDirectory CDHash: `2f5bfb4a3530b5a0f85d7747f4f73caccb68a75a`.
- `appleAdHocSealVerifiedOnTemporaryFullApp=true`; `phaseDVFullAppDSIntegratedHostOnly=true`.

Os hashes e CDHashes **devem diferir** porque são versões distintas. Correspondência de Bundle ID e entitlement entre Build70 arquivada e Build71 sombra é necessária, mas **não é prova de instalação por cima nem preservação de dados**. A DQ/DO da DV continha somente relatórios sintéticos.

## Novo workflow de revalidação independente macOS

`.github/workflows/chimera-build70-phase-dw-archive-identity.yml` baixa o artifact ORIGINAL do run fixo 42705903886 e repete o preflight nativo `ci/build70_private_qa_ipa_preflight.py` para a Build70. As verificações incluem SHA256 integral dos bytes, `codesign` Apple nativo, Bundle ID, build, mínimo iOS, arm64, CodeDirectory/CDHash e entitlement; compara o resultado com os dois recibos originais e o manifesto de proveniência.

O job Linux executa **7 testes estáticos** em `ci/test_build70_dw_archive_identity_contract.py`, incluindo a ausência de upload, Release, comandos de instalação ou permissões de escrita. Nenhuma IPA é anexada ao workflow ou publicada. Os resultados de macOS precisam ser conferidos antes de marcar a DW como aprovada.

Como o artifact original tem expiração, o workflow executa na mudança dos arquivos da DW e é invocável manualmente, mas não em todo commit. Falha futura por expiração não deve ser interpretada como falha de compatibilidade da Build71.

## Bloqueio físico permanece

A Build70 arquivada no GitHub não é necessariamente a mesma instância do código hoje instalado no iPad. O usuário pode ter instalado exatamente essa IPA, outra assinatura, ou ter ocorrido modificações posteriores; sem inspecionar o bundle físico, **não declarar equivalência instalada**.

Um teste privado Build71 futuro ainda requer observação da identidade do aplicativo instalado (Fase DQ, procedimento somente leitura), backup externo adequado, consentimento específico, validação do pacote final e teste dos mesmos capítulos offline antes/depois. O backup `.mr12backup` não inclui imagens e sua restauração pode apagar downloads. Não restaurar automaticamente.

**Travas:** `productionPublicKeyX963=nil`; `independentlyProvisionedSPKISHA256=nil`; `liveInstallationEnabled=false`.
