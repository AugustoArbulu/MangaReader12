# WebReader — Fase DY: entrega privada da Build71 preparada, NÃO acionada

**11/11/2026 — PR #90 Draft, `feat/chimera-updater-phase1-protocol-audit`; `main` preservada.**

## Objetivo e estado atual

As fases DL/DV compilaram o WebReader **completo** Build71 Release ARM64/iOS12 no macOS, ad-hoc assinaram uma cópia efêmera e validaram os bytes temporários por DI/DK/DS. O arquivo foi destruído: nunca houve IPA71 disponível para instalar. As fases DW/DX verificam o artifact histórico real Build70 e preparam a comparação com os metadados do bundle instalado no iPad; esta observação física ainda **não foi executada**.

A DY prepara o próximo passo operacional: um **workflow de entrega de QA privado e de uso único**, que pode produzir e reter por 14 dias o ZIP de artifact Actions contendo **uma Build71 real assinada ad-hoc**, arquivo SHA256 e auditorias. **O workflow não foi disparado**: a própria criação das ferramentas nesta fase não gera IPA, upload ou Release. Não cria automaticamente o gatilho necessário.

## Arquivos implementados

- `ci/build71_owner_approved_actions_qa_package.py`: motor do empacotamento, identidade histórica de instalação, contrato de versão 70→71, assinatura nativa, verificação de bytes finais, relatórios de proveniência e rollback em falha.
- `.github/workflows/chimera-build71-owner-approved-one-shot-qa.yml`: **único gatilho** é push que altera `ci/build71_owner_approved_qa_trigger.txt`. Arquivo deliberadamente **ausente na árvore atual**. Não aceita evento PR nem `workflow_dispatch`.
- `ci/test_build71_dy_owner_approved_qa_contract.py`: 18 testes de host para bloquear execução comum, contexto GitHub falso, branch/repositório diferente, marcador ausente/forjado, symlink, SHA de checkout inconsistente, mudança adicional no commit, hashes e flags elevadas, ausência de app e comandos de instalação.
- `.github/workflows/chimera-build70-phase-dy-build71-delivery-readiness.yml`: roda os testes de segurança em Linux, mais regressões DI/DV, e exige a ausência do marcador. Não gera artifact ou imagem.
- Este documento é o handoff que deve ser lido antes de eventual trigger autorizado.

## Único gatilho possível — só mediante autorização explícita futura

A geração da IPA71 exigiria **uma nova instrução explícita do proprietário** aprovando o preparo e a entrega de **uma** IPA71 para teste manual, sem instalação. Só depois dessa autorização, um commit isolado deve criar `ci/build71_owner_approved_qa_trigger.txt` com **exatamente duas linhas**:

```text
WEBREADER_BUILD71_OWNER_APPROVED_ONE_SHOT_ACTIONS_QA_IPA_NO_INSTALL
<sha40-do-commit-pai-revisado>
```

O workflow também exige:

1. O evento ser `push` na branch exata do projeto, do repositório exato, com `GITHUB_WORKFLOW_REF` e `GITHUB_SHA` coerentes.
2. O commit de trigger alterar **somente** esse arquivo, e a segunda linha coincidir byte a byte com `HEAD^`. O marcador precisa conter exatamente duas linhas ASCII terminadas em LF.
3. `GITHUB_RUN_ATTEMPT=1`: um rerun de um workflow antigo é recusado; uma nova entrega requer um novo gatilho e revisão de autorização.
4. Checkout sem modificações, projeto fonte com `CURRENT_PROJECT_VERSION = 56` como era, e travas de confiança e instalador inalteradas.
5. Compilação da fonte revisada em snapshot temporário com `CURRENT_PROJECT_VERSION=71`, Release ARM64, SDK iPhoneOS e mínimo efetivo iOS12.
6. Assinatura Apple ad hoc temporária com entitlement histórico exato `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`, e verificação `codesign --verify`.
7. Pacote IPA e SHA256 imutável; preflight DI 70→71 sobre os bytes exatos, cruzamento host-only DS com relatórios **fictícios** DQ/SQLite/offline, rehash após cada auditoria e segunda auditoria independente pós-empacotamento.
8. Upload **apenas** de artifact privado do GitHub Actions: `WebReader-Build71-OwnerApproved-iOS12-ManualQA`, retenção 14 dias, com os arquivos `WebReader-Build71-iOS12-adhoc.ipa`, `.sha256`, preflights, proveniência e resumo. Sem publicar Release, update feed, IPA pública, DEB ou executar `appinst`.

**Este marcador é uma medida operacional, NÃO autenticação criptográfica do proprietário.** Um colaborador com acesso de escrita à branch pode forjar um commit. A autorização efetiva deve ser decidida e conferida fora do repositório, na conversa com o proprietário; o assistente não deve inferi-la de `continue` nem de um resultado de CI.

## Diferença importante entre preparar, entregar e instalar

- **Preparar** (estado DY atual): publicar código, workflow e testes na branch. Não é necessário o iPad; nada instalado.
- **Entregar uma IPA71 privada** (futuro, somente com consentimento explícito): executar trigger, gerar artifact via Actions, conferir os hashes/reports finais, disponibilizar um arquivo para o usuário baixar e transferir via Android/Filza. Não implica instalar.
- **Instalar por cima da Build70** (decisão posterior e separada): antes comparar o bundle instalado no iPad por DQ, conferir backup fora do aparelho sem sobrescrever downloads, registrar contagens antes/depois e verificar capítulos existentes sem Wi-Fi. Não desinstalar a Build70 nem restaurar automaticamente o backup `.mr12backup` — este não inclui bytes de páginas offline.
- **Atualização automática** (outro projeto): só após confiança editorial/pinning provisionado independentemente, autenticação da ponte Chimera, auditoria de instalador e QA físico. Não é habilitada pelo artifact manual.

## Não avançar sem estes dados

A Build70 física relatada pelo usuário permanece instalada no iPad com biblioteca, favoritos, progresso e downloads. O artifact histórico Build70 era válido no GitHub, mas não atesta assinatura/entitlement **atualmente instalados**. Os textos DQ são sujeitos a falsificação; mesmo DQ textualmente compatível não garante continuidade de contêiner. Nenhum backup externo completo foi verificado; não concluir preservação a partir de nove contagens SQLite iguais.

As flags Swift seguem:
- `productionPublicKeyX963=nil`
- `independentlyProvisionedSPKISHA256=nil`
- `liveInstallationEnabled=false`

A resposta do packager ainda registra `installationAuthorized=false`, `installationPerformed=false`, `automaticUpdaterEnabled=false`, `ownerIdentityCryptographicallyAuthenticatedByTrigger=false` e `physicalDeviceUpgradeVerified=false`.

## Validação e limites

A CI de prontidão DY não cria IPA; exige que o arquivo de trigger esteja ausente. **Não declarar DY aprovada antes de conferir esse run.** O caminho de assinatura/empacotamento de uma IPA71 real dentro desse novo workflow não foi executado nesta fase — sua validação Apple **deva acontecer na execução autorizada**, utilizando DI/DS nativos. A DV anterior demonstra a capacidade técnica do mesmo projeto de compilar/assinar uma sombra descartável, mas não substitui a auditoria do artifact final.

**Estado final esperado da DY:** pronto para solicitar aprovação específica e executar o gatilho em um turno futuro, não pronto para instalar automaticamente.
