# WebReader Build69 — fases BR, BS e BT: planos de recuperação atômicos e preservação de downloads

**Data:** 2026-11-09 (UTC). **Repositório:** `AugustoArbulu/MangaReader12`. **Branch exclusiva:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft.** Nunca mesclar ou alterar `main` sem autorização; Build68 continua instalada e aprovada no iPad iOS12.5.8. Nenhuma IPA Build69 privada foi produzida/instalada/publicada nesta fase. O instalador Chimera e o trust root editorial real continuam desativados.

## Base conhecida antes desta rodada

A [CI AC–BQ #42572758345](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42572758345) passou **SUCCESS nos 2/2 jobs**: testes Linux, testes Swift reais no macOS, Xcode Debug/Release ARM64/iOS12, preview unsigned Build69 e assinatura ad hoc **apenas** de uma cópia temporária do aplicativo real. A preview não é uma IPA, não cria release, não comprova preservação dos dados físicos e não altera a Build68 instalada. Consultar também o [handoff BO–BQ](WEBREADER_BUILD69_PHASES_BO_BP_BQ_OFFLINE_RECOVERY_2026-11-09.md).

A fase BQ já lia `_download-plan.json` com um FD `O_NOFOLLOW|O_NONBLOCK`, limitando a **16 MiB** e comparando `fstat` antes/depois. Contudo, a escrita em `ChapterDownloadManager.savePlan` ainda usava `Data.write(options:.atomic)` sem impor o mesmo limite. Se a fila recebesse um plano demasiado grande, o app podia salvar um arquivo que ele próprio recusaria após reiniciar.

## BR — gravação bounded + atômica dos planos privados de recuperação

Novo `MangaReader12/Downloads/WebReaderOfflineRecoveryPlanWriter.swift`, compilado no target iOS12 (PBX ID 49). A função `write(data:to:)`:

1. Exige JSON já codificado **não vazio**, tamanho **até 16 MiB** idêntico à BQ e basename exato `_download-plan.json`.
2. Abre o diretório existente com `O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC`, verifica com `fstat` e só admite destino inexistente ou arquivo regular com `fstatat(...AT_SYMLINK_NOFOLLOW)`. Rejeita links simbólicos, FIFOs, diretórios e arquivos especiais no caminho final.
3. Cria um arquivo `*.tmp` privativo e exclusivo no mesmo diretório usando `openat` e `O_EXCL|O_NOFOLLOW` com **permissões 0600**. Grava exatamente os bytes em loop que suporta escrita parcial/EINTR; `fsync` conclui antes da publicação.
4. Mantém o comportamento de proteção de arquivos iOS da implementação anterior (`completeUntilFirstUserAuthentication` quando suportado). Reconfere a segurança do caminho e faz **renameat atômico** para trocar um plano normal já existente quando o usuário prioriza um capítulo na fila.
5. Em falhas **antes** do rename, limpa **somente** o `*.tmp` desta tentativa; o arquivo original e as páginas offline permanecem intactos. A rotina não faz network, remove diretórios de capítulos, altera banco SQLite ou chama o instalador.

`ChapterDownloadManager.savePlan` chama o novo writer tanto para a fila inicial quanto para Prioritize. O leitor BQ permanece inalterado e compatível com planos existentes. **Limite:** as garantias de FD e `fstatat` reduzem risco, mas não constituem uma prova formal de inexistência de uma corrida local contra substituição maliciosa do caminho entre a última verificação e `renameat`. O diretório permanece restrito ao contêiner privado do app.

### Testes BR

`ci/test_native_webreader_offline_recovery_plan_writer.py` compila **ambos** reader/writer Swift num macOS com pasta temporária, exercita leitura/escrita, substituição do plano após priorização, modo POSIX 0600, limite 16MiB+1, dados vazios, basename inesperado, link simbólico, diretório no lugar do arquivo, caminho de diretório symlink e limpeza de `*.tmp`. Verifica que o conteúdo anterior permanece se uma escrita inválida falha.

`ci/test_build69_br_atomic_recovery_plan_writer_policy.py` verifica integração no Xcode, limite único BQ/BR, escrita regular privada com `renameat` apenas após `fsync`, proteção de destino, ausência de invocação `appinst` e integração com ambas as chamadas de `savePlan` existentes.

## BS — limitar 5.000 páginas antes de mexer na pasta do capítulo

O formato recuperável admite até **5.000** páginas por capítulo (regra BO/BQ na restauração), mas o caminho inicial `download()` aceitava arbitrariamente mais. Agora o limite é conferido **antes** de entrar na worker queue, consultar diretórios, apagar arquivos de uma tentativa fracassada ou criar uma nova pasta. Uma segunda validação dentro de `savePlan` impede que um futuro caller contorne o gate.

Se exceder esse limite, a conclusão do download retorna `ChapterDownloadError.tooManyPages` com uma mensagem compreensível. **Não houve alteração no conteúdo da biblioteca e nenhum arquivo é tocado nesta rejeição.**

Teste `ci/test_build69_bs_bounded_download_admission.py`: verifica a ordem página-limite → fila → filesystem, a segunda verificação antes do `JSONEncoder` e o texto de erro.

## BT — impedir que um novo toque apague um capítulo já completo

O caminho de retry em `ChapterDownloadManager.download()` removia recursivamente o diretório local quando já existia, antes de criar uma pasta para reiniciar. Se o registro estivesse `state='completed'`, um segundo toque em Baixar poderia eliminar um capítulo offline **aprovado na Build68**, inclusive as imagens que o `.mr12backup` não contém.

Agora, antes de `removeItem(at:directory)`, a função consulta `DownloadRepository.record` e **recusa** um segundo download quando o registro do capítulo já está `completed`. O erro localizado orienta a remoção **explícita e consciente** do item na área Downloads se a pessoa realmente desejar baixar novamente. Não apaga nem restaura automaticamente.

**Escopo importante:** isso protege capítulos **com registro `completed`** contra um re-download acidental. Para um download incompleto (`failed`) cuja pessoa escolha reiniciar, o fluxo de retry anterior ainda reinicia a pasta, excluindo os arquivos parciais anteriores; isso não deve ser descrito como backup ou preservação irrestrita de todos os dados. A fase atual não promete consertar capítulos corruptos automaticamente. A remoção manual explícita permanece disponível na interface.

Teste `ci/test_build69_bt_completed_download_retention.py`: exige que a consulta do registro completo anteceda qualquer remoção, verifica o erro e preserva o caminho manual de remover.

## Validação integrada

Workflow `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml` renomeado **AC–BT**, com três suites estáticas novas no Linux e teste BR Swift real adicionado ao job macOS. Também roda toda a bateria anterior (AC–BQ), Xcode Debug/Release ARM64 iOS12, preview unsigned versionada 69 e assinatura ad hoc **de uma cópia descartável do WebReader real**, sem criar IPA.

[GitHub Actions AC–BT #42574421076](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42574421076). **CI consolidada concluída: SUCCESS nos 2/2 jobs** (Linux e macOS). A primeira execução encontrou apenas uma chamada de função auxiliar com rótulo ausente no teste Swift; o teste foi corrigido. A execução final aprovou testes Swift reais, segurança Linux, Xcode Debug/Release ARM64 iOS12, preview unsigned Build69 e assinatura ad hoc efêmera do WebReader real. Nenhuma IPA foi produzida. Execuções antigas podem aparecer canceladas automaticamente por `cancel-in-progress`.

## Critério para a futura IPA privada

Nenhuma IPA Build69 foi produzida nesta etapa; o empacotador BK/BL permanece bloqueado por aprovação explícita e não é executado no GitHub Actions. O plano de confiança editorial P-256 não foi provisionado e `liveInstallationEnabled=false` continua. A Build68 instalada e seus downloads reais não foram alterados.

Quando houver aprovação específica para a candidata privada, auditar identidade/entitlements/SHA/ZIP e a transferência PC→Filza com BB/BC, instalar **por cima sem desinstalar**, comparar a biblioteca com o backup portátil e fazer os 16 checks físicos. Um `.mr12backup` não preserva as imagens offline; restaurá-lo no meio da QA apagaria Downloads.
