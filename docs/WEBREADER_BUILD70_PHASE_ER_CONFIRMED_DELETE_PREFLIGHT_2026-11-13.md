# WebReader — Fase ER: auditoria de segurança antes de exclusão confirmada
Data: 13/11/2026 · branch de trabalho PR #90 (Draft) · sem operação no iPad

## Falha de segurança observada

O método `ChapterDownloadManager.remove()` já exigia confirmação destrutiva pela UI e, desde a Fase EQ, verificava a identidade única da pasta no SQLite. Porém, em seguida executava `FileManager.removeItem(at: current)`, **recursivamente**, sem examinar todos os itens da pasta. Se algum arquivo inesperado, subpasta de outro usuário, link simbólico ou metadado de diagnóstico ocupasse esse local, a confirmação para remover um capítulo poderia apagar conteúdo de outra origem.

A correção deve ser conservadora: não apaga arquivos inesperados, nem tenta "limpar" a pasta antes da exclusão.

## Implementação

`WebReaderOfflineDeletionPreflight.inspect` usa apenas `lstat`, `open` com `O_NOFOLLOW`, `fstat`, `fstatat(AT_SYMLINK_NOFOLLOW)` e listagem de nomes. A inspeção aceita somente:
- Diretório real do capítulo e seus quatro ancestrais imediatos esperados (manga, fonte, Downloads, MangaReader12), sem symlinks;
- Até 99.999 arquivos de páginas regulares e com link-count 1, nome exato `page-NNNNN.bin`, com tamanho maior que zero e no máximo 20 MiB;
- Plano `_download-plan.json` regular até 16 MiB e recibo `.webreader-completion-v1` regular até 64 bytes;
- Pasta vazia genuína.

Qualquer arquivo desconhecido, diretório aninhado, symlink, hardlink, arquivo especial, página sem dados, tamanho excessivo ou alteração observável da identidade do diretório durante a inspeção resulta em `.unsafe` e em `ChapterDownloadError.unsafeOfflineDeletionContents`, com mensagem em português e **nenhuma exclusão**.

`ChapterDownloadManager.remove()` executa as checagens da EQ **antes** de chamar o auditor ER; verifica a pasta **antes de alterar a fila ou o SQLite**. Só executa `removeItem(at: current)` se o veredicto for `.allowed`. Se a pasta estiver ausente, continua sendo possível remover apenas o registro SQLite correspondente à identidade exata e não ambígua, sem tocar no filesystem. A confirmação destrutiva existente na UI permanece obrigatória. Uma falha durante a remoção não retira antecipadamente o job da fila.

## Validação host, sem arquivos reais

`ci/test_build70_er_deletion_preflight.py` tem 6 testes: contratos estáticos para tipo dos arquivos, ordenação das guardas, tratamento de pasta ausente, manutenção da confirmação UIKit, preservação EQ e um teste **nativo Swift/Darwin** com pastas totalmente sintéticas cobrindo recibo/plano/página legítimos, pasta vazia, arquivo estranho, temporário, subpasta, symlink do capítulo, symlink ancestral, hardlink, arquivo vazio, índice inválido e página grande. O teste não apaga páginas do iPad; arquivos de fixture são descartados pelo runner.

Integrado ao workflow EA–ER Ubuntu/macOS e ao build geral de iOS 12. A Fase ER não necessita distribuir IPA nem ativar o updater.

## Limites e travas

A inspeção é feita **antes** da chamada recursiva `FileManager.removeItem` e por isso não fornece atomicidade perfeita contra substituições concorrentes/maliciosas no filesystem. O gerente serializa apenas operações de sua própria instância; não é prova contra alterações de outro processo durante essa janela. Guardas recusam dados não reconhecidos, mas a proteção integral segue exigindo cópias externas completas e verificadas da Build70.

`main` não deve ser alterada; PR #90 permanece Draft. `liveInstallationEnabled=false`, SPKI de produção ausente, chave pública de produção nil, gatilho `ci/build71_owner_approved_qa_trigger.txt` ausente. Não executar `appinst`, restaurar `.mr12backup`, instalar/gerar Build71 ou alterar dados do iPad. Antes de qualquer atualização real: verificar cópias independentes do contêiner, ler o mesmo capítulo offline no iPad e solicitar autorização distinta para distribuição e instalação.
