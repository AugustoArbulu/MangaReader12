# WebReader Build70 — Fase EK: confronto do plano de retomada com páginas parciais

13/11/2026 UTC. PR #90 Draft na branch feat/chimera-updater-phase1-protocol-audit. **Somente host, somente leitura.** Nenhum iPad é contatado, nenhuma restauração/remoção/instalação é executada, nenhuma IPA71 é gerada.

## Lacuna identificada

EI inventaria arquivos completos, parciais, órfãos e diretórios vazios. EJ verifica os metadados em _download-plan.json. Porém um plano com 3 páginas e uma pasta contendo page-00000.bin e page-00002.bin pode passar por ambas. O aplicativo real WebReaderOfflineResumePrefix.count() exige um prefixo contínuo começando em page-00000.bin para retomar; só aceita páginas regulares, não vazias, e no máximo 20 MiB cada, com máximo de 5.000 páginas no plano.

## Implementação

- ci/build70_ek_partial_prefix_metadata.py — sobre uma cópia EXTERNA previamente extraída do data container, lê o banco SQLite vinculado ao hash EA/ED e obtém todos os downloads não completos. Invoca EI para recusar arquivos ou diretórios órfãos e não classificados; valida o plano de recuperação com as verificações de metadados EJ.
- Com os índices previstos pelo plano, examina SOMENTE metadados dos arquivos na pasta de capítulo: nomes page-00000.bin, page-00001.bin, etc.; tamanhos, regularidade, quantidade e sequência, usando abertura do diretório por descritor e sem seguir symlinks. Nunca abre, decodifica, corrige, substitui ou renumera as imagens.
- Identifica separadamente páginas vazias ou maiores que 20 MiB, índices fora do plano, páginas após uma lacuna e arquivos extras no diretório que não correspondem ao padrão. Confronta apenas os arquivos com índice menor que o número de páginas declaradas por um plano estruturalmente plausível.
- Um download pausado com páginas suficientes ainda recebe EK_STOP_PARTIAL_PREFIX_NEEDS_IOS12_READING e saída 2: a presença dos arquivos não prova decodificação ou retomada no iPad.
- Planos ausentes ou incorretos, diretórios faltantes, páginas inválidas ou arquivos extras geram EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW e saída 2, com contagens agregadas; nenhuma tentativa de reparo.
- Para um download failed sem plano de retomada, o arquivo de plano é OPCIONAL conforme EJ. Os arquivos, caso existam, são marcados como unverifiedPageFilesWithoutPlan, não como páginas comprovadamente fora de sequência. Essa distinção evita inferir uma corrupção inexistente. A situação continua bloqueante para atualização não assistida.
- Um banco sem trabalhos incompletos pode produzir EK_NO_INCOMPLETE_DOWNLOAD_ROWS_NOT_DEVICE_PROOF (exit 0 informativo), mas nem isso nem qualquer auditoria anterior atesta origem física ou autoriza instalar IPA.

Os relatórios não imprimem títulos, IDs, nomes de arquivos, URLs, cabeçalhos ou conteúdo das imagens. A verificação é conservadora: a ausência de irregularidades detectadas no material COPIADO não comprova que ele foi obtido integralmente do iPad.

## Testes

ci/test_build70_ek_partial_prefix_metadata.py usa fixtures sintéticos com downloads paused, failed e queued, incluindo páginas esparsas, somente page-00002, páginas vazias ou grandes demais, páginas além do plano, metadados inválidos, recibos residuais, diretório desaparecido, symlinks, arquivos órfãos e ausência legítima de plano em job failed. O workflow .github/workflows/chimera-build70-phase-ek-partial-prefix.yml executa regressões EA, ED, EI, EJ e EK no Linux/macOS com validações explícitas das flags de instalação e confiança desabilitadas.

**Não declarar que a fase passou sem verificar logs dos jobs.** Nenhum teste usa dados do iPad.

## Principal risco do upgrade

O .mr12backup é um backup portátil sanitizado: elimina downloads da cópia do SQLite, redefine chapters.downloaded e NÃO inclui page-*.bin. Sua restauração real substitui o banco e remove Downloads. Não usar esse restore como etapa da futura atualização por cima.

Para eventual Build71 final, será indispensável primeiro verificar a identidade do app físico instalado, conservar uma cópia externa coerente de TODO o contêiner com capítulos completos/parciais e metadados, testar o mesmo capítulo offline sem Wi-Fi e obter duas autorizações específicas: uma para entregar a IPA privada e outra para instalar. Trigger ci/build71_owner_approved_qa_trigger.txt ausente; publisher key nil, SPKI pin nil, liveInstallationEnabled=false. Sem merge na main.
