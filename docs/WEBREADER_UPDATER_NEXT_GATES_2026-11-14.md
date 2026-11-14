# Atualizador WebReader iOS12 — próximos passos práticos (14/11/2026)

## Meta específica
O usuário quer **atualizar o WebReader diretamente dentro do aplicativo**, sem depender de PC, e-mail ou Filza. Não é necessário concluir as investigações EV–FN de exclusão para isso. A Build70 instalada, dados e downloads permanecem preservados.

## Estado verificado na branch do PR #90
- `ci/test_public_github_release_parser.py` ganhou cenário sintético **Build70 → Build71**, assim como rejeição de Build70 ou antiga e de Release sem SHA-256. Isso **não autoriza criar ou publicar Build71**, é apenas um teste com metadados fictícios e o parser Swift real.
- O workflow de [MVP do atualizador](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43549579113) terminou **SUCCESS** no commit `117bd1f`, incluindo parser, checagem de update, stager de IPA, auditoria, UI e AppInst falso, mais compilação do app inteiro para iOS 12 sem IPA.
- No GitHub, o repositório está público mas **não possui nenhuma Release** (lista vazia; `/releases/latest` retorna 404 em 14/11/2026 UTC). O atualizador não pode mostrar um pacote inexistente.
- O botão atual do app só oferece compartilhamento manual via Filza depois de validação local. `WebReaderAppinstSocket.install()` continua recusando `WRINST1` e `liveInstallationEnabled=false`. Um PING no socket ou o SHA de GitHub **não** autentica uma solicitação de instalação.

## Caminho mínimo, sem novas fases de armazenamento
1. Preparar **somente com aprovação explícita do proprietário** uma IPA futura maior que a instalada (Build70), mesmo bundle ID, iOS mínimo 12, assinatura ad hoc/entitlements compatíveis. Verificar preservação por backup e teste em dispositivo antes de substituir o WebReader principal.
2. Publicar uma Release `buildN` com **um único asset** `WebReader-BuildN-iOS12-adhoc.ipa`, tamanho e `digest: sha256`, somente depois de aprovação para publicação. Publicação de asset não é equivalente a assinatura editorial independente.
3. Testar detecção, TLS/CDN, SHA, ZIP e exportação pelo app iOS 12, sem instalar a IPA principal automaticamente.
4. Para remover o Filza, validar primeiro uma instalação com **aplicativo descartável** via método integrado. A ponte de produção não pode receber pedidos de instalação até autenticação do cliente, confirmação no app e integridade do caminho/IPA no momento da instalação. O helper já demonstrou protocolo fake em macOS, não uma instalação física segura a partir do WebReader.

## Alternativa exploratória: OTA do sistema (`itms-services`)
O iOS possui mecanismo de instalação OTA via manifesto plist HTTPS contendo URL e Bundle ID. **Não há evidência física de que isso funcione com as IPAs ad hoc do projeto + AppSync em iOS12/Chimera**; os fluxos oficiais de OTA normalmente pressupõem assinatura de distribuição adequada. Pode ser testado **somente com aplicativo descartável e manifesto próprio**, nunca disparado automaticamente para o WebReader real. Isto é alternativa, não implementação aprovada e não substitui os controles de autenticidade do artefato.

## Proibições mantidas
Não alterar `main`, não gerar Release/Build71, não executar AppInst real, não instalar no iPad, não migrar banco nem apagar capítulos; manter PR #90 Draft. O trabalho EV–FN fica arquivado e fora do caminho crítico.

## Resultado do CI final (14/11/2026 UTC)
O [workflow dedicado #43551192312](https://github.com/AugustoArbulu/MangaReader12/actions/runs/43551192312) terminou **SUCCESS** em macOS 15, no commit `cb541b6ffc82b4fd2141f8fd679f412bc863984b`. Passaram os 5 testes de escopo, o parser real com a fixture Build70→Build71, checker Swift com resposta injetada, stager de IPA, auditor nativo ZIP/Info.plist/SHA-256, UI e AppInst falso; o WebReader inteiro compilou para o alvo iOS 12 sem assinatura, IPA ou instalação. Esse resultado **não comprova** a instalação no Chimera nem cria uma Release pública.

O método OTA foi apenas estudado: AppSync Unified pode contornar certas verificações de assinatura no `installd`, mas as exigências de manifestação e distribuição OTA são distintas. Nenhuma compatibilidade real entre `itms-services` e a assinatura ad hoc usada aqui foi demonstrada. Preferir o caminho já comprovado de AppInst/Filza até ensaio físico com um app descartável.
