# WebReader — Fase P: inventário e limpeza confirmada de IPAs locais de QA

**Data:** 2026-11-08  
**Repositório:** AugustoArbulu/MangaReader12 (privado)  
**Branch experimental:** feat/chimera-updater-phase1-protocol-audit  
**PR:** #90 Draft contra main; não fazer merge nem alterar main.  
**Workflow aprovado:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42448774778  
**Commit compilado/testado:** 6503b38254882babb000301d49aaae5e27f59572  
**Build física estável relatada:** 66 (iPad iOS 12.5.8, Chimera, biblioteca e leitura offline aprovadas). Build67 tem IPA manual disponível e ainda não foi confirmada fisicamente. Build68 é somente código experimental, sem IPA publicada nesta fase.

## Objetivo

A ferramenta de importação local introduzida na Build67 cria cópias temporárias para auditoria de IPA. Após fechar o app, cópias antigas podem continuar no armazenamento. A Fase P acrescenta uma forma de identificar o espaço ocupado e descartar, sob confirmação explícita, apenas cópias antigas de QA, protegendo a biblioteca, os bancos, os capítulos baixados, as IPAs recém-importadas e arquivos desconhecidos.

Não alterar a forma de instalação; não executar appinst, launchctl, ferramentas root ou comandos externos. A limpeza não deve ocorrer automaticamente ao abrir o aplicativo.

## Implementação Swift nativa

Arquivo: MangaReader12/Core/WebReaderIPAStager.swift

Novas estruturas e funções:
- WebReaderLocalQAStaleCandidate: guarda nome, tamanho, dispositivo, inode e registros de modificação e alteração de metadados com segundos e nanossegundos.
- WebReaderLocalQAStorageInventory: guarda lista ordenada de candidatos, tamanho total, número de entradas ignoradas e negativa explícita de autoridade de instalação.
- WebReaderLocalQAStorage.inventory(directory:now:protected:): consulta SOMENTE LEITURA, sem criar pasta ou eliminar arquivos.
- WebReaderLocalQAStorage.discardConfirmed(_:directory:now:protected:): limpeza restrita a candidatos que já foram inspecionados e somente quando chamada após ação confirmada do proprietário.

Política do inventário:

1. Quando a pasta de QA ainda não existe, retorna zero cópias e zero bytes sem criar nenhum arquivo.
2. Abre a pasta Application Support/WebReaderLocalQAImports com O_DIRECTORY, O_NOFOLLOW e O_NONBLOCK, validando um diretório regular por fstat.
3. Limita a leitura a no máximo 512 nomes. Uma pasta com mais entradas é recusada, não percorrida sem limites.
4. Aceita somente nomes completos no padrão WebReader-Build<inteiro positivo>-local-<UUID>.ipa. Nunca aceita caminhos arbitrários, arquivos de backup ou nomes de capítulos.
5. Usa fstatat com AT_SYMLINK_NOFOLLOW no descritor da própria pasta, aceitando apenas arquivos regulares com um único hardlink e tamanho entre 1 byte e 512 MiB.
6. Exige no mínimo 24 horas tanto desde a última modificação quanto desde a última alteração de metadados (mtime e ctime). Arquivos recentes não são considerados elegíveis.
7. Exclui expressamente do inventário de limpeza a cópia ativa em revisão pelo usuário, comparando dispositivo+inode; ela permanece protegida mesmo se for antiga.
8. Faz soma de tamanho com verificação de overflow Int64. Retorna cópias ordenadas, tamanho total elegível e número de itens preservados.

Política do descarte:

- A tela exige confirmação distinta do usuário para excluir cópias consideradas antigas.
- Cada candidato é revalidado por fstatat, incluindo nome, diretório, tipo regular, hardlink único, identidade dispositivo+inode, tamanho, mtime/ctime e nanossegundos, idade mínima e exceção do arquivo ativo.
- Quando qualquer valor mudou desde a inspeção, a operação retorna false e NÃO remove o arquivo.
- Exclusão somente pelo unlinkat na pasta específica, após as verificações. Não há varredura recursiva, exclusão em Documents/Library/Downloads nem descarte de origem.
- Mostra o número real de arquivos removidos e de MB liberados, sem inventar remoções dos itens ignorados.

**Limite de segurança:** fstatat e unlinkat não formam uma transação atômica. Um adversário com permissão de escrita no mesmo diretório poderia competir na janela entre a inspeção e a exclusão. O código é não privilegiado; não usá-lo como política para o instalador root, nem afirmar que o nome do arquivo comprova autenticidade editorial. O sistema minimiza risco e exige confirmação, mas não oferece proteção perfeita contra toda corrida possível.

## Interface do aplicativo

Arquivo: MangaReader12/UI/WebReaderAppUpdatesViewController.swift

A seção IPA LOCAL (ARQUIVOS OU FILZA), disponível no WebReader normal e ausente nos apps de diagnóstico IPC, ganhou duas linhas, passando de quatro para seis ações:

1. Importar IPA local para conferir.
2. Compartilhar IPA local conferida.
3. Copiar SHA-256 conferido.
4. Descartar cópia local de QA atualmente selecionada.
5. ESPAÇO OCUPADO POR IPAS ANTIGAS: inspeção em fila assíncrona, mostrando quantidade e MB elegíveis e número de itens preservados.
6. LIMPAR CÓPIAS ANTIGAS DE QA: inspeção separada, mensagem explicando os limites, UIAlertController com botão Cancelar e botão destrutivo Excluir cópias antigas. O descarte só começa após a confirmação.

O indicador localQASpaceBusy impede que o inventário e a exclusão sejam executados simultaneamente a importação e compartilhamento do mesmo recurso. O usuário recebe mensagens claras para pasta indisponível, entradas demais e arquivos de QA efetivamente descartados.

## Testes e correção importante descoberta

Arquivo ci/test_native_webreader_local_qa_storage.py: suíte nativa Swift em macOS usando fixtures ZIP não instaláveis.

Cobertura inclui:
- Validação estrita de nomes de IPA de QA, rejeitando traversal e nomes que imitam backups.
- Pasta ausente resultando em inventário zero e sem criação de pasta.
- Recusa de pasta alvo que seja link simbólico ou arquivo regular.
- Duas importações com inodes próprios, protegidas por idade.
- Injeção de data futura somente dentro do teste para simular o decurso de 24 horas, sem alterar o relógio do sistema.
- Proteção do arquivo ativo, rejeição de exclusão antes da idade mínima e recusa de recibos inválidos.
- Links simbólicos, hardlinks e arquivos desconhecidos dentro do diretório ignorados, inclusive um arquivo com nome de biblioteca.
- Substituição de um candidato por bytes idênticos mas inode diferente: exclusão recusada.
- Metadados divergentes em nanossegundos: exclusão recusada.
- Após mover/restaurar arquivo original, o ctime muda e invalida corretamente o recibo antigo; somente uma nova inspeção pode gerar recibo válido.
- Com consentimento simulado, somente a cópia envelhecida e identificada exatamente é removida; a IPA original, a cópia ativa e arquivos desconhecidos permanecem.

Arquivo ci/test_phase_p_local_qa_inventory_policy.py: 11 testes estáticos sobre ausência de efeitos colaterais no inventário, limites de nome/tamanho/contagem, metadados, proteção da IPA ativa, confirmação explícita, nenhuma autoinstalação e contrato da interface. Permanecem em execução os 18 testes da auditoria e os 14 testes anteriores da interface.

O primeiro teste nativo falhou porque o próprio teste tentava limpar um arquivo movido e restaurado com um recibo antigo. A proteção do aplicativo funcionou, recusando a limpeza; o teste foi corrigido para exigir um inventário atualizado após a mudança de ctime, mantendo a rejeição do recibo velho. A execução final passou.

## CI final verificada

Workflow: .github/workflows/chimera-phase-p-qa-storage.yml  
Run: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42448774778  
**STATUS FINAL: SUCCESS, dois jobs aprovados**, commit 6503b38254882babb000301d49aaae5e27f59572.

- Linux: 18 + 11 + 14 = 43 testes estáticos aprovados, além das regressões existentes de UI, biblioteca e compatibilidade com Build65.
- macOS: passaram os testes reais Swift de auditoria ZIP/SHA, importação local, nova suíte de inventário e limpeza, downloader simulado, validação de manifesto e negação de instalação privilegiada.
- Compilação Debug completa para iOS12 ARM64: BUILD SUCCEEDED.
- Compilação Release completa para iOS12 ARM64: BUILD SUCCEEDED.
- A verificação final de identidade do aplicativo e da ausência de autorização de instalação passou.
- Nenhuma IPA Build68 foi produzida, publicada ou instalada. Não houve acesso ao iPad do proprietário.

## Estado do projeto e próximos passos

- Build66: última versão com aprovação física de biblioteca preservada e leitura offline.
- Build67: IPA de QA manual já entregue, mas ainda precisa ser testada no dispositivo para receber aprovação.
- Build68 experimental: fases N (auditoria do mesmo descritor), O (cópia vinculada ao inode) e P (inventário e limpeza com consentimento) passaram em CI, porém não foram compiladas como IPA distribuída nesta fase.
- Branch main permanece intocada; PR #90 permanece Draft.
- WebReaderAppinstSocket.liveInstallationEnabled = false. A chave pública editorial de produção permanece nil.
- LOCAL_PEERTOKEN não foi utilizável no diagnóstico mobile/Chimera; não assumir que testes macOS resolvem autenticação do helper no iOS12.
- Um próximo incremento pode estudar a identidade editorial independente e a distribuição assinada de releases, mas não deve conceder instalação privilegiada sem consentimento robusto, vínculo dos bytes ao executante e proteção contra replay/rollback.
- Um eventual teste manual de Build68 deverá ser explicitamente decidido pelo proprietário, com backup atualizado da biblioteca fora do iPad e pacote de QA com SHA-256 próprio, nunca reutilizando o nome/hash da Build66 ou 67.

**Encerramento:** gerenciamento conservador de IPAs temporárias concluído e aprovado na CI, sem modificar a Build66 instalada, sem criar IPA nova e sem habilitar atualização automática.
