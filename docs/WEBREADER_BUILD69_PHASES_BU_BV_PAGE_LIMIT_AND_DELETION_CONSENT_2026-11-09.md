# WebReader Build69 — Fases BU/BV: limite de imagens e confirmação antes de perder páginas offline

**Data:** 2026-11-09 UTC. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 continua Draft**. A Build68 instalada no iPad iOS12.5.8 e sua biblioteca não foram modificadas; `main` permanece intacta. Nenhuma IPA Build69 foi gerada, publicada, distribuída ou instalada. Helper Chimera e confiança editorial de produção permanecem desativados.

## Base técnica

A [CI AC–BT #42574653681](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42574653681) terminou **SUCCESS nos 2/2 jobs**, incluindo Linux offline, Swift nativo, Xcode Debug/Release ARM64 iOS12, preview isolada unsigned Build69 e assinatura ad hoc apenas de cópia temporária do WebReader real. Não houve geração de IPA.

As fases BR–BT já gravam planos de recuperação em até 16 MiB e impedem que um segundo download de um capítulo marcado `completed` apague automaticamente os arquivos antigos. Entretanto, a revisão identificou dois problemas complementares no tratamento das páginas:

## BU — impedir que uma página recém-salva se torne irrecuperável

**Achado:** `WebReaderOfflineResumePrefix.maximumPageBytes` rejeita páginas locais com mais de **20 MiB** durante a retomada de downloads interrompidos; porém, em `ChapterDownloadManager.performPageRequest`, o download podia aceitar e persistir um corpo maior que esse limite após validar a imagem, criando um capítulo que o próprio sistema de retomada depois recusaria.

**Alteração:** antes de chamar `ChapterDownloadImageValidator.canStore` e antes de `response.data.write(to:destination,options:.atomic)`, a rotina verifica `!response.data.isEmpty` e `Int64(response.data.count) <= WebReaderOfflineResumePrefix.maximumPageBytes`. A mesma constante de 20 MiB passa a ser usada nas duas direções. Em rejeição, sinaliza `ChapterDownloadError.oversizedImagePayload`, sem marcar capítulo como concluído ou sobrescrever arquivo daquela página.

**Limite:** o HTTP client ainda pode ter recebido um corpo maior antes desta etapa; a mudança **limita validação e persistência**, não constitui por si só um limitador de streaming na rede. Arquivos offline de capítulos **já concluídos e legados** não são apagados/revisados por esta alteração.

Teste `ci/test_build69_bu_page_payload_bound.py` exige a ordem de validação de tamanho → validador de imagem → escrita atômica e a ausência de conclusão antecipada.

## BV — consentimento para exclusão e reinício destrutivo

**Achado:** a tela `DownloadsViewController` oferecia duas rotas de exclusão: botão `Remover` e gesto iOS de `commit editingStyle == .delete`. Ambas podiam chamar `manager.remove` sem um alerta explícito sobre a perda de imagens. Além disso, `retryDownload` para `failed` (e `paused` sem sessão recuperável após reiniciar o app) acabava chamando `manager.download`, cujo comportamento atual **limpa a pasta parcial** antes de iniciar uma tentativa nova. O `.mr12backup` não inclui as páginas offline.

**Alteração de interface, sem mudança nos dados:**

- O gesto de exclusão e o botão `Remover` convergem para `confirmRemoveDownload(record)`.
- O alerta informa que a operação **apaga as imagens baixadas** e que o backup portátil não permite recuperá-las. Oferece `Cancelar` e `Apagar download`; só a escolha destrutiva chama a rotina anterior `removeDownload`.
- A rotina real `removeDownload` **reconsulta o estado atual** e continua recusando apagar uma transferência ativa ou em nova tentativa. Não remove nada antes da confirmação.
- `retryDownload` mostra alerta específico informando que reiniciar substituirá páginas parciais e que não estão no backup. Só `Reiniciar download` aciona `beginRetryDownload`, com a checagem de estado existente e a resolução de detalhes/chapters/pages pela fonte. `Cancelar` não faz request nem toca arquivos.
- Um download apenas `paused`, que ainda existe em memória, usa `manager.resume` e **não passa** pelo alerta: retoma preservando os arquivos. Se a sessão não existir mais após reiniciar o app, o fallback `retryDownload` passa agora pelo consentimento, antes de resolver as páginas novamente.
- **Transparência:** um reinício explicitamente confirmado de `failed` ainda pode apagar páginas parciais. Não confundir confirmação com backup ou retomada não destrutiva.

Teste `ci/test_build69_bv_destructive_download_consent.py` verifica as duas rotas de exclusão, botões Cancelar/destrutivo, aviso de backup, consentimento de retry e reconsulta de estados. A validação de compilação real em iOS 12 vem do workflow completo.

## CI e status

Workflow `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml` atualizado para **AC–BV**, incluindo os testes Linux BU/BV e mantendo toda a regressão AC–BT, testes Swift macOS, build Debug/Release ARM64 iOS12, preview unsigned 69 e auditoria ad hoc efêmera **sem produzir IPA**.

[Execução AC–BV #42578090544](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42578090544): checar o resultado final antes de declarar esta rodada aprovada. Nenhum teste local/CI substitui os **16 testes físicos** no iPad.

## Próxima etapa física quando houver aprovação

Uma candidata privada Build69 verdadeira ainda precisa de autorização de empacotamento e distribuição, assinatura ad hoc compatível, preflight final ZIP/entitlements/SHA e conferência da transferência para Filza. Antes de instalar por cima da Build68, exportar `.mr12backup` para outro dispositivo **sem restaurá-lo** e anotar os capítulos completos offline; o backup não leva suas imagens. Após instalar, verificar biblioteca e capítulos antigos **integralmente sem Wi-Fi**, fechar/reabrir ainda offline, e executar o roteiro de 16 verificações.

**Proibido nesta fase:** mesclar `main`, limpar biblioteca, criar Release editorial, provisionar trust root real, ativar `WebReaderAppinstSocket.liveInstallationEnabled` ou instalar IPA no iPad.
