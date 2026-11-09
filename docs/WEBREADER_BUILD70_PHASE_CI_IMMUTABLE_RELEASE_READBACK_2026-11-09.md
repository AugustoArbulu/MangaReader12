# WebReader — Fase CI: readback de GitHub Release imutável e manifesto ECDSA v2

**Registro:** 09/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit` (PR #90 Draft). **Referência física:** Build70 no iPad iOS12.5.8, relatada como funcionando pelo proprietário. **Não gerar IPA, publicar Release, modificar `main` nem executar instalação nesta fase.**

## Problema que resolvemos

Os testes anteriores já vinculavam os claims assinados ECDSA P-256 da versão de produção a uma IPA auditada (CE/CF/CH). Faltava formalizar a conferência do **asset disponibilizado ao público depois do upload**, com a mesma verificação nativa de assinatura e arquivo que a IPA aprovada offline. Um checksum exibido na página do GitHub ou a palavra `signedManifest` na UI não bastam por si só.

O GitHub oferece dois campos verificáveis por snapshot REST: `release.immutable` e `assets[].digest` (SHA-256). A proteção de Releases imutáveis está disponível de forma geral desde 28/10/2025; quando habilitada, novas publicações protegem os assets e a tag. Referências oficiais:
- https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/
- https://docs.github.com/en/rest/releases/releases
- https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/establish-provenance-and-integrity/prevent-release-changes

## Novo verificador offline, sem publicação

`ci/build70_immutable_public_release_readback.py` exige **arquivos externos**, enviados separadamente ao operador (não credenciais da API, não objetos obtidos do próprio manifesto):

1. **Chave pública PEM do proprietário** e **SPKI SHA-256 obtido previamente por canal independente**. O programa nunca lê nem gera a chave privada.
2. **Manifesto production-v2 assinado**, como bytes originais do proprietário, e **cópia exata do manifesto recuperado do canal público** `main/updates/channel-production-v2.json`. Os dois devem ser *byte a byte iguais*.
3. **IPA de origem assinada ad hoc** e **cópia da IPA baixada novamente do Release público**. Devem ser arquivos regulares distintos, fora do repositório. Cada arquivo passa individualmente por `review_production_release`: ECDSA, pin, SHA, tamanho, ZIP, identidade, assinatura nativa macOS/ARM64 e iOS12. A cópia do Release não pode ser o mesmo inode da origem.
4. **Snapshot JSON da API REST do Release**, com URL/tag `buildN`, `draft:false`, `prerelease:false`, **`immutable:true`**, asset `WebReader-BuildN-iOS12-adhoc.ipa` único, `state:uploaded`, `size`, `digest:sha256:<hash-assinado>`, tipo ZIP/octet-stream e `browser_download_url` igual à URL assinada.

O verificador recusa versões não superiores ao iPad, campos REST duplicados, metadados ou conteúdo alterados, referências SHA/pin divergentes, caminhos symlink, retorno de Release editável ou rascunho e IPA sem assinatura ad hoc correta.

O programa é **offline**, não possui URLSession/urllib/requests, não pede tokens GitHub, não cria Releases, não edita manifesto, não escreve no app e não invoca `appinst`. O recibo positivo indica **consistência dos arquivos apresentados ao processo**, não prova, sozinho, que a API realmente foi consultada, que o download veio do GitHub nem que o proprietário autorizou publicar. Essas evidências precisam ser coletadas separadamente de uma origem autenticada. O resultado jamais autoriza instalação.

## Ensaios

- [**CI real CE estendida #42724518479**](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42724518479): **SUCCESS**. Reutilizou a IPA70 real e auditada, SHA `526291cc77203c3881e5f3f1c75904e8863dbde3b3bd9df7e1185c3229fb4fc1`, duas cópias distintas e um manifesto assinado com chave P-256 **efêmera**. O campo `immutable:true` e demais metadados do Release foram **simulados localmente**. Ambas as cópias passaram na auditoria real de assinatura nativa macOS; **nenhuma publicação, nenhuma chave editorial cadastrada**.
- `ci/test_build70_immutable_public_release_readback.py`: assinatura ECDSA efêmera genuína e mutações de `draft`, `prerelease`, `immutable`, tag, URL, tamanho, digest, estado do asset, tipo, duplicates, JSON malformado, canal e baseline. Os testes de controle de fluxo Linux empregam mock do verificador nativo **apenas na parte de contrato**; teste separado confirma que a IPA sintética real é recusada pelo auditor nativo.
- [**CI AC–CI**](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42724564434): testes Python/Linux, Swift nativo/macOS e compilação iOS12 ARM64 Debug/Release, sem produzir uma IPA.

## Procedimento de lançamento real — futuro, condicionado à aprovação

1. O proprietário gera e protege **fora do GitHub e deste chat** uma chave P-256 de produção, registra de modo independente o fingerprint público e revisa o patch público produzido pelo preparador CG. Nenhum usuário precisa compartilhar senha/chave privada por mensagem.
2. Após revisão separada, compila-se uma **Build bootstrap superior à 70**, com **somente o ponto público X9.63 e pin SPKI**, instalando-a **manualmente e por cima** da Build70. Verifica-se que biblioteca, favoritos, progresso e páginas offline antigas sobreviveram. A chave privada jamais entra na IPA.
3. O proprietário aprova explicitamente a visibilidade pública da futura IPA e a habilitação de **Settings → General → Releases → Enable release immutability** no GitHub; essa política protege apenas novas Releases. A configuração não foi alterada por esta fase.
4. Para uma Build posterior: assinar manifesto v2 **fora** do CI, conferir IPA/codesign/manifesto com `ci/build69_production_release_preflight.py`. Em Release **rascunho**, anexar a IPA auditada, revisar os bytes e só então publicar como Release imutável. O `gh release create` envolve diversas chamadas API e não é uma operação atômica.
5. Em um computador independente, baixar o asset público, exportar o JSON de `GET /repos/AugustoArbulu/MangaReader12/releases/tags/buildN`, e obter o manifesto publicado por HTTPS. Rodar o verificador CI com esses arquivos **sem fornecer token ao WebReader**.
6. Somente após conferência pública e aprovação explícita, atualizar `main/updates/channel-production-v2.json` com os mesmos bytes assinados. Rechecar HTTPS pelo iPad em iOS12 e o download manual no aplicativo. O manifesto assinado mantém a autenticidade editorial, independentemente de GitHub funcionar como transporte.

**Exemplo do readback, apenas depois de existirem arquivos genuínos e aprovados**:

```bash
python3 ci/build70_immutable_public_release_readback.py \
  --owner-public-key /offline/owner-public-p256.pem \
  --independent-spki-sha256 "$OWNER_INDEPENDENTLY_VERIFIED_PIN" \
  --signed-manifest /external/owner/channel-production-v2.json \
  --public-manifest /external/readback/channel-production-v2.json \
  --source-ipa /external/approved/WebReader-Build72-iOS12-adhoc.ipa \
  --readback-ipa /external/readback/WebReader-Build72-iOS12-adhoc.ipa \
  --release-rest-json /external/readback/github-release-build72.json \
  --installed-build 71
```

O exemplo não é uma ordem para lançar a Build72 nem afirma que exista. **Não executar** com dados fabricados como se fossem uma publicação real.

## Barreiras persistentes

A Build70 instalada **não possui pin público editorial**. Nenhum Release público foi publicado no repositório quando esta fase começou; `main/updates/channel-production-v2.json` também não existe. A partir daqui, apenas o proprietário pode definir a custódia do par real e autorizar a futura exposição de uma IPA em Release.

Mesmo após uma atualização assinada poder ser baixada, **a instalação continuará manual**: helper Chimera exige autenticação do processo ligado ao socket no iOS12, ledger confiável antirreplay/rollback, confirmação de instalação no helper e uso dos bytes imutáveis autenticados. `WebReaderAppinstSocket.liveInstallationEnabled=false` permanece intocado.

**Condições não alteradas:** `main` intacta; PR Draft; Build70 iPad intacta; biblioteca, offline, backups e fontes de leitura não acessados; nenhuma nova IPA criada nesta fase.
