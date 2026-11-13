# WebReader Build70 — Fase EI: inventário de TODOS os downloads da cópia externa

**Data:** 12/11/2026–13/11/2026 UTC. **PR #90:** Draft na branch feat/chimera-updater-phase1-protocol-audit; main inalterada. Executa só no computador com diretório de dados já copiado, não acessa iPad, não restaura, não escreve, não move, não remove e não instala IPA.

## Problema concreto

A Fase EA verifica exclusivamente páginas dos capítulos marcados downloads.state=completed, associando registros ao SQLite e aos recibos. A EC inventaria/hasha arquivos do contêiner inteiro, mas não distingue quais pertencem a downloads em andamento ou estão órfãos. No aplicativo, ChapterDownloadManager.swift mantém uma pasta para trabalhos queued, downloading, paused e failed, incluindo page-*.bin já recebidos e o arquivo _download-plan.json para recuperação. Essas páginas parciais e metadados de retomada são dados que não devem ser descartados em uma atualização.

Um diretório com páginas e nenhum registro em downloads também pode ter valor: pode representar material legado, registros inconsistentes ou sobras de sessão. NÃO apagá-lo automaticamente e NÃO assumir que é seguro restaurar .mr12backup sobre ele.

## Implementação

- ci/build70_ei_all_downloads_inventory.py: recebe --snapshot com a raiz do data container EXTERNO já extraído. A EA confere previamente a estrutura e os bytes dos capítulos completos; o SQLite é desserializado em memória usando o hash da EA.
- O EI obtém TODOS os registros de downloads, não apenas completed, reconstruindo os diretórios esperados a partir de source_id, source_manga_id e source_chapter_id com a mesma aproximação de sanitização usada na EA. A camada de varredura percorre Downloads em descritores de diretório com O_NOFOLLOW, recusa symlinks, FIFO, hardlinks de arquivos, árvores excessivas e alterações detectáveis em metadados.
- A auditoria inventaria os arquivos regulares presentes em Downloads, inclusive _download-plan.json, recibos, páginas, arquivos ocultos e material adicional. Classifica quantidades e bytes de: diretórios associados a linhas completas, linhas não completas (pausadas, falhas, em fila, interrompidas), pastas de capítulo sem registro associado e arquivos em profundidade inesperada. Nomes, IDs, URLs e caminhos privados NÃO são impressos.
- Ao encontrar conteúdo de pastas sem registro ou arquivos em local não classificado, retorna EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES e exit code 2. Quando há trabalho incompleto mas todos os arquivos estão associados a registros, retorna EI_NONCOMPLETED_DOWNLOADS_OR_UNICODE_REQUIRE_OWNER_REVIEW: isso **não é falha do aplicativo** nem comprova que os arquivos parciais foram protegidos fisicamente. Colisões de caminho sanitizado envolvendo qualquer estado também são bloqueadas, diferentemente da EA, que só precisava comparar capítulos completos.
- Dados completos, não completos e órfãos devem permanecer intocados mesmo se o status for STOP. O EI nunca grava novas linhas, não faz normalização do SQLite e não elimina pastas ou capítulos.
- Testes: ci/test_build70_ei_all_downloads_inventory.py, somente fixtures; workflow Linux/macOS em .github/workflows/chimera-build70-phase-ei-all-downloads.yml.

## Limites

Esta fase é um inventário de metadados (tamanhos, caminhos internos para classificação) e não lê integralmente o conteúdo dos arquivos de downloads NÃO completos. A EA já lê/hashia os capítulos completos, enquanto EC pode comparar conteúdo de duas cópias externas; nenhuma delas atesta os bytes do iPad. Uma pasta vazia sem registro pode não ser classificada como pasta de capítulo com arquivos. A presença de arquivos parciais não garante retomada, legibilidade de imagem, plano válido ou consistência do snapshot físico.

A sanitização de identificadores Unicode por Python pode divergir de Foundation, portanto o auditor sinaliza IDs Unicode para revisão, sem tratar hash local como prova de origem. Valores de current path no banco podem conter UUIDs antigos; a ferramenta NÃO segue local_path e utiliza apenas os caminhos derivados dos IDs.

## Uso futuro — opcional e ainda não realizado

python3 ci/build70_ei_all_downloads_inventory.py --snapshot "/copia-externa-do-data-container"

O caminho é ilustrativo. Nenhum dado privado do iPad foi recebido. Nunca enviar arquivos SQLite, páginas, chaves, preferências ou relatórios sensíveis ao GitHub.

O backup portátil .mr12backup apaga downloads da cópia SQLite e NÃO contém páginas. Restaurar o .mr12backup substitui o banco vivo e remove Downloads; não fazer isso como parte de atualização. Antes de um teste físico da Build71, guardar uma cópia EXTERNA consistente do contêiner de DADOS completo, incluindo o material de downloads parciais, planos, fontes, preferências e SQLite. A validação física e a instalação exigem autorizações posteriores separadas.

Trigger ci/build71_owner_approved_qa_trigger.txt permanece ausente; productionPublicKeyX963=nil, independentlyProvisionedSPKISHA256=nil e liveInstallationEnabled=false. Nenhum resultado EI permite distribuir IPA, restaurar, instalar ou ativar o updater. Só declarar aprovação Linux/macOS após os respectivos logs concluídos.
