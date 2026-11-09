# WebReader — Build 69 Fase AZ: continuidade de dados, backup e QA físico

**Data da engenharia:** 2026-11-09 UTC.  
**Branch de desenvolvimento:** `feat/chimera-updater-phase1-protocol-audit`; [PR #90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). **Nunca publicar/mergear `main` sem autorização expressa do proprietário.**

**Baseline físico aprovado:** Build 68 no iPad iOS 12.5.8, biblioteca e leitura offline previamente aprovadas; SHA-256 do artefato de referência `fb8263573a5b46a94bab74f91c2a25b08de6aa9ac327f078339f1ff77ae5d841`, commit de referência `605f607b08d714d8eabfd3270516b77dfaf673e0`. Não reinstalar/remover essa build durante a engenharia. A árvore de código ainda usa `CURRENT_PROJECT_VERSION=56` como valor histórico de compilação e **não** deve ser descrita como uma Build 69 instalável. Não há IPA Build 69 distribuída.

## Resultado anterior confirmado

O workflow AC–AY [#42550113510](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42550113510) concluiu **SUCCESS** nos 2/2 jobs (Linux offline e macOS testes Swift/compilação iOS12). Nenhuma IPA final foi publicada.

## Achado crítico de produto: backup portátil não guarda capítulos offline

`MangaReader12/Core/BackupManager.swift` tem dois caminhos distintos:

- **Criar arquivo `.mr12backup`**: copia a biblioteca SQLite e um subconjunto de preferências; a cópia portátil executa `sanitizePortableSnapshot`, `DELETE FROM downloads` e `UPDATE chapters SET downloaded = 0`. Nenhuma página/imagem de capítulos entra no arquivo de backup.
- **Restaurar arquivo `.mr12backup`**: substitui o banco SQLite, restaura preferências e chama `clearExcludedDownloadFiles`, que **remove a pasta `Application Support/MangaReader12/Downloads` inteira** antes de recriá-la. Portanto, restaurar um backup pode eliminar os capítulos offline atuais.
- **Atualizar IPA por cima do mesmo aplicativo, mesma identidade instalada**: fluxo separado do backup; a continuidade dos dados depende de instalação in-place e de teste real no iPad. O código atual mantém `SQLiteDatabase.currentSchemaVersion=1` e `BackupManager.formatVersion=1`. Isso é um indício favorável, não é garantia de preservação física.

**Nunca tratar `Restaurar backup` como uma etapa automática da atualização.** Em caso de problema após instalar uma candidata, parar; não apagar o app ou restaurar indiscriminadamente porque os capítulos offline não estão no `.mr12backup`.

## Alterações implementadas nesta fase

1. **Confirmação de perda de dados antes da restauração:** `MangaReader12/UI/BackupViewController.swift` agora, após escolher um arquivo, exige confirmação explícita `Restaurar e apagar downloads` (ação `.destructive`), oferece `Cancelar` e só então chama `manager.restoreBackup(from: url)`. Estado `restoreConfirmationPending` impede duplicidade de seleção. A lista de backups passa a avisar que arquivos offline não estão inclusos.
2. **Instruções corretas de Filza:** `MangaReader12/UI/WebReaderAppUpdatesViewController.swift` recomenda exportar o backup da biblioteca para outro dispositivo, **não desinstalar a versão atual** e não restaurar por padrão. O aviso afirma explicitamente que o backup não preserva páginas offline.
3. **Roteiro de QA física ampliado:** `WebReaderPhysicalQAChecklist.swift` agora tem **14 perguntas manuais**, todas `[SIM/NÃO/NÃO TESTADO]`, incluindo instalação por cima, fechamento/reabertura offline e não restauração acidental. O relatório é copiável, sem rede, sem leitura do conteúdo pessoal.
4. **Regressões de consentimento e compatibilidade:** `ci/test_build69_az_backup_restore_consent.py` valida a sequência de confirmação real; `ci/test_build69_az_persisted_library_sqlite.py` executa **o SQL extraído diretamente de `SQLiteDatabase.schemaV1`** em banco SQLite temporário, cria registros sintéticos de biblioteca, capítulos, leitura, categorias, histórico e downloads, reabre e confere que nada se altera. **Teste de host, não iOS físico.**
5. **CI ampliado:** `.github/workflows/chimera-build69-phase-ac-af-integrated-qa.yml` integra os dois novos testes Linux, a atualização do teste Swift de QA física, `ci/test_build53_backup_pins.py` (backup antigo/pins), e `ci/test_build65_offline_relocation.py` (páginas locais após mudança de contêiner). Compila ARM64/iOS12 Debug e Release **sem produzir IPA**.

## Critérios do próximo QA no iPad

**Antes de qualquer IPA candidata:** exportar backup da Build68 para Android/PC; anotar 2–3 obras já baixadas em cada fonte e seu progresso de leitura; manter a Build68 instalada e com espaço livre suficiente. O arquivo exportado contém apenas biblioteca e preferências, não cópia das imagens offline.

**Durante:** conferir SHA-256 e identidade de bundle/entitlements de **uma IPA nova e aprovada**; instalação manual **por cima**, sem `Uninstall` e sem chamar `Restaurar backup`; não executar appinst via WebReader. O proprietário decide quando instalar.

**Depois, com Wi-Fi DESLIGADO:** abrir pelo menos 3 capítulos já baixados, rolar todas as páginas e conferir se o progresso está preservado. Fechar completamente e reabrir o aplicativo ainda offline, revalidando os mesmos capítulos. Depois conferir categorias, obras fixadas, histórico, escala do leitor, filtros e comportamento das fontes quando voltar à rede.

**Se qualquer check falhar:** registrar mensagem/Build sem copiar dados privados ou paths pessoais; **não** limpar biblioteca, não desinstalar, não restaurar backup automaticamente. A Build68 permanece a baseline conhecida.

## Gates que continuam fechados

| Item | Resultado |
| --- | --- |
| Código de segurança e testes AC–AY | CI anterior 2/2 SUCCESS |
| CI de estabilização AC–AZ | [Execução #42551945366](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42551945366) iniciada; resultado a verificar |
| QA física da próxima Build69 no iPad | **NÃO TESTADA** |
| Geração da IPA de teste privada da Build69 | **NÃO AUTORIZADA/NÃO EMITIDA** |
| Chave privada de release e pin SPKI independente | **NÃO PROVISIONADOS** |
| Canal production v2 no aplicativo | **DESATIVADO** |
| Merge `main`, GitHub Release público, upload de IPA | **NÃO EXECUTADOS** |
| Instalação direta por Chimera | **BLOQUEADA** (`liveInstallationEnabled=false`) |

O CI verifica invariantes técnicos e não é evidência de preservação física ou permissão para publicar. A PR #90 deve permanecer **Draft**. A Build68 não foi alterada.

## Próxima etapa recomendada

Concluir AC–AZ e, com o resultado verde, preparar critérios para **uma candidata QA de Build69 com versionamento correto, identidade idêntica e distribuição privada sob aprovação explícita**. Evitar ativar canal de produção antes de concluir custódia editorial da chave; não ligar automaticamente instalador Chimera.
