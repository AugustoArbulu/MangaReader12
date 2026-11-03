# Build 45 — WeebCentral EN filtros gerais via busca remota

**Data:** 2026-11-03  
**Objetivo:** integrar os filtros suportados pelo mecanismo de busca da WeebCentral à UI nativa iOS 12 sem priorizar qualquer tag específica.

## Estado confirmado antes desta fase

WeebCentral EN **0.1.2** no **Build 44**, iOS 12.5.8:
- Listagem e detalhes funcionam, capítulos abrem e imagens de páginas carregam.
- Usuário confirmou que *One Piece* mostra agora o **capítulo 1** como mais antigo, antes cortado no 998. O bug nativo de 200 capítulos está resolvido para essa obra.
- Ainda não foram comprovadas a atualização automática na Biblioteca e leitura de download em modo avião.

## Referência técnica

Implementação Keiyoushi `src/en/weebcentral/.../Filters.kt`: 
https://github.com/keiyoushi/extensions-source/blob/main/src/en/weebcentral/src/eu/kanade/tachiyomi/extension/en/weebcentral/Filters.kt

A fonte oferece parâmetros repetidos `included_tag` e `excluded_tag`, além de `included_type`, `included_status`, `sort` e `order`. Tags disponíveis na fonte são explicitamente enumeradas, incluindo Romance, Action, Fantasy, Harem, Horror, Yaoi, Yuri, Mecha e outras. **Não há inferência automática por título, capa ou personagem**; o comportamento depende da classificação e da execução da busca pelo próprio site.

## Mudança do script — WeebCentral EN 0.1.3

- Expõe `source.filterOptions()`, opcional na Source API v1, com lista de **38 tags**, quatro tipos, quatro status e seis opções de ordenação.
- `source.search(query,page,filters,done)` recebe objeto de filtros contendo `includedTags`, `excludedTags`, `types`, `statuses`, `sort`, `order`. A rota continua `/search/data`, com parâmetros públicos do site, no mesmo pedido HTTP de busca; sem novas chamadas para classificação.
- Lista de opções restrita ao arquivo de referência do Keiyoushi. Valores desconhecidos, duplicações, tipo incorreto ou tag simultaneamente incluída e excluída são rejeitados **antes** de qualquer request.
- Sem filtros, mantém compatibilidade com a API existente: `popular`, `browse`, `search(...,[])`.
- Mantém regras HTTPS, allowlist de mídia e erros de acesso; nenhuma alteração no mecanismo anti-bot, TLS, cookies ou identidades.
- Catálogo experimental isolado atualizado com SHA-256 do script 0.1.3.

## Mudança nativa — Build 45

No painel existente `Explorar ▸ filtros` para fontes que anunciam `filterOptions`, adicionar:
- Seção **Gêneros e tags da fonte** com 38 opções e três estados: **um toque exclui** (vermelho), **segundo toque inclui** (cor de destaque), **terceiro toque limpa**.
- Tipo de obra (Manga, Manhwa, Manhua, OEL), status (Ongoing, Complete, Hiatus, Canceled), ordenação e ordem crescente/decrescente.
- Vários gêneros podem ser incluídos/excluídos; seleção de tags sem um limite artificial de 5 opções.
- Valores persistidos localmente por **ID de fonte**, sem modificar preferências de outras fontes, Biblioteca ou arquivos baixados.
- Quando há filtros da fonte ativos, as listagens passam pelo método `search` com a mesma seleção em **todas as páginas**, inclusive quando nenhuma palavra-chave é digitada. Em **Recentes**, a ordenação padrão `Latest Updates` continua disponível caso o usuário não a substitua.
- O filtro local antigo permanece acessível somente se tinha exclusões já configuradas; novas preferências da WeebCentral devem ser feitas por **Gêneros e tags da fonte**.
- Outros adaptadores sem `filterOptions` continuam usando as exclusões locais e os métodos existentes. Interface foi projetada para reutilização por outras fontes, como a Asura, quando houver suporte equivalente.

**Limite de escopo:** os filtros mais raros da extensão Android, como autor e flags oficiais/anime/adulto, ainda não têm controles nativos. Este build cobre a demanda de exclusão geral, tags, tipo, status e ordenação.

## QA e critérios de aceitação iOS 12.5.8

1. Instalar **Build 45** via IPA não assinada e Sideloadly, preservando a instalação anterior. Instalar/atualizar **WeebCentral EN 0.1.3** no catálogo piloto — ambos são necessários para exibir a UI de filtros.
2. Abrir a WeebCentral, tocar no painel **Explorar** e acessar **Gêneros e tags da fonte**. Selecionar, por exemplo, **+ Romance** e **− Horror**. Para incluir Romance, tocar duas vezes; para excluir Horror, uma vez.
3. Aplicar. Percorrer várias páginas, observar se a paginação continua funcionando e se os títulos retornados refletem os critérios. Filtros dependem da marcação no site e podem omitir obras incorretamente classificadas.
4. Testar também tipo `Manhwa`, status `Ongoing`, seção Recente e busca textual com filtros ativos.
5. Fechar e reabrir o app; confirmar persistência. Usar **Limpar** e verificar a volta da lista padrão. Conferir Webtoons EN sem mudanças inesperadas.
6. Caso retorne HTTP 403/429 ou recusa explícita de acesso, **não insistir nem contornar**; enviar somente a mensagem de erro, sem URLs de capítulos ou tokens.
7. **Não marcar como produção** até validação física dos filtros, atualizações na Biblioteca e downloads offline.

## Testes de CI

- `node ci/test_weebcentral_offline.cjs`: opções completas, encoding de inclusão/exclusão repetidas, múltiplos tipos/status, paginação com query, ordenação e rejeição de entradas inválidas sem requests.
- `python3 ci/test_build45_filters.py`: versão nativa, callback, persistência, estado tri-state, integração da busca e proteção de outras fontes.
- Preservados: verificação de segurança Comix, CBZ, leitor, filtro Webtoons e parser HTML do Build 44.

**Status:** funcionalidade implementada e testada offline, **QA físico não realizado**.
