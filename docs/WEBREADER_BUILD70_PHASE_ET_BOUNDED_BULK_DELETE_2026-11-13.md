# WebReader — Fase ET: exclusão em lote limitada a capítulos registrados
Data: 13/11/2026 · PR #90 Draft · sem acesso ao iPad iOS 12.5.8

## Risco concreto corrigido

A opção `Dados e armazenamento → Apagar todos os downloads` já exigia consentimento destrutivo e informava que `.mr12backup` não inclui imagens. Porém, `StorageManager.clearAllDownloads()` removia **recursivamente todo o diretório `Downloads`** via `FileManager.removeItem`, recriava-o e zerava a tabela SQLite. Essa rota **ignorava** as barreiras de colisão de caminhos (EQ), diretórios inesperados (ER) e procedência de plano/recibo (ES) aplicadas a capítulos individuais. Arquivos órfãos, antigos ou sem representação no banco poderiam ser apagados como se fossem do app.

## Solução ET

`StorageManager.clearAllDownloads()` não chama mais `fileManager.removeItem(at: downloadsDirectory())` nem `DownloadRepository.clearAll()`. Após o consentimento já existente, ela delega à instância compartilhada `ChapterDownloadManager.defaultManager().removeAllConfirmed()`.

`removeAllConfirmed()` é serializada na mesma `worker` dos downloads individuais:
1. Rejeita operação se houver job em execução, entrada pendente, linha `queued/downloading`, uma chave ambígua ou conflito de caminhos. Somente linhas `completed/failed/paused` são candidatas.
2. Inspeciona **todos os registros** e suas pastas antes da primeira remoção, usando os mesmos IDs exatos e o `WebReaderOfflineDeletionPreflight.inspect` das Fases ER/ES. Qualquer arquivo especial, plano estrangeiro, recibo inválido, subpasta estranha ou alias bloqueia o lote inteiro nesse momento.
3. Confirma que todos os jobs do gerente têm linha correspondente no SQLite. Antes de remover cada capítulo, repete a inspeção para recusar mudanças observáveis.
4. Remove **somente o diretório daquele capítulo validado**, seguido da sua linha SQLite e da finalização do job pausado. **Nunca remove a raiz `Downloads`, pasta de outra origem, pasta órfã nem conteúdo não reconhecido.** Pais vazios podem continuar presentes. Caso uma pasta do capítulo já não exista, remove apenas seu registro.
5. Se ocorrer erro de E/S/SQLite durante a fase de remoção, o processo para e informa erro. **Não há transação atômica entre arquivos e SQLite**: algumas entradas anteriores podem ter sido removidas. A UI informa explicitamente essa possibilidade, além de preservar as advertências de backup e confirmação.

A expressão “Apagar todos” passa a referir-se somente aos *capítulos registrados e seguros*. O usuário ainda pode gerenciar downloads individualmente. Se houver conteúdos desconhecidos, a operação nunca os remove silenciosamente.

## Validação host-only

`ci/test_build70_et_safe_bulk_deletion.py` verifica os contratos de segurança e, em macOS, compila **o código Swift real de `removeAllConfirmed`** com uma implementação sintética de banco/gerente e sentinelas descartáveis. Testa falha de preflight numa segunda pasta antes de apagar a primeira, lote com duas entradas legítimas, arquivo órfão que permanece, download ativo, fila pendente, colisão de IDs e base vazia. A ferramenta usa mock apenas para fornecer os veredictos de diretório; os verificadores ER/ES já são compilados e executados em fixtures separadas.

Integração: a regressão Linux/macOS EA–ET e a etapa de build iOS12 `.github/workflows/build.yml`. Não chamar `appinst` nem o iPad; nenhuma IPA Build71 de produção criada.

## Limites e próximo gate

A coleta de linhas, o exame de pastas e a exclusão ocorrem sob a fila do `ChapterDownloadManager`, não como uma transação ACID do filesystem. Um processo externo ainda pode modificar arquivos entre a inspeção e a remoção (TOCTOU) e um erro no meio da sequência não pode desfazer páginas já apagadas. Não afirmar “backup integral” nem “instalação segura” só porque um teste host passou. Antes de atualizar o app físico, obter duas cópias completas verificáveis do contêiner (SQLite, WAL, downloads completos/parciais, preferências e histórico) e comprovar leitura sem rede do mesmo capítulo, sob aprovação expressa.

**Travas:** PR #90 Draft; `main` não modificada; `WebReaderAppinstSocket.liveInstallationEnabled=false`, chave de produção nil, SPKI independente nil, gatilho proprietário Build71 ausente; sem instalação, restauração, acesso físico ou exclusão de conteúdo real do iPad.
