# Build 47 + Asura Scans EN 0.1.2 — correção de capas e metadados Astro

**Data:** 2026-11-04. **Origem:** relato físico do usuário com MangaReader12 Build 46, Asura EN 0.1.1, iOS 12.5.8: **capas da listagem não carregam**; abrir uma obra retorna `source failed: JSON Parse error: Unexpected EOF`.

## Análise do código

São dois sintomas diferentes e **não se deve assumir que tenham exatamente a mesma causa**:

1. **Capas:** o adaptador 0.1.1 só aceitava mídia hospedada em `asurascans.com` ou `api.asurascans.com`; o domínio de CDN associado ao site `cdn.asurascans.com` não era permitido nem pelo adaptador nem pelo manifesto nativo. Fontes públicas recentes associam `cdn.asurascans.com` ao site. *Ainda não confirmamos fisicamente o hostname de cada capa faltante*; por isso o adaptador inclui um diagnóstico de hostname sem transmitir URL, query ou token.
2. **Metadados:** Asura usa atributos `props` JSON dos componentes `astro-island`. O `HTMLSelectorService.info` do Build 46 limitava atributos genéricos a **4.096 caracteres** (somente `data-page` tinha exceção), removendo `props` longos sem aviso. Isso é um bug estrutural real de compatibilidade do runtime com Astro. `Unexpected EOF` indica uma tentativa de analisar JSON incompleto, mas o erro isolado **não comprova que esse limite foi a única causa**. Um HTML alterado, response incompleto ou atributos inesperados também podem causar JSON inválido.

## Alterações

### Native Build 47 (nova IPA)
- O parser de DOM **inerte** (sem executar scripts externos nem visitar o site via WKWebView) permite `props` de **até 2 MiB somente quando o elemento é `astro-island`**, assim como a exceção pré-existente para `data-page`.
- Os demais atributos continuam limitados a 4.096 caracteres.
- Mantém HTML total <=3 MiB, saída <=4 MiB, seleção até 4.000 capítulos e 1.500 imagens; sem mudança na política de URLs HTTPS, domínios ou certificados.
- Build Debug/Release e Configurações atualizados para **47**, com teste antigo de integridade ImageIO do Build 46 preservado.

### Asura EN 0.1.2 (mesmo catálogo experimental)
- Autoriza o **hostname exato HTTPS `cdn.asurascans.com` somente como mídia**, ao lado de `asurascans.com` e `api.asurascans.com`. **Requests HTML/API continuam limitadas aos dois hosts anteriores.**
- Não permite `images.cdn.asurascans.com`, `cdn.asurascans.com.fake.invalid`, HTTP ou outras CDNs não revisadas.
- Listagens agora incluem `coverDiagnostic` opcional com hostname e `host-not-allowed` caso a capa permaneça bloqueada; jamais expõe URLs assinadas ou tokens.
- `astroProp` valida tamanho até 2 milhões de caracteres. Em JSON incompleto retorna mensagem controlada `Asura Astro props contain incomplete/invalid JSON (... characters)` ao invés de vazar/propagar exceção de parser sem contexto. No caso de props ausentes, indica possível incompatibilidade de Build 46 ou mudança do site. **Não faz retries ou bypass.**
- IDs estáveis da v0.1.1, cache, exclusão de premium, recusa de imagens com tiles, API pública e outras fontes preservadas.
- Manifesto `fixtures/asurascans-pilot-repository.json` pinado em `0.1.2` com SHA-256 do novo script.

## Testes automatizados
- `ci/test_asurascans_offline.cjs`: fonte 0.1.2, CDN autorizado vs. impostores/HTTP, diagnóstico só de hostname, metadados Astro com **350 capítulos** e atributo `props` acima dos antigos 4 KiB, JSON truncado e ausência de props; mantém testes de premium, tiles, URLs, IDs e estabilidade.
- `ci/test_build47_astro_props.cjs`: extrai e executa a **função JavaScript real** de `HTMLSelectorService.info` do Swift, com elemento falso `astro-island` e props de 500 capítulos; confirma que props >4 KiB são preservados até 2 MiB, mas props sobre limite e demais atributos >4 KiB continuam recusados. Verifica limites globais e numeração Build 47.
- Pipeline original segue testando iOS 12 SDK, contratos, ImageIO, SQLite/CBZ, Webtoons e WeebCentral, compilação Debug/Release sem simulador. Não realiza requests ao site.

## QA físico solicitado (após compilar e disponibilizar a IPA)
1. **Instalar Build 47 por cima do Build 46 via Sideloadly**, sem desinstalar, para preservar Biblioteca, configurações e downloads existentes.
2. Em **Explorar → Repositórios → catálogo Asura → Atualizar**, instalar **Asura Scans EN 0.1.2**.
3. Testar **Populares/Recentes**: capas de 2 ou 3 obras, não muitas. Se continuam vazias, reportar os títulos e eventual observação de hostname; não fornecer URL com token.
4. Abrir a **mesma obra** que dava `Unexpected EOF`; informar se agora aparecem título, capa, gêneros e capítulos.
5. Se reaparecer JSON inválido, enviar **apenas o erro textual**, pois pode indicar HTML Astro real diferente do fixture. Não tentar forçar autenticação ou contornar acesso.
6. Se lista de capítulos funcionar, abrir **um capítulo público**, sem premium. `tiled images` e `CDN requires review` são limitações deliberadas e ainda não corrigidas; isso não é falha deste Build 47.
7. Confirmar regressão rápida na WeebCentral EN 0.1.6 (abrir capítulo do CDN `official.lowee.us`) e no menu de downloads.

**Limites/estado:** passa em fixtures offline e compila para iOS 12 no CI. A disponibilidade real do CDN, formato Astro e decodificação de capas no dispositivo ainda precisam de QA físico; uma imagem WebP pode não ser decodificável pelo UIImage no iOS 12.
