# WeebCentral EN 0.1.5 — datas dos capítulos para Biblioteca e atualizações

**Data: 2026-11-03.** Atualização somente do script da fonte e do catálogo piloto; mantém o MangaReader12 **Build 45**.

## Motivo
O upstream Keiyoushi identifica `<time datetime="...">` no HTML de `/full-chapter-list`, porém a adaptação iOS da WeebCentral 0.1.4 devolvia `date: null` para todos os capítulos. O leitor já suporta `Chapter.date: String?`, e a infraestrutura nativa verifica atualizações por **IDs estáveis** em `LibraryUpdateManager`. Esta revisão melhora metadados e registros sem mudar a detecção por ID.

## Implementação
- Reutiliza a seleção existente `time[datetime]` já realizada pelo parser WebKit.
- Retorna o valor ISO 8601 original (com frações e fuso) quando passa pela validação estrita, sem mudar o timezone nem inventar datas.
- Quando o atributo está ausente ou tem formato desconhecido, `date` continua `null`. Nome, ID, ordem dos capítulos, gêneros da obra, capas e páginas permanecem inalterados.
- Não adiciona pedidos HTTP nem contorna restrições de acesso.
- Atualiza `fixtures/weebcentral-pilot-repository.json` para `0.1.5`, com SHA-256 fixado.

## Testes
A suíte `ci/test_weebcentral_offline.cjs` reproduz atributos de data como `2026-10-29T20:05:15.069Z` e `2024-09-07T17:04:15.717343Z`, validando a integridade do campo e os IDs de capítulo. Os testes existentes cobrem gêneros, filtros gerais, paginação, capas, imagens e recusa de host externo.

## QA físico para quando o usuário voltar
1. Atualizar o catálogo WeebCentral e instalar **WeebCentral EN 0.1.5** no Build 45.
2. Conferir datas (quando exibidas na lista de capítulos) e abertura dos capítulos em *One Piece*.
3. Adicionar uma obra pequena à Biblioteca e executar **Atualizar Biblioteca**. Confirmar que a operação termina e não cria notificações falsas repetidas para capítulos já conhecidos.
4. Para verificar detecção de capítulos **novos**, precisa ocorrer de fato uma atualização na fonte; não inventar atualizações nem usar conteúdo privado.
5. Verificar um download pequeno e leitura em modo avião separadamente.

**Status:** testes offline; atualização de Biblioteca e downloads ainda não validados fisicamente.
