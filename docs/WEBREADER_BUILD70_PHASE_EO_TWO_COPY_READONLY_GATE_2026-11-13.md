# WebReader — Fase EO: duas cópias externas completas, auditoria somente leitura
Data: 13/11/2026 · PR #90 Draft · Build 70 instalada no iPad (sem alteração física nesta fase)

## Por que esta fase existe

O arquivo `.mr12backup` **não** contém as imagens offline. Uma comparação isolada da biblioteca ou um ZIP com as IPAs não demonstra que Downloads, planos parciais, preferências e histórico foram preservados.

As fases EA–EK já verificam partes distintas dos arquivos **de cópias extraídas**, mas rodar apenas uma delas pode dar falsa sensação de segurança. A fase EO agrupa os auditores existentes em um único pré-check que nunca aprova uma instalação, mesmo quando as duas cópias concordam.

## Ferramenta de pré-check (computador, sem conexão com iPad)

`python3 ci/build70_eo_two_copy_review.py --first "/CAMINHO/COPIA_INTEGRAL_1" --second "/CAMINHO/COPIA_INTEGRAL_2"`

Os argumentos representam as pastas-raiz de duas cópias **independentes** e extraídas do **contêiner completo de dados** do app, não duas pastas Downloads isoladas, nem duas pastas dentro uma da outra. O conteúdo deve preservar, no mínimo, `Library/Application Support/MangaReader12/library.sqlite`, `Library/Application Support/MangaReader12/Downloads/` e todos os demais diretórios do contêiner, como `Documents` e `Library/Preferences`. Não supor que as duas cópias são independentes apenas por terem nomes diferentes.

A ferramenta consulta, sem gravar dados:
- **EC** compara o hash integral do conteúdo e a estrutura das duas árvores, recusando symlinks, arquivos especiais e alterações.
- **EA** valida SQLite e as páginas de capítulos concluídos.
- **EH** inspeciona integridade e relacionamentos do banco; **EI** contabiliza também downloads inacabados e órfãos.
- **EJ** revisa planos de recuperação sem expor URLs/headers; **EK** classifica apenas o prefixo parcial por metadados.
- **EF** identifica respostas HTML, truncamentos e assinaturas plausíveis de imagem, sem afirmar decodificação em iOS 12.
- **EC novamente** detecta alteração visível nas árvores entre o início e o fim dessas inspeções.

A saída é um JSON com **status por auditor e contadores agregados**: nunca imprime caminhos absolutos, títulos, nomes de fontes, capítulos, URLs, headers, checksums completos ou conteúdo dos arquivos. `EO_STOP_*` exige revisão. `EO_TWO_COPIES_COHERENT_NOT_DEVICE_ATTESTED` significa apenas que as duas cópias coincidem no host, não que foram extraídas do mesmo iPad nem que podem ser restauradas.

**Política fail-closed:** o programa retorna código de saída **2 em todos os casos** (inclusive cópias idênticas). Isso é intencional: resultados locais não liberam IPA71, acesso privilegiado, `appinst`, restaurar banco ou limpar dados. Um relatório com downloads incompletos/órfãos exige análise manual, nunca exclusão automática.

## Gate físico que permanece pendente

A validação com o iPad iOS 12.5.8 precisará ser realizada **separadamente**, após autorização do proprietário e uma cópia externa comprovadamente recuperável:
1. Confirmar que o contêiner copiado pertence à instalação Build70 em uso, com identidade de aplicativo e conjunto de arquivos coerentes; não substituir o app nem usar `.mr12backup` como cópia integral.
2. Obter duas capturas íntegras com o app fechado e atividades de escrita suspensas, sem perder WAL, journal, histórico, preferências e capítulos parciais. A ferramenta apenas lê capturas já existentes; ela **não** realiza extração, congela o app ou verifica a origem da cópia.
3. Reabrir o **mesmo capítulo já baixado** no WebReader físico com a rede desligada; observar imagens e posição de leitura antes de qualquer atualização. Não inferir sucesso no iPad de um teste sintético macOS.
4. A eventual atualização Build71 requer autorização específica **de entrega** e outra **de instalação**; somente depois comparar o mesmo capítulo e os dados antes/depois. Nenhuma dessas autorizações é dada por este documento.

## Limitações explícitas

Cópias idênticas podem resultar da mesma cópia original defeituosa. Dois hashes iguais não provam cadeia de custódia, origem do dispositivo, consistência de SQLite **no instante da captura**, identidade assinada do WebReader nem possibilidade de restaurar. Verificação de metadados de páginas parciais não prova que todos os bytes de imagem são legíveis. Hash integral antes/depois reduz corridas observáveis, mas não é snapshot atômico contra alterações externas maliciosas. Se a captura contiver dados privados, **não publicá-la na PR ou nos artefatos de Actions**.

## Segurança e CI

`ci/test_build70_eo_two_copy_review.py` usa apenas SQLite e arquivos sintéticos e cobre correspondência de duas cópias, alteração de preferências, página ausente, links simbólicos, órfãos, incompletos, alteração durante auditoria, privacidade e retorno não zero. Os testes são rodados na matriz Linux/macOS do workflow EA–EO; **a PR Draft, `main` e o iPad não são alterados** pelas verificações. `productionPublicKeyX963` e SPKI continuam nil, e `liveInstallationEnabled=false`; `ci/build71_owner_approved_qa_trigger.txt` continua ausente.

Próxima etapa só após evidência física: conferir identidade do app instalado e leitura offline real antes de eventual autorização de build de atualização. Não gerar nem instalar IPA71 nesta fase.
