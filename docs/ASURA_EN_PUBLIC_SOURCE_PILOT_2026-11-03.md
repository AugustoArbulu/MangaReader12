# Asura Scans EN — primeiro piloto público de fonte para iOS 12

**Data:** 2026-11-03. **Escopo:** primeira etapa da Asura, **não publicada no catálogo principal**. A WeebCentral continua independente e funcional na versão confirmada pelo usuário. Não há necessidade de nova IPA.

## Requisitos do projeto
O usuário confirmou querer **duas fontes completas**, WeebCentral e Asura, incluindo busca, Biblioteca, atualização de capítulos e downloads offline. Esta implementação Asura é um **piloto parcial**, não um anúncio de fonte completa.

## Referências verificadas
- Keiyoushi `src/en/asurascans` (Apache-2.0): https://github.com/keiyoushi/extensions-source/tree/main/src/en/asurascans
- Busca usa a API pública `GET https://api.asurascans.com/api/series`, `limit=20`, `offset=(page-1)*20`, `sort`, `order`, `search`.
- Detalhes e capítulos extraídos de propriedades **Astro serializadas** do HTML de `https://asurascans.com/comics/{public-slug}`.
- Capítulos podem ter `is_premium`, `is_locked` ou `early_access_until`; a extensão Android possui rota opcional autenticada para imagens premium. **Este projeto não a implementa**.
- Parte das imagens públicas usa `tiles`, `tile_cols`, `tile_rows` e requer um redimensionamento/reordenação nativo. **Não entregar imagens embaralhadas como se fossem páginas legíveis.**

## Implementação source-only `0.1.0`
- `fixtures/keiyoushi-asurascans-en.js` implementa `metadata`, `popular`, `search`, `details`, `chapters` e `pages`, além de descoberta popular/recente.
- `popular` / `search` / `browse` mapeiam JSON da API pública, sem navegador, scripts da página ou credenciais.
- `details` / `chapters` parseiam **somente atributos `props` estáticos** por `Native.htmlSelect`, desempacotam a serialização Astro e geram modelos iOS. Chamadas simultâneas para a mesma página são agrupadas, e os resultados são cacheados em memória por 30 segundos, para evitar dois GETs imediatos ao abrir detalhes.
- Capítulos marcados premium, bloqueados ou sujeitos a acesso antecipado ainda ativo são **omitidos**, sem chamadas autenticadas nem tentativas de acesso.
- `pages` só retorna páginas **públicas, não embaralhadas e em hosts permitidos**; caso encontre qualquer imagem com `tiles` ou host externo, interrompe todo o capítulo para evitar download incompleto/corrompido.
- Rejeita URLs HTTP, domínios não permitidos, filtros arbitrários e redirecionamentos externos. Erros mostram somente hostname de CDN, sem URL assinada, query ou cookies.
- Catálogo experimental **separado** em `fixtures/asurascans-pilot-repository.json`, com SHA-256 fixado. Nenhuma modificação no catálogo de fontes existentes.

## Limitações importantes (gates)
1. **CDNs de capas e páginas:** ainda não foram verificados em uma amostra física atual. A allowlist inclui somente `asurascans.com` e `api.asurascans.com`. Capas de outros hosts podem aparecer vazias; não abrir hosts adicionais sem evidência.
2. **Imagens divididas em tiles:** falta um decodificador nativo iOS 12 com CoreGraphics, validação de permutação, limites de pixels/memória e integração à leitura e aos downloads offline. Até lá, esses capítulos **falham com mensagem específica**.
3. **Capítulos premium:** não suportados; a ausência de páginas é uma falha controlada, não autorização para buscar tokens ou cookies.
4. **IDs e redirecionamentos:** o piloto usa a URL pública `/comics/{slug}` identificada pela API. O site às vezes altera um sufixo aleatório do slug; persistência de capítulos e updates precisam de um mapeamento de ID estável depois de teste e documentação dessa mudança, antes de marcar a Asura como completa.
5. **Filtros avançados** da Asura dependem de gêneros dinâmicos da página `/browse`; não incluídos nessa fase. O app preserva os controles das outras fontes.
6. **iOS 12.5.8:** nenhuma funcionalidade de rede da Asura foi testada fisicamente nesta etapa. O CI não prova disponibilidade atual da API nem do HTML.

## Testes offline
`node ci/test_asurascans_offline.cjs` cobre:
- retorno JSON de busca popular/recentes/com texto, offsets 20, ordenação e esquema dos cards;
- Astro props aninhados, autoria, status, gêneros, títulos alternativos e descrição;
- carregamento conjunto de detalhes e capítulos sem dois GETs;
- remoção de capítulos premium/bloqueados/early access;
- datas ISO, IDs e ordenação de capítulos;
- duas imagens públicas normais, host externo e `tiles` com falha controlada;
- rejeição de HTTP/hosts externos, 403 sem retry, redirecionamentos e filtros não suportados;
- integridade SHA-256 do catálogo experimental.

## Próximos passos recomendados
- Validar o piloto em dispositivo **somente se desejado** e com requisições pontuais. Se houver acesso negado/403/429, interromper; não repetir nem contornar.
- Confirmar hostnames reais dos CDNs legítimos e revisar política.
- Implementar a transformação de imagens por tiles **em um PR nativo separado**, com fixture artificial segura, limites de memória e QA offline/physical antes de qualquer publicação.
- Verificar estabilidade de IDs por URL em atualização da Biblioteca e estratégia de migração sem perder progresso.
- Depois aplicar filtros remotos da Asura por parâmetros oficiais, sem simular exclusões de tags que o servidor não oferece.

**Status:** adaptador experimental parcialmente funcional por contrato offline. **Não validado em site/aparelho e não considerado fonte completa.**
