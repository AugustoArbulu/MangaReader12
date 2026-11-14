# WebReader Build69 — Decisão para a primeira IPA privada de QA (não é autorização)

**09/11/2026 — estado técnico após as fases AC–CA**

- Branch de trabalho: `feat/chimera-updater-phase1-protocol-audit`; PR #90 **Draft**, sem merge na `main`.
- Build 68 no iPad iOS 12.5.8 preservada; biblioteca e downloads não foram tocados por testes host.
- Nenhuma IPA real Build 69 foi produzida, distribuída ou instalada. Trust root editorial de produção não provisionado; instalação automática Chimera desativada.
- CI AC–BZ [#42692085242](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42692085242): SUCCESS 2/2 jobs.
- CI AC–CA [#42696114497](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42696114497): consultar conclusão dos dois jobs. O segundo job não pode ser presumido aprovado antes de encerrar.

## Bloqueio real, distinto de funcionalidade do app

Hoje o checkout contém toda a cadeia preparatória: BA (versão e Mach-O iOS12), BN (assinatura ad hoc em cópia descartável), BX (commit revisado e checkout limpo), BY (build isolado de git archive), BK/BL/BZ/CA (empacotamento privado, assinatura, SHA e publicação exclusiva) e BB/BC (auditorias de arquivo original e transferido).

O código da Build 69 **intencionalmente proíbe** empacotamento e upload real no GitHub Actions, inclusive com marcador de consentimento no ambiente. A ferramenta BY/BK está reservada a um macOS pessoal, com autorização específica do proprietário. Portanto, seguir executando CI de compilação unsigned **não produz arquivo instalável**.

## Caminhos técnicos possíveis após decisão explícita do proprietário

### A. macOS local (política implementada atualmente)

No Mac controlado pelo proprietário, selecionar conscientemente o SHA completo e registrar autorização apenas para **uma candidata Build69 de QA privada**. Executar BY, que prepara fonte isolada do SHA, faz build Release iOS12, chama BK/BL para assinar cópia ad hoc e conferir integridade. BB em seguida confere IPA final e gera recibo. O checksum local e o recibo não autenticam editor; verificar SHA por canal separado após a transferência usando BC. Não executar no CI.

Limitação: exige acesso a Mac e não entrega o arquivo ao usuário automaticamente.

### B. workflow manual no GitHub Actions (AINDA NÃO IMPLEMENTADO/AUTORIZADO)

As Builds 67/68 tiveram workflows de entrega manual de IPAs de teste que compilavam no runner macOS, auditavam código e SHA e forneciam um artifact temporário. Esses precedentes demonstram **viabilidade técnica**, não autorização retroativa para Build69.

Um novo fluxo para Build69 precisaria ser criado somente após decisão de alterar a política atual, com:

1. `workflow_dispatch` manual, nunca push, PR ou agendamento; branch experimental e commit fixo confirmado; check-out somente do SHA autorizado. Um texto de aprovação explícita não substitui autenticação do proprietário.
2. Permissão GitHub somente `contents: read`; sem secrets editoriais, sem repositório de produção e sem integração com Chimera. Runner macOS com Xcode iOS12.
3. Testes Linux/macOS exigidos e compilação real ARM64 com `CURRENT_PROJECT_VERSION=69`, mantendo `project.pbxproj` em 56. O gate atual que bloqueia CI para o empacotamento precisa de **mudança deliberada e revisada**; não passar por cima desse bloqueio.
4. Assinatura ad hoc do aplicativo real e inspeção BB de identidade instalada, Mach-O, Info.plist, ZIP, CodeDirectory/CDHash, SHA-256 em arquivo exato e verificação CA do nome final. Recibos de origem não equivalem a assinatura editorial confiável.
5. Entrega somente de artifact de QA com retenção curta e sem GitHub Release, sem feed de atualização e sem instalação. **Atenção:** este repositório é público; artifacts de GitHub Actions não devem ser tratados como conteúdo estritamente privado sem revisar e confirmar controles de acesso do serviço.
6. Não iniciar entrega se qualquer check falhar; nunca atualizar a `main` ou ativar `liveInstallationEnabled`. Mesmo uma IPA baixável não autoriza instalação automática.

## Checklist obrigatório antes do primeiro upgrade manual

- Exportar `.mr12backup` da Build68 e guardá-lo **fora do iPad**; o backup não inclui as imagens offline.
- Anotar os capítulos antigos realmente concluídos para serem lidos depois **sem Wi-Fi**.
- Conferir origem, SHA-256, identidade, build69, iOS12 e assinatura ad hoc da IPA real.
- Instalar **por cima** da Build68, sem apagar aplicativo, sem reindexar downloads, sem limpar armazenamento e **sem restaurar backup**.
- Executar os **16 testes físicos** previstos no app, incluindo biblioteca, favoritos, progresso, imagens offline antigas, reinício ainda offline, leitor, fontes e controles de atualização.
- Se ocorrer regressão, **não** usar exclusão, reindexação ou restauração para tentar "consertar" sem diagnóstico.

## Decisão pendente

Há uma escolha real, não mais uma fase genérica de programação: **autorizar a geração e disponibilização da primeira IPA privada Build69**, por Mac local ou por novo workflow manual do GitHub Actions. Até a autorização e a adaptação deliberada do caminho escolhido, nenhum artefato instalável deve ser gerado em nome do proprietário. Essa autorização tampouco concede permissão de instalação no iPad, automação Chimera, publicação editorial ou alteração da `main`.

**Handoff:** CI verde de fontes/build não é IPA; IPA assinada ad hoc não é release editorial; integridade em host não é compatibilidade física; backup portátil não guarda capítulos offline.
