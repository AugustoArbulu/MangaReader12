# WebReader — Build69, fases BH/BI/BJ: páginas offline, auditoria parcial e QA física

**Data:** 2026-11-09 UTC. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; [PR #90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). **Nunca modificar `main` nem a Build68 instalada sem autorização.** Nenhuma IPA Build69 assinada, distribuída ou instalada nesta fase. Produção editorial sem chave e Chimera com instalação desabilitada.

## Base comprovada

[GitHub Actions AC–BG #42564766964](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42564766964) finalizou **SUCCESS em 2/2 jobs** (Linux + macOS nativo/compilação iOS12). As fases BD–BG oferecem a comparação de oito contagens a partir do backup portátil da Build68 e nove contagens no aplicativo Build69, sem ler nomes de obras. O backup `.mr12backup` **não guarda páginas offline**; restaurá-lo apaga `Downloads`.

O código Xcode do app ainda usa `CURRENT_PROJECT_VERSION=56` nas configurações originais; o override `CURRENT_PROJECT_VERSION=69` é aplicado apenas na compilação experimental isolada. Não existe candidato IPA real assinado/fornecido ao proprietário.

## BH — impedir capítulo offline parcialmente lido como completo

**Achado:** em `ChapterDownloadManager.localPages`, uma obra com `downloads.state='completed'` que tivesse apenas arquivos `page-00000.bin` e `page-00002.bin` podia retornar duas páginas sem reconhecer que a página 1 faltava. Um arquivo de zero bytes ou symlink também podia entrar na lista com base no nome. Isso é particularmente problemático após movimentar contêineres, instalações ou downloads interrompidos.

**Implementação:**

- `MangaReader12/Downloads/WebReaderOfflinePageInventory.swift`: lista somente metadados de arquivos de página de um capítulo. Exige diretório real, arquivos regulares não symlink, nome `page-%05d.bin` para cada índice desde 0, sequência sem lacunas, tamanho positivo e limite máximo de 99.999 páginas. Não lê o conteúdo, não faz download, não renomeia, não repara SQLite e **não apaga nenhum arquivo**.
- `ChapterDownloadManager.localPages` agora chama essa validação antes de gerar `Page` ou fazer o antigo `rebindCompletedPath` de localização (que, quando necessário, mantém o comportamento compatível com a mudança de UUID do contêiner do iOS). Se um capítulo marcado `completed` perder o diretório inteiro, retorna erro explícito em vez de `nil` que poderia ser interpretado como não baixado.
- Mensagem `ChapterDownloadError.missingCompletedFiles` em português: informa que uma página está ausente, vazia ou inválida e que arquivos não foram apagados. `DownloadsViewController` também oferece alerta específico **Capítulo offline incompleto**, sem recorrer a restauração automática de backup.
- Limitação importante: **sequência não comprova que a última página do servidor foi salva**, nem prova que cada imagem pode ser decodificada. Ler o capítulo inteiro sem Wi-Fi continua obrigatório.

**Testes:** `ci/test_native_webreader_offline_page_inventory.py` compila Swift real em macOS e exercita três páginas válidas, lacuna no meio, falta de primeira página, arquivo vazio, symlink, diretório mascarado, lixo não relacionado e diretório symlink. `ci/test_build69_bh_offline_reader_policy.py` confere o encadeamento de validação no leitor, antes de qualquer metadado corrigido; nenhum file-delete ou rede. Nenhum dado do usuário é usado.

## BI — diagnóstico presencial de integridade parcial na interface

Nova classe `MangaReader12/Core/WebReaderOfflinePreservationAudit.swift` e nova opção em **Atualizações do WebReader → Segurança → Conferir presença dos capítulos offline**.

- Abre um **SQLite read-only**, valida schema v1, transação consistente e conta downloads `completed`. Consulta até **64 capítulos**, em ordem determinística, juntando IDs de source/manga/chapters **somente internamente** para derivar os caminhos do **contêiner atual** com `OfflineDownloadPath.chapterDirectory`. Nunca segue o antigo `downloads.local_path` persistido em versões anteriores.
- Cada pasta consultada passa pela **mesma validação BH usada pelo leitor**. O relatório contém somente seis totais: registros completos no banco, inspecionados, com sequência de arquivos válida, com arquivos ausentes/incompletos/inseguros, fora da amostra e número de arquivos presentes nessa amostra. Nenhum título, ID, nome de source, caminho, URL, imagem ou preferência é copiado.
- A amostra é **parcial e limitada**; se houver mais que 64 capítulos, o relatório mostra honestamente quantos **não foram avaliados**. Imagens são apenas verificadas por metadados de arquivo (presença, nome, tamanho, tipo). Portanto `arquivos presentes` **não significa** imagens decodificadas ou capítulo completo na origem.
- A execução roda fora da thread principal (`DispatchQueue.global(qos: .utility)`), com bloqueio de toques repetidos e retorno à main thread para clipboard/alerta. Não executa requests, download, migração, exclusão, backup/restore ou `appinst`.
- Banco indisponível ou schema incompatível produz `INDISPONÍVEL`, **não** um falso `0 arquivos`.

**Testes:** `ci/test_native_webreader_offline_preservation_audit.py` utiliza esquema SQLite v1 real com dados e IDs inteiramente fictícios, arquivos de página sintéticos com lacunas e tamanho zero, e 66 downloads para conferir limite de 64 (2 não avaliados). Verifica não divulgação dos identificadores e que a consulta não altera os bytes do banco. `ci/test_build69_bi_offline_audit_policy.py` confere modo read-only, limite, isolamento, UI assíncrona e ausência de install/requests.

## BJ — diagnóstico de erro e QA ampliada sem ações destrutivas

- `DownloadsViewController` apresenta aviso local específico em caso de capítulo incompleto; não tenta resolver o problema restaurando backup ou apagando a pasta.
- `WebReaderPhysicalQAChecklist.swift` passa de 14 para **16 verificações manuais**, acrescentando: a amostra offline não mostra lacunas de arquivo?; os capítulos antigos abrem **integralmente** com Wi-Fi desligado? Cada check permanece **NÃO TESTADO** até o proprietário executá-lo fisicamente.
- `ci/test_build69_bj_offline_corruption_and_qa.py`, `ci/test_native_webreader_physical_qa_checklist.py` e `ci/test_build69_az_backup_restore_consent.py` verificam esses invariantes. Nunca solicitar ao usuário que crie arquivos corrompidos nem corromper downloads reais de propósito.

## CI integrado

Workflow: `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml`, nome **AC–BJ — Offline Reader + Preservation QA iOS12**.

Inclui Linux com testes de todas as fases AC–BJ, backup e políticas fail-closed; macOS com testes Swift reais das novas classes, assinatura ad hoc apenas em fixture sintética, compilação completa Debug/Release ARM64/iOS12 e preview temporário `CFBundleVersion=69` **não assinado e não empacotado em IPA**.

[Execução AC–BJ #42566938982](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42566938982): criada; verificar conclusão final e correções posteriores, se houver. O CI usa `cancel-in-progress: true`: execuções anteriores canceladas não são prova de aprovação.

## Critérios de aprovação da futura IPA

1. **Antes:** exportar `.mr12backup` (privado) da Build68 para PC/Android; obter baseline de oito contagens com BF e anotar **quais capítulos antigos devem ler offline**. Nenhum backup contém as páginas.
2. **Somente depois de autorização específica de candidata privada:** produzir Build69 verdadeira, auditar sua assinatura/identidade/entitlements/CDHash e SHA-256 com BB/BC. Não publicar GitHub Release de produção nem modificar `main`.
3. **Instalação manual por cima, sem desinstalar ou restaurar:** abrir `Atualizações → Segurança`; copiar contagens BD e presença offline BI; verificar 16 checks físicos, inclusive carregar páginas inteiras sem Wi-Fi e reabrir o aplicativo ainda offline.
4. **Falha não significa apagar arquivos:** parar e diagnosticar, não restaurar `.mr12backup` ou limpar `Downloads` automaticamente.

**Permanece bloqueado:** chave editorial P-256 real, provisionamento de trust root, publicação de release assinado, autorização de helper Chimera, instalação privilegiada, merge `main`. Tudo nesta fase é código experimental na PR #90 Draft, preservando a Build68.
