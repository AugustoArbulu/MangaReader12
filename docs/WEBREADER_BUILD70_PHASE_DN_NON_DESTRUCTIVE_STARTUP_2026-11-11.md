# WebReader Build70 — Fase DN: bloqueio conservador de operações destrutivas na inicialização e na atualização

**Data:** 11/11/2026. Repositório `AugustoArbulu/MangaReader12`, branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. `main` não foi alterada e a Build70 instalada no iPad iOS12.5.8 (biblioteca, favoritos, progresso e downloads offline) permaneceu intocada.

## Entrada — Fase DM validada

**DM terminou SUCCESS 2/2** em https://github.com/AugustoArbulu/MangaReader12/actions/runs/42954878260. A CI Linux aprovou 17 testes DM, 21 DJ e 16 DK; o macOS Xcode16.4 aprovou 17 testes e **compilou/executou código Swift real de produção** da `SQLiteDatabase`, `OfflineDownloadPath`, `WebReaderOfflinePageInventory` e `WebReaderOfflineCompletionReceipt` contra banco e páginas artificiais em diretório temporário. Fechar/reabrir o schema v1 preservou valores da biblioteca fictícia, favoritos, progresso de leitura, histórico, localização histórica registrada e bytes das duas páginas. O recibo de duas páginas rejeitou a ausência da última. **Não houve IPA ou upgrade físico.**

## Motivo da DN

Mesmo com o SQLite e o inventário funcionando após reabertura, uma mudança futura no código da UI poderia executar, no lançamento do aplicativo ou na abertura da tela de atualizações, uma manutenção destrutiva. Há funções legítimas e perigosas que **não devem ser acionadas automaticamente**:

- `BackupManager.restoreBackup` substitui a base e chama `clearExcludedDownloadFiles()` — **restaurar .mr12backup remove Downloads offline**, pois os arquivos de imagem não fazem parte do backup;
- `StorageManager.reindexDownloads` pode eliminar registros de capítulos que pareçam ausentes em caminhos antigos;
- `StorageManager.clearAllDownloads` elimina imagens e registros offline.

Essas funções permanecem disponíveis, mas somente por ação consciente na interface de dados/backup e após confirmação explícita. A DN não altera o comportamento da Build70 nem adiciona código Swift novo; cria uma regra de regressão **conservadora e somente leitura** sobre esses caminhos.

## Implementação

Novos arquivos:
- `ci/build70_dn_startup_data_guard.py` — auditoria estática restrita aos corpos do `AppDelegate.application(...didFinishLaunching...)`, `MainTabBarController.viewDidLoad`, `WebReaderAppUpdatesViewController.viewDidLoad/viewDidAppear`, `DataStorageViewController.viewDidLoad/viewWillAppear` e `BackupViewController.viewDidLoad`. Rejeita chamadas diretas a `restoreBackup`, `clearAllDownloads`, `reindexDownloads`, exclusões de arquivos e rotinas de instalação. Verifica `inspectReleaseCache(cleanup: false)`: abrir atualizações não pode limpar automaticamente caches parciais.
- Além dos sete trechos de inicialização/entrada, exige que o backup continue protegido por `UIDocumentPicker` e alerta destrutivo `Restaurar e apagar downloads`; reindexação e apagamento completo também devem continuar atrás de avisos explícitos. Verifica que o comportamento destrutivo do **núcleo** ainda é reconhecido e documentado, para impedir alterações silenciosas nesses fluxos sem nova revisão.
- `ci/test_build70_dn_startup_data_guard.py` — 16 testes com cópias temporárias de fontes Swift e mutações adversariais: inserir exclusão no lançamento, restauração no `viewDidLoad`, transformar inspeção `cleanup:false` em `true`, trocar ação destrutiva por ação padrão, alterar o texto de aviso ao usuário, remover guarda de pin/public key ou ativar `liveInstallationEnabled`.
- Workflow `.github/workflows/chimera-build70-phase-dn-startup-data-guard.yml` — a mesma suíte nos runners Linux e macOS, além de testes de fonte da DM. Somente leitura; nenhum iPad, IPA, codesign, instalação ou arquivo privado envolvido.

**Alcance exato:** este é um **guard de código-fonte em um conjunto fechado de métodos**, não um analisador formal de fluxo de dados ou uma prova de execução do aplicativo inteiro. Ele detecta alterações diretas nessas rotinas, mas não pode demonstrar que métodos chamados indiretamente por outras classes jamais alteram dados. Uma mudança no formato das funções ou nos textos de confirmação faz o guard falhar fechado para revisão. A afirmação `runtimeInvocationGraphProven` permanece **false**.

## Efeitos sobre o QA da Build71

DN impede que mudanças óbvias e diretas sejam promovidas sem revisão, mas não certifica a preservação física do contêiner. Antes da futura instalação manual de uma Build71 privada, ainda será preciso verificar identidade real e assinatura da Build70 no iPad, consentimento para preparar/distribuir IPA, SHA/CDHash final, backup fora do dispositivo e leitura de capítulo baixado antes da atualização com Wi-Fi desligado. Depois, comparar os nove contadores DJ, biblioteca/favoritos/progresso e abrir/reabrir o mesmo capítulo **offline**. Não utilizar `restoreBackup` como rollback automático: apaga downloads.

**Proibição contínua de instalação automática:** `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, `liveInstallationEnabled=false`. O teste não cria pacote, editor confiável, helper autenticado ou consentimento; os campos `readyToDistributePrivateIPA`, `installationAuthorized` e `installationPerformed` são sempre **false**.

**CI DN:** consultar o resultado dos jobs antes de declarar a fase aprovada. Nenhuma das observações de host certifica o iOS12/Chimera físico.
