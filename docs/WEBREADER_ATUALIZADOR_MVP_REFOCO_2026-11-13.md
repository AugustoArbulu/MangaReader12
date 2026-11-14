# WebReader iOS 12 — retomada do atualizador (MVP pessoal)
Data: 13/11/2026 (America/Sao_Paulo) · PR #90 Draft

## Decisão
Interromper as fases experimentais EV–FN de exclusão, retenção e migração como pré-requisito do **atualizador**. O objetivo imediato é o fluxo já existente **GitHub Releases → conferir nova Build → baixar IPA por HTTPS → validar hash, ZIP, Bundle ID e versão → compartilhar com Filza**. Esse é o MVP *manual*. O objetivo posterior, explicitado pelo usuário, permanece a instalação **dentro do app** via helper seguro e confirmação explícita, sem computador/Filza. Não confundir ambos.

## Verificações de estado
- O repositório `AugustoArbulu/MangaReader12` é **público** conforme a API do GitHub e sua lista de GitHub Releases está **vazia** na inspeção de 14/11/2026 UTC. `/releases/latest` retorna HTTP **404**. Portanto, o app não tem nenhuma IPA pública para baixar, mesmo com o parser/UI prontos.
- `WebReaderGitHubReleaseParser.swift` aceita somente tag canônica `buildN` e um único asset `WebReader-iOS12-unsigned.ipa` ou `WebReader-BuildN-iOS12-adhoc.ipa`, em HTTPS no repositório exato, com `digest: sha256:<hex>`, `state=uploaded` e tamanho até 512MiB. Assets de **GitHub Actions** não são Releases.
- `WebReaderUpdateChecker.swift` não trata HTTP 404 como app atualizado; mostra erro. O texto da tela foi simplificado para `HTTP 404: nenhuma Release pública acessível; não há IPA para baixar`.
- `WebReaderIPAStager.swift` só armazena e valida, mediante confirmação; `WebReaderAppUpdatesViewController.swift` compartilha a IPA revalidada pelo menu do iOS para usar no Filza, **sem instalação automática**.
- `WebReaderAppinstSocket.install()` retorna `.rejected`; `liveInstallationEnabled=false`. A autenticação do helper no Chimera não foi comprovada para pedidos de instalação. O PING/PONG não equivale a autenticação. Nenhum comando real appinst deve ser disparado a partir do app até um teste de aplicação descartável.
- Root editorial ECDSA de produção ausente. O hash fornecido pelo próprio GitHub atesta consistência sob essa origem HTTPS, não uma assinatura editorial independente.
- O app instalado no iPad é a **Build 70**; uma Release somente será oferecida como atualização quando tiver **build maior que 70**. **Nenhuma Build71, Release ou atualização física está autorizada** por esta retomada.

## O que fizemos nesta retomada
1. Reconfirmamos o GitHub (público; zero Releases).
2. Clarificamos no UI a resposta de 404, sem mascarar erro como `upToDate`.
3. Adicionamos `ci/test_webreader_updater_mvp_scope.py`, cinco testes de contrato do caminho manual, da ausência de autoridade AppInst e da separação do canal assinado.
4. Criamos `.github/workflows/webreader-updater-mvp-no-install.yml`, CI macOS dedicado ao parser real, checker injetado, stager, auditor de IPA, UI e socket fake, seguido de compilação integral sem assinatura e sem IPA.

## Para entregar o objetivo final
1. Escolher e aprovar uma próxima Build candidata (sem sobrepor a Build70); compilar/assinar e validar a identidade do app, conteúdo e backup offline. **Não publicar sem aprovação do proprietário**.
2. Publicar explicitamente um GitHub Release compatível (tag, asset e digest), verificando a API pública sem login.
3. Testar no iOS12 físico a consulta, TLS/CDN, download, SHA, auditoria e compartilhamento para Filza; preservar app instalado e dados.
4. Só para atualização **em um toque**: desenvolver uma política mínima e comprovável de autenticação do cliente para o helper `appinst`, revisão no Chimera e teste em aplicativo descartável. Não habilitar isso apenas por PING ou por SHA de GitHub.

## Invariantes
PR #90 continua Draft. Código das fases EV–FN permanece arquivado na branch, sem novas mudanças. `main`, Build70, downloads reais, banco SQLite, dados de usuário e chaves de produção não foram modificados. Este workflow de CI não publica Release, não produz IPA distribuível, não instala e não faz migração.
