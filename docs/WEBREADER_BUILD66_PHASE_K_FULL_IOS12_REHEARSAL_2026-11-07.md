# WebReader Build66 — Fase K: compilação completa iOS12 e ensaio de IPA sem publicação

**Data:** 2026-11-07 UTC
**Branch:** feat/chimera-updater-phase1-protocol-audit
**PR:** [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90), Draft, sem merge na main.
**App em uso:** Build65 no iPad com Chimera; biblioteca e leitura offline previamente aprovadas.

## Resultado auditável

O workflow [WebReader Build66 Full iOS12 Compile and Private QA Audit — run #42349950938](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42349950938)
terminou em **SUCCESS** no commit d4143879e7a85a3417ac4c34cdae78a92556004a.

A execução não usou o iPad, não fez instalações e não publicou uma IPA. Testou:
- Bloqueio de instalação no Swift, chave editorial de produção ausente, validação de metadados GitHub e staging manual.
- Testes offline de biblioteca/atualizador, incluindo 15 cenários de recusa de artefatos, links simbólicos, SHA-256 incorreto, build antiga e nomes adulterados.
- Ícones oficiais e libwebp compatíveis com iOS12.
- **Compilação Debug de verdade: BUILD SUCCEEDED.**
- **Compilação Release de verdade: BUILD SUCCEEDED.**
- Verificação do bundle original, versão de projeto 56, arquitetura ARM64 e mínimo iOS 12.0.
- Cópia isolada do app compilado, com versão no Info.plist alterada **apenas na cópia** para 66, assinatura ad hoc e entitlements idênticos aos observados no app instalado.
- Auditoria de SHA-256, ZIP, identidade, thin ARM64 e codesign nativo no arquivo da Build66.

### Identidade do pacote interno gerado no runner

- Nome: WebReader-Build66-iOS12-adhoc.ipa
- Build no pacote: 66
- Tamanho: **17.760.100 bytes**
- SHA-256: **3866d4369d860e11fc5732575290ed2a6b48b9cec3cec3d8f7e43570e7357b69**
- Bundle ID: com.example.MangaReader12
- Identificador de entitlement: AR5SFJC432.com.example.MangaReader12.AR5SFJC432
- Arquitetura: thin ARM64
- Versão mínima: iOS 12.0
- Ad-hoc codesign: integridade e entitlement auditados, **não autentica o editor**.
- Compatibilidade de instalação real no iPad: **NÃO testada**.
- Chave de release de produção: **NÃO configurada**.
- Instalação/consentimento do usuário: **NÃO realizado**.

A branch mantém CURRENT_PROJECT_VERSION=56 no projeto-fonte; somente a cópia temporária do bundle de ensaio recebeu a versão 66. O hash é dos bytes gerados naquele runner específico, não de uma publicação e não é uma garantia de futura reprodução byte a byte.

**Artefato de CI:** WebReader-Build66-Private-Compile-Audit-Only, ID 13564678553. Ele contém **somente o relatório JSON**, não a IPA. O workflow não fez upload de qualquer candidato instalável e não criou GitHub Release.

Os campos de auditoria productionPublisherAuthenticated, releaseManifestIndependentlySigned, ios12DeviceInstallTested, userConsentVerified, helperPeerAuthenticated, installationAuthorized, installationPerformed e approvedForAutomaticRelease permaneceram todos **false**.

## Correções incorporadas

1. GitHub Releases pode listar uma IPA v1 com nome legado ou a v2 com nome ad hoc e build explícita; o app rejeita assets duplicados, ambíguos ou de outro repositório.
2. A etapa de download reconhece a convenção v2. Antes, a descoberta poderia indicar v2, mas o staging exigia apenas o nome antigo.
3. O código HTTP 404 vindo de releases/latest agora é erro de acesso, pois um repositório privado pode responder 404; não significa "versão atualizada".
4. Os rótulos da interface informam "Baixar e conferir IPA" e "Compartilhar IPA conferida", distinguindo SHA/ZIP da assinatura editorial independente.
5. O script de ensaio foi construído sem instalador, não aceita root, fixa o nome do pacote e confere os entitlements. Foram corrigidos os argumentos posicionais antes da execução verde.

## Limites que ainda importam

A nova CI executa uma seleção extensa de regressões, mais as duas compilações reais. O workflow histórico "iOS 12 Milestone 0" possui testes adicionais e havia sido cancelado em rodadas com vários commits; **não declarar que todos os seus testes históricos passaram**.

O teste de diagnóstico feito no iPad como mobile mostrou UNIX_PEERTOKEN=UNAVAILABLE e CSOPS_TOKEN_BINDING=NOT_TESTED. Três símbolos específicos do Security.framework não foram localizados. No macOS, o ensaio de mensagens já enfileiradas mostrou que o token depois de recv não atribui criptograficamente a autoria de cada pedido. Não usar isso para autorizar appinst.

A assinatura ad hoc e o match de entitlement são compatibilidade de arquivo, **não prova de quem publicou**. O usuário ainda precisará aprovar uma eventual distribuição de IPA manual e fazer QA físico com backup, sem remover a Build65.

## Próximo marco

Com autorização separada do proprietário, criar uma entrega manual de QA que disponibilize a IPA Build66 e um SHA-256 verificável, sem usar instalação automática. Antes de testar no iPad, confirmar backup da biblioteca e capítulos offline e rota de retorno à Build65. Depois, validar atualização não destrutiva, reabertura da biblioteca, leitura offline e consulta de GitHub Releases.

A instalação automática deverá esperar chave editorial confiável, autorização independente do helper, revalidação dos bytes instalados, limites de privilégio e proteção contra replay e downgrade. Não expor credenciais de um repositório privado dentro do cliente iOS.

**Estado:** Build66 compilou Debug/Release no macOS e seu pacote passou na auditoria host; não há IPA publicada; Build65 continua estável no iPad; main intocada; PR #90 Draft; instalador privilegiado desativado.
