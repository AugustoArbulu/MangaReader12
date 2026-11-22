# WebReader / MangaReader12 — Build 66: auditoria de assinatura e identidade
Data: 2026-11-07 (UTC)
Branch exclusiva: `feat/chimera-updater-phase1-protocol-audit`
PR: #90 (Draft; base `main`, não mesclar)

## Status efetivamente verificado

A Build 65 permanece a versão instalada/aprovada no iPad com iOS 12.5.8. Nenhuma IPA foi instalada por esta investigação. A interface/ponte de instalação continuam fail-closed (`liveInstallationEnabled = false`). A chave pública de updates de produção segue **ausente** (`productionPublicKeyX963 = nil`).

Foram criadas verificações apenas de host:

- `ci/build66_ipa_preflight.py`: verifica SHA-256, tamanho, ZIP e metadata sob um único descritor aberto com `O_NOFOLLOW`; o snapshot verificado pode ser retornado somente para QA explícito.
- `ci/build66_signed_release_preflight.py`: valida envelope ECDSA P-256/SHA-256 com chave de teste fixada pelo consumidor e vincula os campos assinados aos mesmos bytes e metadados da IPA; sem I/O de instalação.
- `ci/build66_code_signature_gate.py`: em macOS, inspeciona **esse mesmo snapshot**, extrai em diretório temporário isolado, executa `/usr/bin/codesign --verify` e lê os entitlements assinados. Exige exatamente o `application-identifier` observado no aplicativo instalado e um executável Mach-O **thin ARM64**.
- `ci/test_build66_code_signature_gate.py`: testes macOS com aplicativos fictícios e assinatura ad hoc feita com ferramentas locais; rejeitam ausências de assinatura, assinatura adulterada, entitlement divergente/adicional, CPU x86-64, manifesto errado e arquivo modificado.
- `ci/audit_build65_signed_artifact.py`: confronta o arquivo real da QA Build 65 com o SHA-256 aprovado, o entitlement da instalação, `codesign` e a arquitetura, sem instalação.

### Identidade do aplicativo preservada

- Bundle: `com.example.MangaReader12`.
- `application-identifier` da instalação existente: `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`.
- Binário: `MangaReader12`, Mach-O thin ARM64.
- Referência Build65 QA no GitHub: execução `42263333598`; artefato `13526372276` (`WebReader-Build65-OfflineRepair-ManualQA-iOS12`).
- SHA-256 da IPA Build65 aprovada: `798d2bc9472e626eea9dd9c794fb7d6053b4eac01d288e86d0f04a3c092af10a`.

## Resultados registrados no GitHub Actions

1. `WebReader Build66 IPA Preflight Security QA`, run `42332283426` (#31): **success**, incluindo testes de assinatura ad hoc em macOS.
2. `WebReader Build66 IPA Preflight Security QA`, run `42332475358` (#34): **success**, após a integração dos testes adicionais ARM64.
3. `WebReader Build65 Archived IPA Identity Crosscheck`, run `42332475367` (#3): **success**. A IPA REAL arquivada foi baixada dentro do GitHub Actions e sua auditoria confirmou: SHA-256 fixado igual, `codesign` válido, entitlement esperado igual, ARM64 correto. Relatório explicitou `installationAuthorized=false`, `installationPerformed=false`, `deviceInstallTested=false`, `publisherAuthenticatedByAdHocSignature=false`.

## Limitações deliberadas e bloqueadores

- Uma **assinatura ad hoc** valida a integridade do código e entitlements, mas **não atesta** a identidade do autor/publicador. O manifesto de release assinado só terá confiança de produção quando existir chave pública fixada de origem confiável e chave privada protegida pelo proprietário. Não adicionar chaves privadas ao repositório.
- O workflow macOS usa binários de testes compilados para macOS; isso NÃO demonstra execução/instalação em iOS. A auditoria separada da Build65 real verifica a IPA real previamente aprovada, não uma Build66.
- O contrato do manifesto v1 aceita somente assets de nome `WebReader-iOS12-unsigned.ipa`, enquanto a Build65 real distribuída para QA se chama `WebReader-Build65-iOS12-adhoc.ipa`. Esta incompatibilidade deve ser resolvida deliberadamente e com testes sincronizados entre os validadores Swift/Python, antes de distribuir updates por manifesto. Não renomear arquivos nem relaxar URL/política silenciosamente.
- Uma resposta `PING/PONG`, o pareamento HMAC e a validação de SHA-256 no cliente NÃO autenticam o peer/solicitante de um instalador privilegiado. Não reutilizar serviço diagnóstico como canal root de instalação.
- A validação do arquivo no host não substitui a autenticação do helper que fará a operação, consentimento one-shot na UI, proteção contra replay/downgrade, autorização de origem, ou uso de bytes imutáveis durante a própria instalação. O nome da IPA ou o Bundle ID isolados não são provas de origem.
- Nenhuma distribuição automática, novo `appinst`, `main` ou Build66 instalável deve ser habilitada nesta fase.

## Próxima etapa segura

1. Definir e revisar um contrato de asset **versionado** para IPA destinada à atualização, com chave pública release pinada por um procedimento confiável, sem revelar segredos.
2. Fazer testes contra assinaturas divergentes, entitlements inesperados e deriva do contrato entre Swift e Python.
3. Projetar helper com autenticação independente do cliente e verificação da IPA exata que será instalada; continuar com instalador desativado até auditoria concluída.
4. Só então avaliar uma IPA manual QA e eventual teste supervisionado no iPad, garantindo a preservação da biblioteca e dos downloads já funcionais na Build65.

**Não há nova IPA para baixar nesta fase.**
