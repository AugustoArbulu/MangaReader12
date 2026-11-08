# WebReader — Fase Q / Build68 experimental: retenção segura do cache de downloads

**Data:** 2026-11-08
**Branch:** feat/chimera-updater-phase1-protocol-audit
**PR:** #90 Draft contra main; **não fazer merge**.
**Checkpoint físico:** Build66 aprovada (iOS 12.5.8); Build67 ainda requer teste físico; Build68 experimental não teve IPA distribuída.
**Escopo:** implementação não privilegiada. Nenhuma instalação/appinst/launchctl, nenhum novo release.

## Motivação

A Fase P gerenciou somente cópias de QA importadas pelo usuário para
Application Support/WebReaderLocalQAImports. O downloader de GitHub Releases,
entretanto, escreve outros arquivos em Application Support/WebReaderUpdates:

- A transferência incompleta tem nome exato \`.webreader-<UUID>.partial\`.
- A IPA final conferida usa \`WebReader-build<N>-<UUID>.ipa\`.

Após fechamento abrupto, downloads incompletos podem permanecer na pasta.
Após exportar manualmente uma IPA final, ela também pode ocupar espaço.
Esses arquivos **não** podem ser removidos por uma varredura da biblioteca
ou por um limpador geral, nem confundidos com a pasta de importação local.

## Implementação

### Núcleo Swift iOS 12

Arquivo: \`MangaReader12/Core/WebReaderIPAStager.swift\`.

Novo \`WebReaderReleaseCacheStorage\`, separado do inventário da Fase P:

- \`isManagedName\`: aceita estritamente as duas gramáticas de nomes criadas
  pelo downloader; rejeita traversal, extensão extra, build zero e arquivos
  alheios. Não interpreta os nomes como prova de autenticidade editorial.
- \`inventory(directory:now:protectedName:)\`: **somente leitura**.
  Sem criar a pasta quando ausente, sem exclusão. Limite de 512 nomes,
  diretório aberto via \`O_DIRECTORY | O_NOFOLLOW\` e arquivos examinados com
  \`fstatat(AT_SYMLINK_NOFOLLOW)\`; permite somente arquivos regulares,
  com um hardlink, até 512 MiB, não modificados **nem** alterados em metadados
  nas últimas 24 horas. Arquivos \`.partial\` de zero bytes são elegíveis,
  desde que antigos. A IPA atual escolhida para compartilhamento é protegida.
- \`discardConfirmed\`: recebe um candidato previamente inventariado e,
  **após confirmação do dono na interface**, compara novamente nome,
  dispositivo, inode, tamanho, mtime/ctime, precisão de nanossegundos,
  idade mínima e exclusão do nome atualmente protegido. Remove apenas por
  \`unlinkat\` dentro da pasta aberta. Se qualquer dado mudou, nega.

As operações não acessam a origem Files/Filza, Downloads de capítulos,
Biblioteca SQLite, banco de dados, backups, outras pastas de QA ou o
instalador Chimera. Não há exclusão automática ao abrir o WebReader.

### Interface

Arquivo: \`MangaReader12/UI/WebReaderAppUpdatesViewController.swift\`.

Duas ações adicionais na seção **IPA LOCAL (ARQUIVOS OU FILZA)**:

1. **Espaço usado por downloads antigos** — conta arquivos elegíveis e MB
   que podem ser recuperados, sem eliminar.
2. **Limpar downloads antigos…** — apresenta uma confirmação destrutiva
   separada, antes de revalidar cada candidato e remover os elegíveis.

O código bloqueia a ação durante download/conferência para exportação,
e protege o nome da IPA atualmente selecionada.

### Limitações explicitadas

- Os arquivos elegíveis incluem cache de uma distribuição GitHub Release,
  cuja procedência **ainda não é autenticada por uma chave editorial de
  produção**. Excluir o cache não significa verificar uma assinatura.
- \`fstatat\` seguido de \`unlinkat\` não é uma transação atômica contra um
  adversário com permissão de escrita na mesma pasta. A operação é
  **não privilegiada**; nunca deve servir como autorização para um helper root.
- A idade usa o relógio do dispositivo, que pode ser ajustado. A confirmação
  permanece obrigatória.
- Limite de 512 nomes: em caso de pasta maior, a inspeção falha
  explicitamente; não ocorre uma limpeza arbitrária.

## Testes adicionados

- \`ci/test_phase_q_release_cache_policy.py\`: verifica controles de interface,
  recusa de instalação, separação dos diretórios, gramática/idade/identidade,
  limite de entradas, confirmação explícita e CI.
- \`ci/test_native_webreader_release_cache_storage.py\`: Swift real em macOS
  usando arquivos sintéticos, sem IPA instalável. Testa pasta ausente, nomes
  válidos/inválidos, retenção de 24h, \`.partial\` vazio, IPA ativa protegida,
  arquivo desconhecido e symlink/hardlink ignorados, substituição de inode,
  ctime alterado, limite de diretório e fonte original intacta.
- \`.github/workflows/chimera-phase-p-qa-storage.yml\` agora inclui as duas
  suítes. Compila app iOS12 Debug e Release, sem gerar IPA.

**Validação:** não marcar a Fase Q como aprovada até verificar a CI do HEAD
com ambas as suítes e a compilação completa. Nenhum teste físico de Build68
foi realizado.

## Linha de confiança — próximos bloqueadores

1. **Chave editorial**: escolher uma chave P-256 de produção, mantê-la fora
   do repositório como chave privada, fixar sua **chave pública** de maneira
   verificável no app e definir procedimento de revogação e rotação. O
   \`productionPublicKeyX963\` permanece \`nil\`. GitHub HTTPS, SHA e
   assinatura ad-hoc não substituem essa prova.
2. **Manifesto**: aceitar somente esquema v2 assinado e compatível com a
   identidade instalada, hash/tamanho exatos e política monotônica
   de builds; verificar novamente o objeto estável que será entregue.
   O laboratório de preflight já existe, mas não há release autenticado
   distribuído ao WebReader.
3. **Chimera**: definir uma identidade de solicitante verificável pelo
   **sistema**, não por alegações do app (PID, UID mobile ou HMAC), além de
   consentimento independente, nonce/antirreplay, isolamento de descritores
   e verificação pelo helper dos mesmos bytes a instalar. Os ensaios com
   \`LOCAL_PEERTOKEN\` no iOS12 ainda não demonstraram autenticação adequada.
   Até resolver, \`WebReaderAppinstSocket.liveInstallationEnabled = false\`.

## Gates de preservação

- Não modificar \`main\`, não integrar PR #90, não gerar Release/IPA Build68
  sem CI e pedido de validação.
- Não executar \`appinst\` no WebReader, nem tocar na instalação atual ou
  nos capítulos offline no iPad.
- Build66 é fallback físico até Build67 ser aprovada separadamente.
