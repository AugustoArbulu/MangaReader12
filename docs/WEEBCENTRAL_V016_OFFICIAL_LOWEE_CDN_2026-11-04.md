# WeebCentral EN 0.1.6 — CDN oficial lowee.us usado nos capítulos

**Data:** 2026-11-04. **Afeta:** leitura online E downloads offline, pois ambos dependem do método `source.pages`. **Build nativo:** continua 46; esta é uma atualização da fonte JavaScript e do catálogo piloto.

## Evidência física do usuário (Build 46 + WeebCentral 0.1.5)

Ao tentar baixar **e ao abrir** um capítulo no iOS 12.5.8, a fonte apresenta:

```text
source failed: weebcentral: blocked image hostnames: official.lowee.us.
images parsed: 62, permitted: 0, missing/unsupported: 0.
Only hostnames are reported; no blocked images were downloaded.
```

O parser encontrou 62 elementos de imagem no HTML, mas todas as URLs tinham o hostname exato `official.lowee.us`, que **não** aparecia na allowlist. O bloqueio ocorre *antes do download das imagens*, portanto este caso não valida nem invalida o novo ImageIO do Build 46 e não indica que os bytes estejam corrompidos.

## Alterações propostas

- O adaptador `fixtures/keiyoushi-weebcentral-en.js` passa de **0.1.5 → 0.1.6**.
- Adicionar **somente** `official.lowee.us` ao regex `imageHostRE`, além dos hosts já existentes `weebcentral.com` e subdomínios, `temp.compsci88.com` e `hot.planeptune.us`.
- Acrescentar **somente** `official.lowee.us` ao array `domains` do catálogo piloto. Essa segunda alteração é essencial: o runtime nativo autoriza hosts de mídia por manifesto, não somente pelo adaptador.
- Recusar `http://official.lowee.us`, `cdn.official.lowee.us`, `official.lowee.us.malicious.invalid` e quaisquer hostnames ainda não revisados.
- Manter a política de falhar em capítulo incompleto: se uma página for bloqueada, não entregar uma lista parcial.
- Não modificar método de request, cabeçalhos, cookies, WAF, CAPTCHA, detecção de atualizações, ordem das páginas, ImageIO, fila de downloads ou código nativo. Nenhum request de imagem é feito nos testes offline.

## Testes offline

O arquivo `ci/test_weebcentral_offline.cjs` foi ampliado para simular 62 imagens do hostname `official.lowee.us` e validar:

1. Todos os **62** URLs são aceitos sem perdas; índices 0–61, primeiro e último URL preservados.
2. O cabeçalho `Referer` existente é mantido.
3. O parser usa **somente o mesmo GET de HTML**; não realiza downloads de mídia no teste.
4. URLs HTTPS de hosts semelhantes ou subdomínios não revisados continuam proibidas; não há vazamento de tokens, query strings nem caminhos nos diagnósticos.
5. O catálogo e o SHA-256 do script estão sincronizados.
6. Todas as outras regressões da WeebCentral, filtros, gêneros e capítulos continuam cobertas por CI.

## Procedimento de QA físico

1. Permanecer no **Build 46**, sem reinstalar ou apagar Biblioteca/Downloads.
2. **Explorar → Repositórios → catálogo WeebCentral → atualizar → instalar WeebCentral EN 0.1.6**.
3. Abrir o **mesmo capítulo** que falhou e conferir se todas as 62 imagens carregam sem aparecer em branco. Não é necessário abrir dezenas de capítulos.
4. Depois, baixar **esse mesmo capítulo** e verificar se as páginas são salvas e o status alcança `Concluído`. Se for longo ou demorado, usar outro capítulo pequeno do mesmo hostname.
5. Ativar modo avião e verificar que o capítulo já baixado é legível **sem internet**, passando até a última página.
6. Se aparecer HTTP 403/429, erro de certificação TLS, resposta inválida ou outro hostname bloqueado, **não insistir ou contornar proteções**. Reportar o erro exato, sem URL assinada/tokens.

**Limite de evidência:** a aceitação da URL por allowlist é comprovável offline, mas não garante que o host esteja acessível ou retorne imagens válidas no dispositivo. O verdadeiro funcionamento online/offline precisa de teste do usuário após atualização da fonte.

## Referências

- Código da fonte: `fixtures/keiyoushi-weebcentral-en.js`.
- Catálogo: `fixtures/weebcentral-pilot-repository.json`.
- Controle de integridade nativo: `docs/BUILD46_DOWNLOAD_IMAGE_INTEGRITY_2026-11-03.md`.
- Handoff anterior: `docs/HANDOFF_COMPLETO_MANGAREADER12_WEEBCENTRAL_ASURA_BUILD46_2026-11-03.md`.
