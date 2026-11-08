# WebReader — Fase N (Build 68 experimental): auditoria atômica de IPA e proteção de armazenamento

**Data:** 2026-11-08
**Branch experimental:** feat/chimera-updater-phase1-protocol-audit
**PR:** https://github.com/AugustoArbulu/MangaReader12/pull/90 (Draft, sem merge)
**CI aprovada:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42446498882
**Commit testado pela CI:** dbfdcec0f34ca6d7f9ea6222975795953a16a17c

## Decisão de versionamento e estado no dispositivo

- A Build 66 foi aprovada pelo proprietário em um iPad com iOS 12.5.8 e Chimera: biblioteca intacta e capítulos anteriormente baixados abrindo sem Wi-Fi.
- A Build 67 foi construída e disponibilizada como IPA privada de QA, mas **não houve confirmação de instalação ou aprovação física da Build 67** até a redação deste documento. O artefato anterior está na execução https://github.com/AugustoArbulu/MangaReader12/actions/runs/42445422628 (ID 13603049559; SHA-256 de sua IPA 56fca5893ef3c713bf91b163fc8fe11d6b7ee6cfc6614191f0b754dadb39e897).
- Os dois pipelines históricos de Build 66 e de Build 67 para publicação de IPA privada foram congelados, sem gatilho automático de push e com guarda por SHA de commit. Novos códigos não devem ser distribuídos como se fossem a mesma IPA já entregue.
- Esta Fase N é **código e CI para uma futura Build 68**, sem IPA nova publicada, sem instalação e sem alteração na main.

## Problema de segurança investigado

Antes da Fase N, o auditor nativo WebReaderNativeIPAAuditor inspecionava o arquivo em duas aberturas baseadas em caminho: a primeira para calcular SHA-256 e a segunda para abrir e analisar o ZIP. Em um ambiente com jailbreak e processos potencialmente capazes de mudar arquivos locais, esse desenho permite que o arquivo referenciado pelo mesmo caminho seja trocado entre as duas leituras. O usuário poderia receber um relatório enganoso de um arquivo cujo conteúdo mudou durante o processo.

O novo desenho não afirma tornar o sistema à prova de toda alteração concorrente, nem permite uma instalação privilegiada. Seu objetivo é fazer uma verificação robusta e limitada de **um candidato a compartilhamento manual**.

## Mudanças no auditor nativo Swift

Arquivo: MangaReader12/Core/WebReaderNativeIPAAuditor.swift

1. Usa Darwin.open com O_RDONLY, O_CLOEXEC, O_NOFOLLOW e O_NONBLOCK. Não segue links simbólicos no componente final do caminho e não fica bloqueado aguardando um escritor em um FIFO malicioso.
2. Faz Darwin.fstat no descritor e aceita somente um arquivo regular com tamanho compatível com o manifesto esperado e limite do ZIP.
3. Calcula SHA-256 do próprio descritor, então lê diretório central, entradas, cabeçalhos e Info.plist pelo **mesmo descritor aberto**; não reabre o arquivo pelo nome entre os passos.
4. Ao concluir a auditoria, calcula um segundo SHA-256 e compara com o digest esperado.
5. Executa um segundo fstat e verifica dispositivo, inode, tamanho e horários de modificação e mudança de metadados antes de retornar o relatório.
6. Mantém todos os limites de ZIP anteriores: tamanho total, índice, entradas, caminhos, CRC do Info.plist, build nova, mínimo iOS e identidade do bundle.
7. Continua sem extrair IPA, instalar, contatar helper, executar shell ou migrar biblioteca.

**Limitação importante:** essas verificações reduzem inconsistências durante a inspeção. Elas não autenticam o editor e não asseguram que terceiros não modifiquem o arquivo *depois* que o método retorna ou enquanto o usuário compartilha. O instalador futuro precisaria reabrir e conferir seus próprios bytes sob uma política independente.

## Mudanças no importador local e interface

Arquivos:
- MangaReader12/Core/WebReaderIPAStager.swift
- MangaReader12/UI/WebReaderAppUpdatesViewController.swift

O importador local para Files/Filza, introduzido na Build 67, foi reforçado:

- Confere o tamanho da IPA e o espaço livre antes de começar a cópia. Exige tamanho da IPA mais margem de pelo menos 16 MiB e no máximo 64 MiB, sem ultrapassar o limite de arquivo de 512 MiB.
- Recusa a pasta final de staging quando esta é um link simbólico apontando para outro diretório, especialmente para evitar gravações acidentais em Library, Documents ou downloads.
- Usa permissões 0600 na cópia privada gerada, em vez de herdar permissões potencialmente amplas do arquivo de origem.
- Remove uma eventual cópia parcial quando falhar a operação, sem mover ou apagar o arquivo escolhido pelo proprietário.
- Mantém uma revisão anterior bem-sucedida caso uma nova importação seja recusada.
- Apresenta mensagens separadas para armazenamento insuficiente, IPA acima de 512 MB e impossibilidade de criar a cópia.
- Preserva a validação nativa SHA-256/ZIP/Bundle ID, a rechecagem antes do compartilhamento e a exclusão exclusiva de cópias criadas pela área de QA.
- O código do instalador segue bloqueado: liveInstallationEnabled = false. A chave pública editorial de produção continua nil.

O usuário não precisa informar login nem token GitHub dentro do app para analisar uma IPA local. O hash informado pelo usuário **não é prova independente de autoria editorial**.

## Testes adicionados ou ampliados

Arquivo ci/test_native_webreader_ipa_auditor.py:
- Acrescenta provas reais em Swift contra link simbólico apontando para um ZIP válido, FIFO sem processo escritor e diretório no lugar de IPA.
- Os testes rodam com timeout finito para detectar travamento em arquivo especial.
- Preserva casos negativos de pacote incompleto, CRC, compressão, duplicatas, traversal, versão/ID incorretos etc.

Arquivo ci/test_native_webreader_local_ipa_review.py:
- Exercita os cálculos de espaço livre mínimo, fronteiras de tamanho, margem e reserva máxima.
- Recusa uma pasta de QA redirecionada para uma pasta simulada de biblioteca e confirma que não houve gravação na pasta-alvo.
- Verifica as permissões privadas 0600 no arquivo copiado.
- Mantém 17 casos negativos de importação, alteração após aprovação, restauração de arquivos e descarte restrito.

Arquivos ci/test_build68_native_audit_contract.py e ci/test_build67_local_ipa_screen.py:
- Regras estáticas para manter o auditor no mesmo descritor, proibir symlinks/FIFO e conservar segundo SHA e fstat.
- Verificam reserva de armazenamento, mensagens de erro, permissões e isolamento da biblioteca.
- Confirmam que não há chave editorial de produção, nem autorização/instalação pelo appinst, nem mudança destrutiva da Library.

## Resultado comprovado da CI (host macOS e Linux)

Workflow: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42446498882
Resultado final: **SUCCESS em dois jobs**.

- Linux: 13 testes de auditoria atômica e 14 testes do contrato de UI/local staging, além das regressões de tela e biblioteca executadas no job.
- macOS: o auditor nativo rejeitou os casos ZIP malformados e as entradas especiais; testes Swift de importação local passaram com **17 cenários negativos**, limites de espaço, permissão privada e rechecagem após adulteração.
- Testes Swift do downloader, parser de GitHub Releases, verificação de manifesto e negativa do instalador também passaram.
- **Compilação integral Debug iOS 12 ARM64: BUILD SUCCEEDED.**
- **Compilação integral Release iOS 12 ARM64: BUILD SUCCEEDED.**
- O script de verificação de identidade original e bloqueio de instalação passou.
- O workflow NÃO gera IPA de Build 68, não usa appinst, não faz instalação e não publica GitHub Release.

A conclusão verde demonstra o comportamento no macOS CI e a compilação cruzada para iOS 12. Não equivale a um teste físico do novo código no iPad.

## Limitações e próximos marcos

1. A Build 67 ainda aguarda validação no iPad; a Build 66 é a referência fisicamente aprovada. Não desinstalar o aplicativo nem substituir o banco de dados para testar novos recursos.
2. Gerar uma IPA Build 68 deve ser um passo separado, depois da decisão do proprietário e com backup externo atualizado. Não reutilizar o rótulo/sha de Build 67.
3. A atualização automática continua bloqueada por falta de chave editorial confiável e autenticação/autorização independente do helper que executaria a instalação. O diagnóstico real do Chimera apresentou indisponibilidade de LOCAL_PEERTOKEN; não interpretar resultados macOS como viabilidade física iOS12.
4. A Fase N melhora a conferência **manual**. Ela não resolve download autenticado de GitHub Actions privado, consentimento de instalação, proteção total contra substituição após share sheet ou rollback do banco.
5. Manter a main intocada e a PR #90 Draft; continuar os próximos incrementos como código experimental e testes CI antes de distribuí-los ao dispositivo.

**Estado ao encerrar:** Fase N aprovada em CI, nenhuma IPA Build68 publicada, nenhum teste físico da Build68, nenhuma instalação automática habilitada.
