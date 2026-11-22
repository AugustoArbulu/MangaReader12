# WebReader — Fase EQ: impedir acesso e exclusão por colisão de caminhos offline
Data: 13/11/2026 · PR #90 Draft · revisão exclusivamente no repositório

## Risco efetivamente observado no código

`OfflineDownloadPath.safeComponent` conserva caracteres alfanuméricos, pontos, sublinhados e hífens, mas troca outros caracteres por `_` e transforma `.` e `..` em `item`. Logo, IDs de capítulos diferentes podem se tornar **o mesmo caminho físico**. Exemplos sintéticos: `part/01` e `part?01` ambos geram `part_01`; `.` e `..` ambos geram `item`. Em sistemas de arquivos com equivalência de caixa/Unicode, outros nomes podem representar o mesmo destino. Antes da EQ, `remove()` só checava se o job não estava em execução e depois removia o diretório canônico; a confirmação humana da UI não provava que a pasta pertencia exclusivamente àquele ID. Abertura offline, retry e restauração de sessão também podiam confundir duas linhas persistidas que normalizassem para o mesmo caminho.

## Medida implementada

A nova `WebReaderOfflineCanonicalOwnership.collides` considera a identidade **exata e completa** (`sourceID`, `sourceMangaID`, `sourceChapterID`) contra todos os registros de downloads do SQLite. Compara os três componentes do caminho transformados pela mesma `safeComponent`, usando um *folding* conservador de maiúsculas/minúsculas, diacríticos, largura e Unicode canônico. Se outra identidade persistida corresponder ao caminho, **interrompe** a operação sem modificar as páginas.

Guardas adicionados:
- **`download()`**: recusa colisões antes da criação da pasta, atualização do plano ou gravação no banco, inclusive quando o usuário confirmou uma repetição.
- **`restorePreviousSession()`**: mantém os arquivos, mas não restaura automaticamente um job ambíguo nem abre URLs de seus planos.
- **`localPages()`**: não abre páginas que podem pertencer a outro capítulo; também impede o *rebind* do caminho SQLite para um diretório alheio.
- **`remove()`**: verifica antes de alterar `jobs`/`pending` ou apagar a pasta que exista registro de download de **exatamente** aquela identidade e que não haja outra identidade com caminho equivalente. A confirmação da interface permanece obrigatória, mas não contorna a guarda.
- **`DownloadRepository.removeMissingFiles()`**: evita reatribuir ou excluir metadados quando há caminho ambíguo.

O erro em português `ambiguousOfflineChapterPath` esclarece que o conteúdo não foi apagado e requer revisão. Nenhuma rotina tenta renomear, fundir, deduplicar, mover ou remover os downloads conflitantes.

## Testes e suas fronteiras

`ci/test_build70_eq_canonical_path_ownership.py` contém verificações estáticas da ordem das guardas e um teste Swift nativo em macOS com registros SQLite sintéticos. Casos: colapso por pontuação, `.`/`..`, caixa, variantes Unicode conservadoras, identidade exata que não deve bloquear, pasta de outro mangá que deve continuar acessível e inventário vazio. A regressão Linux/macOS da fase EG e o build geral de iOS12 executam o teste sem acesso físico ao iPad.

**Limitação:** a verificação conhece apenas linhas **existentes na tabela de downloads**. Arquivos órfãos ou dados de aplicações sem representação no banco continuam exigindo revisão do contêiner externo completo pela Fase EO/EP. A equivalência Unicode conservadora pode recusar dois nomes que seriam fisicamente distintos: nesse caso, a segurança dos dados é priorizada sobre a disponibilidade. Nenhuma execução sintética garante ausência de todas as corridas de filesystem nem conteúdo legível no iPad real.

## Gates mantidos

A PR continua Draft e `main` não é modificada. Sem Build71, `appinst`, Release, mudança de assinatura, trust de produção, restauração ou acesso ao iPad iOS 12.5.8. O `.mr12backup` não inclui imagens offline; para QA física futura continua indispensável cópia integral externa, revisão local das duas cópias e leitura do mesmo capítulo sem rede antes/depois de qualquer atualização, com aprovação explícita e separada do proprietário.
