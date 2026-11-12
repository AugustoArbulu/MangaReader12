# WebReader — Fase EC: duas cópias externas, conteúdo integral do contêiner (12/11/2026)

**Branch:** feat/chimera-updater-phase1-protocol-audit. PR #90 Draft; main intocada. Fase 100% host-only, sem IPA/Release/instalação e sem acesso aos dados físicos do iPad.

## Motivação

EA (aprovada Linux/macOS) verifica bytes dos capítulos marcados como completos numa cópia externa; EB (aprovada Linux/macOS) compara contagens dos relatórios Build70 com essa cópia. Entretanto, ambos deixam de fora outros arquivos do contêiner (preferências, fontes, capítulos incompletos, documentos e demais dados). Comparar duas cópias externas é uma ferramenta de detecção de perda na transferência — **não é autenticação da origem do iPad**.

## Entrega

- ci/build70_ec_full_container_dual_copy.py: scanner somente leitura de DUAS cópias já extraídas do data container, com hashes SHA-256 determinísticos de caminhos relativos, diretórios e conteúdo de arquivos regulares. Inclui arquivos ocultos e arquivos vazios. Requer cópias fisicamente separadas em árvores de diretórios não aninhadas.
- Reutiliza a EA para verificar em AMBAS as cópias banco SQLite v1, dados offline, recibos, e recusa WAL ou rollback journal não vazio.
- Recusa symlinks na raiz e nas entradas examinadas, entradas especiais, hardlinks de arquivo, alterações detectáveis por mtime/inode entre leitura e fechamento, árvores profundas e limites excedidos (até 250 mil arquivos, 100 mil pastas, 1 GiB por arquivo e 128 GiB de arquivos agregados).
- Não imprime paths, títulos, URLs, IDs ou conteúdo das páginas. Informa totais, quantidades de bytes e hash agregado da árvore apenas se ambas forem byte a byte idênticas.
- ci/test_build70_ec_full_container_dual_copy.py: testes exclusivamente com cópias fictícias de SQLite e páginas.
- .github/workflows/chimera-build70-phase-ec-external-copy-compare.yml: testes host em Linux/macOS, com trava explícita do trigger Build71 e flags de instalação.

## Uso opcional futuro (não executado)

1. O proprietário deve preservar o WebReader Build70 instalado e, somente quando decidir, criar uma cópia EXTERNA do contêiner de DADOS inteiro, usando mecanismo que preserve SQLite coerentemente. Não apagar WAL/journal do original. Não substituir uma cópia antiga sem antes validá-la.
2. Se desejar checar uma transferência de dados, criar uma SEGUNDA cópia independente e extrair cada uma em uma pasta diferente no computador. Não apontar para o próprio iPad, o .app ou .mr12backup.
3. Executar localmente com Python 3: python3 ci/build70_ec_full_container_dual_copy.py --first "/copia-externa/A" --second "/copia-externa/B"
4. Interpretar EC_TWO_EXTERNAL_COPIES_IDENTICAL_NOT_DEVICE_PROOF apenas como igualdade de arquivos DENTRO DAS DUAS PASTAS lidas naquele instante. EC_STOP_EXTERNAL_COPIES_DIFFER significa que as cópias divergem e não se deve usar a conclusão de identidade. Zero capítulos e legados são estados distintos, nunca prova de biblioteca vazia ou de decodificação de imagens.
5. Guardar cópias em armazenamento controlado pelo proprietário; não carregar banco SQLite, preferências ou páginas privadas no GitHub.

## Limitações explícitas

Mesmo duas cópias idênticas podem ter sido obtidas de um original já corrompido, incompleto, falsificado ou desatualizado. Este scanner NÃO faz ou autentica backups, não lê o iPad, não garante atomicidade do instante em que a cópia foi capturada, não prova que dados foram retidos fora do aparelho, não valida restauração e não demonstra leitura de imagens em iOS12. A auditoria de diretórios compara snapshots locais e recusa algumas mutações observáveis, mas não fornece garantia de exclusão de toda corrida de filesystem nem prova identidade do dispositivo. Arquivos maiores que o orçamento são recusados, não truncados.

O .mr12backup segue sem imagens. Restaurá-lo substitui o banco e remove downloads. A futura migração Build70→71 ainda requer identidade física do bundle instalada, backup externo verdadeiro, auditoria da IPA71 final, aprovação explícita e separada de entrega/instalação, e teste do mesmo capítulo offline com Wi-Fi desligado antes/depois. A atualização automática permanece desabilitada.

**Barreiras obrigatórias:** trigger ci/build71_owner_approved_qa_trigger.txt AUSENTE; productionPublicKeyX963=nil, independentlyProvisionedSPKISHA256=nil, liveInstallationEnabled=false; readyToDistributeIPA=false, readyToInstallIPA=false, installationAuthorized=false, restorationAuthorized=false, automaticUpdaterEnabled=false. Nenhuma ação física no iPad.

**Validação CI:** verificar os jobs e logs reais do workflow EC antes de marcar o suporte macOS/Linux aprovado. Não inventar resultados enquanto jobs estiverem em fila.
