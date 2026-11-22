# WebReader Build70 — Fase DU: consolidação dos gatilhos de CI da PR #90

**11/11/2026.** Branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. `main` inalterada e Build70 iPad intacta. Nenhuma IPA, DEB, release, instalação, migração ou leitura de dados privados.

## Problema documentado

A árvore contém **71 arquivos** em `.github/workflows`. Na amostra dos 100 runs mais recentes de GitHub Actions consultada, **80 estavam em fila** naquele momento; é uma amostra transitória, não evidência de um limite específico de conta nem garantia de que sejam todos jobs macOS. Fases DQ, DR, DS e DT tinham disparadores `push` e `pull_request` simultâneos para a mesma alteração na branch com PR aberta. Isso causava duplicação e adicionava trabalhos supersedidos à fila.

## Correção DU

Os workflows dessas quatro fases agora possuem SOMENTE `pull_request` direcionado a `main` e `workflow_dispatch`; o gatilho `push` da branch foi retirado. Assim, cada commit novo da PR continua produzindo seus checks, mas não uma segunda cópia no evento push.

Cada workflow foi configurado com `concurrency` cujo grupo usa o nome do workflow e o número da PR (ou `github.ref` para execução manual), com `cancel-in-progress: true`. A intenção é manter somente a revisão mais nova de cada fase por PR e cancelar verificações daquela fase referentes a commits anteriores quando uma nova execução for enfileirada. Os grupos são separados entre DQ/DR/DS/DT.

Isso não assegura cancelamento de runs antigos de versões do workflow que não tinham essa regra, não afeta as outras definições de workflow, e não acelera necessariamente a obtenção de runners macOS. Não há alteração de permissões: `contents: read`, sem upload de artifacts nem publish.

## Regressões

`ci/test_build70_du_workflow_queue_contract.py` contém seis testes de contrato: presença dos quatro workflows, ausência de gatilhos push duplicados, presença de `pull_request` e `workflow_dispatch`, `concurrency` latest-only, manutenção de Linux/macOS, preservação do teste macOS nativo DS e manutenção das três travas de produção. Os testes foram anexados ao job da Fase DR.

Esta verificação é **estática**. Ela demonstra a configuração no repositório, não comprova como GitHub Actions escalonará os jobs em produção, não implica que macOS tenha terminado e não é um teste físico do iPad.

## Não alterações

- Nenhum arquivo Swift foi modificado.
- O diagnóstico físico DQ ainda NÃO foi executado no iPad.
- Os testes DR/DS/DT existentes não foram removidos, suprimidos ou transformados em aprovação automática.
- A chave de editor permanece sem provisionamento: `productionPublicKeyX963=nil` e `independentlyProvisionedSPKISHA256=nil`.
- O instalador permanece desabilitado: `liveInstallationEnabled=false`.

Para Build71 ainda faltam identificação da Build70 física, preservação comprovada dos dados reais e downloads offline, IPA final analisada, consentimento explícito e teste manual por cima. Uma prova de CI nunca equivale a um upgrade autorizado.

## Handoff

Revisar os jobs Linux/macOS do commit DU e não declarar aprovação enquanto estiverem `queued`. Após novos commits, observar se há apenas um run novo por fase, disparado por PR, e se revisões antigas pertencentes a novos grupos de concorrência são canceladas. Não interpretar falhas/cancelamentos de runs supersedidos como falha de produto.
