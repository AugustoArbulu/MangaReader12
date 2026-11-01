# R2-A — acompanhamento supervisionado de mudanças no Keiyoushi

Data: 2026-11-01. Complementa docs/HANDOFF_ROADMAP_MANGAREADER12_2026-11-01.md.

## Implementação

- Workflow: .github/workflows/keiyoushi-upstream.yml
- Programa: ci/monitor_keiyoushi_upstream.py
- Referência de commits: ci/keiyoushi-upstream-baseline.json
- Testes offline: ci/test_monitor_keiyoushi_upstream.py
- Execução semanal: segunda-feira às 07:17 UTC, no melhor esforço do GitHub.
- Execução manual: Actions > Review Keiyoushi upstream changes > Run workflow.

O programa consulta exclusivamente commits públicos da API oficial do GitHub
para nove fontes selecionadas e três motores compartilhados. Compara o commit
mais recente em cada diretório com a referência fixa. Gera dois relatórios:
keiyoushi-upstream-report.md e keiyoushi-upstream-report.json, publicados no
resumo do job e em artifact retido por 30 dias.

## Fluxo de revisão humana

1. Abra o workflow, pelo menu Actions do repositório.
2. Consulte o último resumo/artefato, ou execute manualmente.
3. Veja as linhas status = review: houve commit após o snapshot.
4. Leia o diff do commit upstream, inclusive componentes compartilhados.
5. Decida se a mudança impacta nosso adapter JS; se não impactar, documente.
6. Se precisar de port: criar branch, atualizar JS + versão/hash do catálogo,
   adicionar teste offline, PR, CI verde, squash merge. Validar no iOS12.
7. Só atualize o baseline após examinar mudanças. CI nunca regrava baseline.

## Fontes monitoradas

Comix; Asura Scans; Webtoons; Vortex Scans; MadaraDex; HotComics;
Manhwa18.net; ToonGod; Manhwa18.cc; Iken; Madara; YiiMadara.

## Limites de segurança e garantia

- Token do Actions limitado a contents: read, usado para API pública do
  GitHub; erros não imprimem token, headers ou conteúdo remoto.
- Não faz requests a páginas dos sites, não usa WebView nem integra scripts
  Android, não faz requests ao Comix e não tenta contornar 403/429.
- Não altera fontes, manifests, scripts, APK, iOS build ou branch main.
- Um commit diferente exige revisão; não prova regressão. Um commit igual
  não demonstra que a fonte ainda funciona.
- Escopo inclui apenas os diretórios listados, não todos os componentes do
  repositório upstream. Mudanças globais não estão cobertas por garantia.
- GitHub cron é oportunista; a execução manual continua disponível.
- Se a API falhar, o relatório marca error e o job falha em vez de inventar
  ausência de alterações.

## Baseline funcional

O aplicativo fisicamente confirmado segue Build36 + Webtoons EN 0.1.7.
Build37 + Webtoons EN 0.1.8 exige teste real no iPhone.
O monitor R2-A altera somente CI/docs e não requer novo IPA.
