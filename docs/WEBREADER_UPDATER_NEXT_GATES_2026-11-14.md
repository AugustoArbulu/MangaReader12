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

## Gate físico Build5 concluído — revisão de prioridade em 20/11/2026 (America/Sao_Paulo)

A sequência Build3→Build4→Build5 isolou o bloqueio mais importante do **lançamento direto de processo pelo aplicativo**. Na Build5, iPad iOS12.5.8/Chimera:

- `WRSpawnChild` instalado como arquivo regular, mas sem bits de execução; `SPAWN_LOCAL=PRECHECK_FAILED`.
- Executável principal já assinado: `SELF_MAIN=REGULAR_EXEC`.
- Tentativa real de `posix_spawn` do próprio executável a partir do processo do app, com argumento seguro e sem instalação: `SPAWN_SELF=NEGADO (1 (Operation not permitted))`.
- `/usr/bin/appinst` foi apenas consultado com `lstat/access`, ambos retornando `EPERM`. O **AppInst não foi executado**, portanto não há evidência física de tentativa de spawn do AppInst, apenas da negação do self-spawn.
- Report e interpretação preservados em `docs/WEBREADER_APPINST_DIRECT_SAFE_SPAWN_PROBE_2026-11-14.md`; fixture de regressão em `ci/test_appinst_probe_report.py`.

### Decisão: não repetir diagnósticos de spawn in-app

Não produzir Build6 diagnóstica sem hipótese materialmente nova. Não recomendar executar `appinst --help`, `chmod` no bundle ou relaxar a sandbox. Não confundir `EPERM` observado no self-spawn com prova de que nenhuma arquitetura jailbreak pode instalar IPAs.

### Próximos marcos — independentes do self-spawn

1. **MVP de download seguro:** manter interface para verificar versões/releases publicadas e, quando existir uma Release aprovada, verificar digest, estrutura ZIP, bundle ID, build, iOS mínimo, assinatura editorial confiável e ligação aos bytes. **Nenhuma Release real foi autorizada nesta etapa**. Sem trust root provisionado, o modo produção assinado deve falhar fechado e não declarar autenticidade.
2. **Instalador fora do sandbox (pesquisa/contrato inicialmente):** investigar somente em laboratório isolado um helper persistente já instalado via mecanismo jailbreak, capaz de operar de forma independente do `posix_spawn` do app. O gatilho do app será no máximo solicitação de *check-only*, nunca caminho/URL/IPA nem autorização. O helper escolherá origem fixa e validará por si próprio identidade editorial, integridade, antirreplay, mesma cópia consumida na instalação, consentimento confiável e limites de uso, conforme fase CN. A identidade de peer por `LOCAL_PEERTOKEN` segue indisponível nos testes CM e não pode ser presumida.
3. **Alternativa OTA:** `itms-services` segue hipótese sem evidência física para IPA ad hoc + AppSync iOS12. Só poderá ser avaliada em aplicativo descartável, com manifesto próprio, nunca no WebReader principal sem aprovação.
4. **Gate obrigatório antes de instalação do WebReader:** teste de IPA descartável, assinatura e identidade verificadas, consentimento do proprietário, estratégia de preservação de biblioteca/offline, recuperação e rollback, sem mexer na Build70 até aprovação explícita.

**Status:** PR #90 Draft e `main` intacta; `WebReaderAppinstSocket.liveInstallationEnabled=false`; nenhum instalador ativo, Release, Build71, migração ou exclusão de dados. Não há necessidade de novos testes físicos de self-spawn por enquanto.

## Marco CX — transporte CHECK_ONLY independente da sandbox (21/11/2026 UTC)

Após o proprietário comprovar pelo NewTerm que o AppInst 2.1.1 inicia normalmente (appinst --help retorna a instrução de uso), mas a Build5 dentro da sandbox retornar SPAWN_SELF=NEGADO (1 (Operation not permitted)), reaproveitamos o núcleo CN/CW sem executar instalador no app.

Novos arquivos:
- ci/webreader_chimera_checkonly_service.c
- ci/test_webreader_chimera_checkonly_service.py
- .github/workflows/chimera-checkonly-transport-lab.yml
- docs/WEBREADER_CHIMERA_CHECKONLY_TRANSPORT_LAB_2026-11-20.md

O serviço de laboratório aceita SOMENTE sete bytes WRCHK2+LF no localhost 127.0.0.1:38973, após EOF da direção de escrita, e retorna WRNOTE2+LF (aviso aceito, sem checagem real), WRRATE2+LF ou WRDENY2+LF. Não recebe caminho, URL, digest, versão, chave, ação de instalação ou consentimento. Reutiliza dispatcher CW e intervalo de 60 s na mesma instância. Não executa AppInst, não abre IPA nem tem efeitos de instalação. Não integra ainda UI, consulta de Release, publisher, download ou mecanismo de aprovação.

CI SUCCESS 3/3: https://github.com/AugustoArbulu/MangaReader12/actions/runs/44849062382 — Linux/macOS QA real de socket e compilação ARM64 iOS12. Sem novo DEB/IPA, sem instalação em dispositivo, sem Release e sem alterar WebReader/Build70. A prévia iOS compilada em CI não foi assinada/distribuída.

Próximo gate: revisar transporte sem confundi-lo com autorização e projetar, somente após aprovação, um pacote de teste isolado, sem permissão de instalar, com identidade/porta distintas do PING Build61. Jamais substituir o PING já validado antes de testar coexistência. Para atualização automática real, continuam exigidos pin editorial, origem fixa, antireplay, custódia dos bytes, consentimento independente, QA de aplicativo descartável, recuperação e preservação do SQLite.


## Marco CY — cliente Swift real para o transporte CX (21/11/2026 UTC)

O WebReaderAppinstSocket.swift, já parte do projeto nativo, recebeu a API não automática checkOnlyConnection(completion:) e o resultado tipado CheckOnlyResult. Trata somente avisos check-only sem instalação:

- porta fixa 38973 no endereço 127.0.0.1; request fixo sete bytes WRCHK2+LF;
- shutdown(SHUT_WR) obriga EOF após frame; resposta de exatamente oito bytes com EOF, validando somente WRNOTE2/WRRATE2/WRDENY2;
- retornos são apenas diagnóstico de evento local não autenticado, sem afirmar checagem real de atualização; nenhum caminho/URL/hash/código/IPA pode ser inserido no quadro;
- nenhuma chamada ao AppInst, nenhuma integração UI automática e nenhum pacote no iPad.
- porta variável apenas em WEBREADER_HOST_TEST para testes isolados.

CI da fase CY: https://github.com/AugustoArbulu/MangaReader12/actions/runs/44850850358 — SUCCESS 3/3, incluindo Swift real para C real no macOS, tentativas de respostas falsas/truncadas/extras e crosscompile de servidor iOS12. A compilação do app inteiro é verificada separadamente no workflow WebReader updater MVP.

Próxima etapa: comprovar a compilação integral, depois definir UX somente de diagnóstico, e planejar um pacote de QA físico separado com consentimento do usuário, reutilizando a experiência Build61 FIX1, sem sobrescrever o serviço PING existente. Não conectar botão de instalação nem criar Release/Build71 enquanto as provas de publisher, bytes consumidos, autorização independente, backup e instalação descartável faltarem.


### Aprovação final da fase CY (21/11/2026 UTC)

A integração foi validada em **dois pipelines SUCCESS** no commit de código 9dcfdc536980243e2e4a53fd6bc350dd59759280:

- GitHub Actions #44850850358: Linux/macOS verificaram o transporte e o serviço CX, macOS exerceu o cliente Swift real e o serviço C real, mais crosscompile ARM64/iOS12 do serviço sem distribuir binário.
- GitHub Actions #44850850395: MVP de atualização completo SUCCESS, inclusive regressões do parser GitHub Release, checker nativo, IPA stager/auditor, UI e IPC Fake-AppInst, **compilação de todo o aplicativo para iOS12 sem assinatura/IPA** e verificação final dos hard stops.

URLs:
https://github.com/AugustoArbulu/MangaReader12/actions/runs/44850850358
https://github.com/AugustoArbulu/MangaReader12/actions/runs/44850850395

O serviço CX continua laboratório não instalado no iPad; o método Swift checkOnlyConnection é opt-in e não é chamado automaticamente pela UI. Todos os relatórios positivos são somente avisos locais, não atualização validada nem instalação permitida. Nenhum package/Release/Build71; Build70 e dados intactos.


## Marco CZ — laboratório físico isolado do serviço check-only (21/11/2026 UTC)

A fase CZ criou um pacote de QA separado do leitor e separado do PING legado. O objetivo é testar de forma opt-in a execução de um serviço launchd persistente no iPad iOS12.5.8/Chimera, sem executar AppInst ou atribuir autoridade a respostas locais.

- DEB: WebReader-Chimera-CheckOnly-CX-iOS12-QA.deb, package ID com.example.webreader.checkonlylab, v0.1.0.
- Contém somente /usr/local/libexec/webreader-checkonly (assinado ad hoc, mobile, modo 0755, executa serve ou probe) e /Library/LaunchDaemons/com.example.webreader.checkonlylab.plist, além dos diretórios pais.
- Usa porta local 38973, distinta da PING 38971; comando explícito em NewTerm como mobile: /usr/local/libexec/webreader-checkonly probe. Uma resposta NOTE é mero aviso de recepção sem consulta real ao GitHub, RATE indica rate limit. Nenhuma atualização é instalada.
- Empacotamento aproveita a correção Build61 FIX1 dos diretórios exigidos pelo dpkg no Chimera. O postinst carrega apenas seu próprio label via launchctl; prerm descarrega o mesmo label. Uma instalação física ainda exige decisão/ação explícita do proprietário.
- CI SUCCESS quatro jobs: https://github.com/AugustoArbulu/MangaReader12/actions/runs/44856655031, artifact ID 14687618052. DEB SHA-256 dd3c56c53fcb26fd8cbd31d3d23e28fe41be79b28c0ec7c3719a84404d15bc8e, verificado após extração.
- Detalhes, status e remoção: docs/WEBREADER_CHIMERA_CHECKONLY_TRANSPORT_LAB_2026-11-20.md.

**Limites:** pacote foi compilado e auditado em CI, NÃO foi instalado no iPad; a viabilidade física permanece em aberto. Nunca tratar PONG/NOTE como publisher trust, identidade de peer, disponibilidade de Release ou autorização de instalação. A API Swift checkOnlyConnection do WebReader não tem UI e não é chamada automaticamente.

**Hard stops:** Build70, biblioteca, banco e downloads intactos; main sem modificações, PR #90 Draft; liveInstallationEnabled=false; nenhuma Build71, GitHub Release ou AppInst real executado em CI. A fase CZ prepara apenas a QA física separada; não autoriza instalar o DEB sem intervenção explícita do proprietário.


## Marco CZ — primeira QA física relatada pelo usuário (21/11/2026 UTC)

O proprietário informou que **os testes guiados do .deb CX no Chimera deram certo**. Esta é uma confirmação por relato, sem captura nem linhas de terminal anexadas; não registrar saída NOTE/RATE ou `dpkg` como evidência documental independente. O pacote é o laboratório `com.example.webreader.checkonlylab`, não substitui o PING da Build61 e não contém instalador.

**Próximo gate objetivo:** confirmar independência da sessão do NewTerm: fechar totalmente o aplicativo de terminal, reabrir em mobile, executar `whoami` e `/usr/local/libexec/webreader-checkonly probe`, compartilhar os resultados. Após esse gate, avaliar um cliente iOS de QA separado para exercitar a comunicação a partir da sandbox, sem tocar na Build70, em vez de habilitar instalação.

Ainda não demonstrados: reinício/rejailbreak, app sandboxed comunicando-se com CX, atualização real, publisher verificado, assinatura editorial, consentimento independente, custódia do IPA e execução do AppInst pelo helper. Manter PR #90 Draft, main intacta e `liveInstallationEnabled=false`.


## Marco CZ — serviço persistente entre sessões do terminal (21/11/2026 UTC)

Após fechar completamente o NewTerm e abri-lo novamente, o proprietário relatou **sucesso no probe CX**. Considerar aprovado por relato o gate de independência da sessão do NewTerm; não há captura do resultado exato. A comunicação do serviço CX no Chimera funciona em contexto CLI sem que o terminal original permaneça aberto.

**Próximo gate:** validar uma solicitação de check-only partindo de um aplicativo iOS sandboxed descartável e com Bundle ID separado. Deve usar somente protocolo WRCHK2 + LF e interpretar confirmação como diagnóstico, não autenticação, disponibilidade de Release ou autorização de instalação. Não mexer na Build70.

Persistência após reinício/rejailbreak, autenticação de publisher, instalação real e verificação de consumo dos bytes continuam pendentes. Manter PR #90 Draft, main e Build70 intactas, liveInstallationEnabled=false.
