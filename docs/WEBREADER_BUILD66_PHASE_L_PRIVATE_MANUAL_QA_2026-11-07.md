# WebReader Build66 — Fase L: candidato manual para Filza entregue e verificado

**Data:** 2026-11-07 UTC  
**Branch:** feat/chimera-updater-phase1-protocol-audit  
**PR:** [#90](https://github.com/AugustoArbulu/MangaReader12/pull/90), Draft, sem merge na main.

## Resultado final

A **Build66 para QA manual** está disponível como artifact privado de GitHub Actions, **não** como GitHub Release nem atualização automática.

- Workflow: [WebReader Build66 PRIVATE Manual IPA QA Candidate — No Install](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42351270670)
- Run: **42351270670**, tentativa **2**; resultado **SUCCESS**.
- Commit de código compilado: **0939a5d7a480b2daa18d5a653a8ecf69f305f013**.
- Artifact: **WebReader-Build66-Private-ManualQA-Filza-iOS12**
- Artifact ID: **13565424419**, armazenamento privado com retenção de 14 dias.
- IPA: **WebReader-Build66-iOS12-adhoc.ipa**.
- Tamanho da IPA: **17.760.332 bytes**.
- SHA-256 auditado: **49ce402e6efba0aaad891d811e3b76bb78d02b627b5b8ad4fb2e8563aed51afd**.
- Bundle ID: **com.example.MangaReader12**.
- Versão dentro do Info.plist: **66**, mínimo iOS **12.0**, arquitetura **ARM64**.
- Entitlement de compatibilidade: **AR5SFJC432.com.example.MangaReader12.AR5SFJC432**.
- Identidade de publisher assinada independentemente: **NÃO** (ad hoc); instalação de produção: **NÃO**.
- InstallationAuthorized/InstallationPerformed: ambos **false**.

### O que há dentro do artifact

1. WebReader-Build66-iOS12-adhoc.ipa
2. WebReader-Build66-iOS12-adhoc.ipa.sha256
3. WebReader-Build66-private-rehearsal-audit.json
4. WebReader-Build66-private-manual-qa-delivery.json
5. docs/WEBREADER_BUILD66_MANUAL_QA_CHECKLIST_2026-11-07.md

O checksum foi confirmado **depois** do download do ZIP do GitHub Actions; o arquivo IPA foi extraído em um ambiente isolado e teve seu SHA-256 recalculado, idêntico ao sidecar e aos dois JSONs. O Info.plist dentro do arquivo foi analisado independentemente, com build 66, bundle correto e iOS mínimo 12.0.

### Testes concluídos no macOS Actions

- Testes de atualização assinada sintética, leitor offline, mensagens de interface, exportação manual.
- Testes de rejeição de release com nome/URL ambígua, verificador de IPA e canal de instalação inativo.
- Testes de artefato manipulado, checksum errado, nome antigo/forjado, symlink e tentativa de autorização incorreta.
- Compilação **Debug** e **Release** completas para ARM64 iOS12, ambas sucesso.
- Empacotamento usando somente cópia temporária do .app: versão no projeto-fonte ainda era 56, versão na IPA copiada e assinada passa a 66; não altera a Build65 instalada.
- Verificação da integridade ad-hoc usando codesign nativo, entitlement igual ao do app aprovado, SHA-256 e checagem estrutural.
- Segundo gate confere novamente bytes exatos da IPA, .sha256 e relatório JSON antes da entrega.
- Nenhum cliente appinst, daemon privilegiado, token de produção, instalação no iPad ou publicação em GitHub Releases.

A primeira tentativa desse workflow chegou à conclusão de todos os gates e falhou **exclusivamente** no upload de artefatos: cinco timeouts do serviço externo de ArtifactService/CreateArtifact. A segunda tentativa **SUCCESS** conseguiu completar upload. Não foi uma falha de compilação, assinatura ou política de segurança.

## Referência para backup e recuperação

A Build65 anteriormente aprovada ainda tem referência privada:
[GitHub Actions #42263333598](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42263333598),
artifact WebReader-Build65-OfflineRepair-ManualQA-iOS12, ID 13526372276.
SHA-256 do IPA Build65 previamente aprovado:
798d2bc9472e626eea9dd9c794fb7d6053b4eac01d288e86d0f04a3c092af10a.

O artifact da Build65 foi verificado como **não expirado** no início desta fase, mas
**não substitui backup externo da biblioteca**. Downgrade da Build66 para a
Build65 pode ser perigoso se existirem migrações de banco de dados; não garantir
rollback automático.

O checklist completo do teste manual está em:
[WEBREADER_BUILD66_MANUAL_QA_CHECKLIST_2026-11-07.md](WEBREADER_BUILD66_MANUAL_QA_CHECKLIST_2026-11-07.md).

## Próxima ação depende de decisão do proprietário

**Agora sim há uma IPA para baixar e transferir manualmente**. Antes de tentar
instalação pelo Filza, o proprietário deve exportar o backup do WebReader,
copiá-lo para outro aparelho, verificar checksum e optar explicitamente por
instalar por cima, sem apagar o aplicativo nem seus dados. A CI **não testa a
instalação no iPad**, e o match de entitlement é necessário mas não suficiente.

Depois do QA físico: registrar se abertura, biblioteca, capítulos offline,
versão dinâmica em Ajustes, WeebCentral/Webtoons EN e consulta a releases
funcionam. Qualquer erro ao instalar ou possível perda de dados deve
interromper o teste antes de tentar reinstalar/desinstalar.

**Status:** código e IPA de QA construídos e auditados; arquivo entregue
somente em artifact privado; Build65 no iPad intocada; branch main preservada;
PR #90 Draft; instalação automática desativada e sem chave editorial de produção.
