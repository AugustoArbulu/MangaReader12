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


## Marco DA — cliente iOS sandboxed separado pronto para QA física (21/11/2026 UTC)

Fase DA implementou e compilou um aplicativo iOS12 ARM64 com Bundle ID exclusivo com.example.WebReaderCXSandboxProbe e nome WebReader CX Teste. O cliente usa exatamente WRCHK2+LF para localhost 38973, acionado manualmente pelo botão Testar comunicacao CX. Nunca fornece IPA, caminho, hash, URL ou comando de instalação. O relatório mostra NOTICE_ACCEPTED, RATE_LIMITED ou falha, sem inferir versão disponível.

CI SUCCESS 3/3: https://github.com/AugustoArbulu/MangaReader12/actions/runs/44859172297. Artifact QA ID 14688662029. IPA SHA256 8fba25d3176b3d617c04f10470b5698b32de6bbd47f6929d5f2ba181dd138a1a. Documentação detalhada: docs/WEBREADER_DA_SANDBOX_CX_QA_2026-11-21.md.

**Próximo gate físico:** usuário instala apenas a IPA descartável por Filza+AppSync, abre WebReader CX Teste e toca no botão de conexão (sem instalar nada pelo próprio app), depois copia relatório. NOTICE ou RATE demonstra acesso ao serviço CX a partir da sandbox; UNAVAILABLE sugere restrição de rede ou listener e requer diagnóstico. Não alterar Build70, PING Build61 ou DEB CX, e não executar AppInst no app. Ainda não testado após reboot/rejailbreak.

Preservar main, PR #90 Draft, WebReaderAppinstSocket.liveInstallationEnabled=false, pins nil, nenhuma Build71/Release.

## Marco DA — comunicação app iOS 12 → serviço CX comprovada fisicamente (21/11/2026 UTC)

O usuário forneceu saída real do aplicativo descartável `com.example.WebReaderCXSandboxProbe` em iOS **12.5.8**, **UID/EUID 501/501**, conexão `127.0.0.1:38973`, quadro `WRCHK2` de sete bytes, resultado **`WR_DA=NOTICE_ACCEPTED`**, com `WR_DA_INSTALL=NEVER` e `WR_DA_PUBLISHER_AUTHENTICATED=NO`. Esse resultado comprova o canal de comunicação do app de QA com o serviço CX local no iPad. Texto integral preservado em `docs/WEBREADER_DA_SANDBOX_CX_QA_2026-11-21.md`.

Gate de transporte da fase DA: **APROVADO (hardware real)**. Não repetir provas de `posix_spawn` nem exigir novo teste de conexão em NewTerm antes de avançar. Próximo trabalho: diferenciar `check-only` do transporte (que não consulta versões) de um futuro serviço independente que verifica Release de origem fixa, autenticidade/editorial, antirreplay e disponibilidade — sem misturar aviso local com autorização de instalação.

Continuam pendentes: nenhum reboot/rejailbreak medido, identidade de processo remoto não autenticada, publisher trust de produção ausente, real instalação IPA pelo helper não implementada, consentimento seguro e preservação de biblioteca não demonstrados. Manter Build70, main e PR #90 Draft, sem habilitar `liveInstallationEnabled` ou publicar Build71.


## Marco pós-DA DB2 — observação de GitHub Releases reutilizando parser iOS12 (21/11/2026 UTC)

O transporte físico DA app → serviço CX foi aprovado; para a próxima etapa foi criado **observador read-only externo**, sem alterar ou reiniciar o serviço instalado. O identificador **DB2** é deliberado: a fase histórica Build70 DB (10/11/2026) trata de UID custody e não deve ser sobrescrita.

Arquivos novos: `ci/webreader_cx_release_observer.swift`, `ci/test_webreader_cx_release_observer.py`, `.github/workflows/chimera-db2-fixed-release-observer.yml`; documentação em `docs/WEBREADER_POST_DA_DB2_RELEASE_OBSERVER_2026-11-21.md`.

O observador Swift reaproveita `WebReaderUpdateChecker.swift` e `WebReaderGitHubReleaseParser.swift`. `--selftest` usa fixtures sintéticos sem rede; `--live` é uma ação explícita que faz um GET só ao endereço fixo `https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest`. Mesmo quando encontra metadata de build maior, rotula o resultado `UNTRUSTED_NEWER_METADATA`, nunca publisher verificado, IPA baixada ou instalação permitida. HTTP 404/403 permanecem erros/ausência de Release acessível, não confirmação de atualização.

GitHub Actions `#44859883589` **SUCCESS**: testes com Swift nativo no macOS, regressões de URLSession/parser e compilação do observador para ARM64 iOS 12. O job opcional de consulta live do observador ficou SKIPPED, por ausência de `workflow_dispatch` com opt-in. Separadamente, a API GitHub do repositório foi consultada: lista de Releases `[]`, `/releases/latest` HTTP 404 no instante verificado. Isso não foi um request realizado pelo novo executável.

**Próximo gate:** testar HTTPS real a partir do observador de laboratório e, futuramente, do iPad; não instalar nova versão de CX, não acionar AppInst, nem promover metadata GitHub à identidade editorial. Publisher pin ainda nil, check-only sem permissão, main/Build70 intocadas. Antes de instalação real permanecem gates de custódia entre UIDs, assinatura editorial, consentimento e recuperação de dados.


## Marcos pós-DA DB3/DB4 — consulta HTTPS real e QA iOS12 (21/11/2026 UTC)

**DB3 HTTPS macOS real:** GitHub Actions https://github.com/AugustoArbulu/MangaReader12/actions/runs/44860381932 SUCCESS. O observador Swift real do DB2 enviou um GET ao endpoint fixo `https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest` e registrou `WR_DB2_OBSERVATION=UNEXPECTED_HTTP_403`, com `IPA_DOWNLOADED=NO`, `OWNER_TRUST_PROVISIONED=NO`, `INSTALL_AUTHORIZED=NO`. O conector GitHub havia observado `/releases/latest` HTTP 404 e `/releases` vazio. **Não se conhece a causa do 403 no runner**; não atribuir a rate limit sem cabeçalhos.

**DB4 QA física preparada:** app UIKit descartável `WebReader HTTPS Teste`, Bundle ID exclusivo `com.example.WebReaderDB4HTTPSProbe`, compilado/signed ad hoc ARM64 iOS12. Faz um único GET ao endpoint GitHub quando se toca no botão; cancela na recepção dos cabeçalhos, rejeita redirecionamentos, exibe status + cabeçalhos limitados sem corpo, não autentica publisher e não instala. GitHub Actions https://github.com/AugustoArbulu/MangaReader12/actions/runs/44860617523 SUCCESS 2/2; IPA `WebReader-DB4-HTTPS-Only-iOS12-adhoc.ipa` SHA-256 `602b03dfe1c9638eaa683bdeb366e8f7e2bd815fd07b9580d966e9ec4e5584f8`. Artifact ID `14689757266`. Handoff: `docs/WEBREADER_POST_DA_DB3_DB4_HTTPS_2026-11-21.md`.

**Próximo gate:** instalação voluntária **apenas** da IPA DB4 usando Filza/AppSync, tocar uma vez em `Testar HTTPS GitHub`, copiar relatório (HTTP 403/404 ou domínio/código de erro de transporte). Não substituir Build70, nem remover DA/CX. Se sair 403 e aparecer `X-RateLimit-Remaining=0` ou `Retry-After`, fundamentar limitação de API; sem esses dados não inventar explicação. Independentemente do resultado, GitHub metadata não é uma chave editorial e não permite execução do AppInst.

Travas intactas: `liveInstallationEnabled=false`, `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, PR #90 Draft, `main` imutável, sem Build71 ou Release. Antes de real instalação ainda faltam identidade editorial, custódia dos bytes consumidos, anti-replay/downgrade, consentimento e recuperação dos dados.


## Gate físico DB4 aprovado — iOS 12 HTTPS GitHub API (21/11/2026 UTC)

O usuário forneceu relatório completo da IPA `com.example.WebReaderDB4HTTPSProbe` no iPad iOS 12.5.8, UID/EUID 501/501. A aplicação executou GET HTTPS para `https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest`, resultando em `WR_DB4_HTTP_REACHED=YES`, `WR_DB4_HTTP_STATUS=404`, content-type JSON, rate limit core **58/60 restante**, `Retry-After=MISSING`, sem ler o corpo, sem baixar IPA e sem instalar. Relatório integral: `docs/WEBREADER_POST_DA_DB3_DB4_HTTPS_2026-11-21.md`.

**DB4 aprovado fisicamente:** conectividade da sandbox iOS12 ao GitHub por HTTPS. A resposta 403 do runner macOS DB3 não foi repetida no iPad; sua causa permanece indeterminada. Em particular o iPad NÃO esgotou seu rate limit. O 404 **não** significa que WebReader está atualizado, só que `/releases/latest` não encontrou Release acessível.

**Próximo gate de engenharia:** revisão/fortalecimento offline do fluxo de atualização assinada v2 já existente, providenciar de forma independente origem de chave editorial somente com aprovação do proprietário, e projetar preservação dos bytes consumidos pelo instalador e consentimento — sem nova rodada física de conectividade, sem atualizar o serviço CX instalado ou habilitar AppInst. Chaves/pin continuam nil, produção fail-closed, nenhuma Build71 ou Release, PR #90 Draft e main/Build70 preservadas.


## Pós-DA DB5 concluída — signed-v2 sem novos direitos de instalação (21/11/2026 UTC)

Auditoria dos verificadores existentes identificou e corrigiu três divergências concretas: Swift de baixo nível exigia `expectedChannel=production` mas ainda podia verificar v1 assinado diretamente (a camada superior v2 já negava); Swift validava apenas a **forma** de `publishedAt`, não a validade Gregorian UTC; os verificadores Swift/Python toleravam aliases de Base64 com bits de padding não canônicos. Agora produção exige v2 diretamente no validador, datas impossíveis são rejeitadas e cada payload/assinatura deve usar Base64 canônico. Fixtures positivas continuam válidas, inclusive 29/02/2024 e manifesto production-v2 com chave de teste temporária.

Código modificado: `MangaReader12/Core/WebReaderUpdateManifestVerifier.swift`, `ci/webreader_update_manifest.py`, testes nativos e Python. Nenhuma chave privada ou pública de produção foi provisionada. CI final https://github.com/AugustoArbulu/MangaReader12/actions/runs/44861557092 **SUCCESS 3/3**, incluindo compilação dos verificadores para iOS 12 ARM64. Handoff: `docs/WEBREADER_POST_DA_DB5_SIGNED_V2_POLICY_2026-11-21.md`.

**Próximos gates reais:** provisionamento fora do repositório da chave editorial com pin independente (aprovação do proprietário), cadeia de bytes realmente consumidos pelo instalador, identidade/custódia protegida entre UIDs, anti-replay, consentimento em contexto confiável, backup/rollback da biblioteca e instalação de app descartável. DB5 não autoriza os gates; não solicitar novos testes físicos de CX/DA/DB4. Manter `liveInstallationEnabled=false`, `productionPublicKeyX963=nil`, `independentlyProvisionedSPKISHA256=nil`, Build70 e main intocadas, PR #90 Draft, sem Release/Build71.

## Pós-DB5 — confiança editorial e custódia da cópia de revisão

A prova anterior de custódia CK reabria a cópia pelo nome para calcular o segundo SHA-256. O hash podia corresponder ao esperado mesmo quando a segunda leitura vinha de um inode diferente do usado na escrita. Agora o laboratório reavalia o SHA-256 no descritor da própria cópia, limita a leitura ao tamanho esperado mais um byte e confere que o nome da IPA e o caminho do diretório ainda apontam para os objetos observados. O verificador recusa substituição por arquivo de conteúdo idêntico, alteração dos bytes gravados e substituição do diretório durante a revisão. Uma falha mantém a semântica de saída exclusiva e a eventual cópia parcial fica para inspeção.

| Etapa | Evidência disponível | Evidência necessária para produção |
| --- | --- | --- |
| Identidade editorial | A [cerimônia CO](WEBREADER_BUILD70_PHASE_CO_OWNER_OFFLINE_SIGNING_IDENTITY_2026-11-10.md) e o preview público CG foram ensaiados com chaves efêmeras. O preview verifica a chave pública SPKI contra o SHA-256 informado e produz um diff externo. | O proprietário deve autorizar e custodiar a chave privada offline. É necessário conferir o fingerprint público por via independente da distribuição da chave pública, antes de revisar o diff. |
| Cópia antes da entrega | O laboratório host compara bytes gravados e lidos no mesmo descritor e confere a identidade do arquivo e do diretório antes de emitir o recibo. | Confirmar que o helper iOS 12 tem custódia exclusiva do staging e dos ancestrais até o fim da leitura pelo consumidor. |
| Consumo pelo instalador | A [fonte de referência](WEBREADER_BUILD70_PHASE_CS_APPINST_PATH_BOUNDARY_2026-11-10.md) abre o pacote pelo nome e depois passa uma cópia ao serviço Apple. | Identificar o consumidor real e demonstrar o vínculo de bytes em cada reabertura ou cópia, até o último consumo. As permissões e o isolamento efetivos no iPad continuam sem evidência. |

A geração editorial pode ser feita no Windows, com a ferramenta CO, após decisão do proprietário. A CLI atual do preview público CG usa `O_NOFOLLOW` e OpenSSL. Usar Linux ou macOS para a revisão com os materiais públicos. Um resultado positivo do preview demonstra correspondência técnica entre PEM e pin, e a confirmação da origem continua sob responsabilidade do proprietário.

O recibo do laboratório expira como evidência no instante da observação. O retorno fecha o descritor e o modo 0400 sozinho não garante imutabilidade. A produção continua com chave e pin ausentes, geração zero e instalação automática desativada. Nenhuma ação no iPad nesta rodada.

O preview CG tem uma modalidade `--verify-only` que executa a mesma revisão do PEM público, do fingerprint independente e das constantes Swift que seriam propostas no diff. Essa modalidade imprime um recibo e deixa `externalPatch` nulo. Use os argumentos do [exemplo da cerimônia CO](WEBREADER_BUILD70_PHASE_CO_OWNER_OFFLINE_SIGNING_IDENTITY_2026-11-10.md), substituindo `--output-patch CAMINHO` por `--verify-only`. A validação da origem do fingerprint continua independente do preview.

## Identificação do AppInst instalado

Os testes físicos de execução direta não chegaram a executar AppInst. O próximo dado de custódia é a identidade do arquivo presente no iPad. O coletor [observe_appinst_identity.sh](../ci/observe_appinst_identity.sh) consulta, em NewTerm, o SHA-256 de `/usr/bin/appinst`, o proprietário registrado para esse caminho e o status, versão e arquitetura do pacote `ai.akemi.appinst`. A consulta de pacote pode ficar indisponível e o SHA-256 ainda pode ser reportado. O coletor não roda AppInst, não exige root e não copia o binário.

Comparar o SHA-256 recebido com o executável extraído em memória de um DEB previamente auditado pelo `ci/compare_appinst_fingerprint.py`. Um match vincula o digest relatado ao payload daquele pacote. A procedência do pacote, o executável efetivamente invocado pelo fluxo futuro e os bytes consumidos pelo instalador continuam dependendo de evidências próprias.

### Resultado físico no iPad — 21/11/2026 (horário de Brasília)

A captura do NewTerm mostra `/usr/bin/appinst` com SHA-256 `f0d17a033391b7f687285a892572662e2bca581766dbdc8bf463c1d517bd3147` e `dpkg-query` para `ai.akemi.appinst` retornando `install ok installed | 2.1.1 | iphoneos-arm`.

O comparador confirmou o mesmo SHA-256 no executável do DEB Legacy-Me previamente auditado. O SHA-256 do **DEB** foi revalidado separadamente como `5997771183c39eb8b5e13fc2bb511b1dfcb7eb39d3f10c9092ab088ec34aae09`. O resultado vincula o binário observado ao payload do espelho e encerra a comparação de identidade para esta observação. A procedência oficial do DEB segue sem confirmação.

A captura não executou o AppInst. O próximo gate de custódia é estabelecer qual arquivo o serviço de instalação efetivamente abre e por quanto tempo os bytes ficam protegidos. A instalação automática permanece desativada.

### Análise estática do AppInst identificado

O DEB de referência voltou a passar na verificação do SHA-256 fixado. A extração em memória confirmou que o executável de 370.064 bytes conserva o SHA-256 observado no iPad. A fatia Mach-O ARM64 contém, na seção Objective-C `__objc_methname`, os seletores `createDirectoryAtPath:withIntermediateDirectories:attributes:error:`, `copyItemAtPath:toPath:error:` e `installApplication:withOptions:error:`. O binário também contém `LSApplicationWorkspace`, `_zip_open` e a mensagem de falha ao copiar a IPA para um diretório temporário.

Esses elementos são compatíveis com a sequência da fonte de referência na [fase CS](WEBREADER_BUILD70_PHASE_CS_APPINST_PATH_BOUNDARY_2026-11-10.md). A inspeção confirma a presença dos seletores no executável correspondente ao hash observado. A ordem efetiva das chamadas, o caminho aberto pelo serviço Apple, as permissões vigentes e o tempo de custódia no iOS 12 ainda não foram observados. Uma próxima prova física exigiria um ensaio separado com pacote descartável aprovado e evidência da identidade do arquivo no ponto de leitura pelo serviço. Uma observação da cópia feita pelo AppInst, isoladamente, não encerra esse gate.

A análise foi somente leitura e não executou o binário. A instalação automática continua desativada.

### Pré-teste de visibilidade do serviço Apple

O app descartável existente (Bundle ID `com.example.WebReaderAppinstDisposableTest`) verifica versão e persistência de uma preferência. Sua tela não fornece evidência sobre a leitura da IPA. Antes de montar um ensaio de instalação, o [pré-teste](../ci/observe_installd_visibility.sh) verifica apenas se o `lsof` presente no iPad lista `installd` na sessão mobile do NewTerm. Ele emite apenas um status, sem enviar caminhos ou PIDs. Não exige elevação, instalação ou captura contínua.

- `PROCESS_LISTED`: o processo apareceu nessa consulta. Em um ensaio posterior, uma observação de descritor poderia identificar um arquivo aberto, mas uma consulta pontual pode perder aberturas breves.
- `LSOF_UNAVAILABLE` ou `NOT_OBSERVED`: a sessão atual não forneceu a observação. A distinção entre serviço ausente, visibilidade insuficiente e outras limitações depende de evidência adicional. O resultado não justifica iniciar uma instalação.

Para fechar o gate, o ensaio terá de ligar o hash conferido antes da transferência ao objeto de arquivo aberto pelo serviço e observar a custódia durante o consumo. Um registro de sucesso do app descartável ou do AppInst fornece evidência de funcionamento, mas deixa o vínculo dos bytes em aberto.

### Retorno físico do pré-teste

O proprietário reportou `WR_INSTALLD_VISIBILITY=PROCESS_LISTED` em NewTerm no iPad com Chimera. A consulta listou o comando exato `installd` na sessão usada. Continuam em aberto a visibilidade de descritores numerados de arquivos regulares e a capacidade de capturar a abertura da IPA durante uma instalação descartável.

A próxima verificação de leitura usa `lsof -a -c installd -Fpcft` em repouso e conta apenas registros `tREG` de descritores numerados do comando exato `installd`. O resultado não divulga PID nem caminhos. Uma contagem positiva demonstra a visibilidade de ao menos um descritor de arquivo regular naquela consulta. Zero é inconclusivo, pois a amostra pode simplesmente não conter arquivos regulares abertos. Nenhuma instalação é necessária para essa leitura.

### Limite confirmado no retorno do NewTerm

A sessão subsequente retornou código 127 com ambos os formatos de consulta. Sem redirecionamento, o Zsh informou `command not found: lsof`. Portanto, o `NOT_OBSERVED` desta sessão foi causado pela falta do comando no ambiente, e não serve como avaliação da visibilidade do serviço. O primeiro `PROCESS_LISTED` relatado fica registrado como observação não reproduzida. Nenhum descritor de IPA foi observado.

Encerrar a rodada de comandos que dependem de `lsof`. Antes de qualquer ensaio com o app descartável, será preciso validar uma ferramenta de observação compatível com esse dispositivo e estabelecer se ela consegue localizar o descritor no serviço no momento da leitura. Instalação automática segue desativada.

### Sondagem nativa após a indisponibilidade do lsof

`ci/webreader_self_fd_visibility.c` procura `proc_pidinfo` em tempo de execução, abre `/dev/null` como controle e verifica se `PROC_PIDLISTFDS` encontra esse descritor no próprio processo. O ABI usado é o definido no [cabeçalho do XNU](https://github.com/apple/darwin-xnu/blob/main/bsd/sys/proc_info.h). O programa não aceita PID externo e imprime somente um status, sem caminhos, PIDs ou conteúdo. Compilar para iOS 12 e observar sucesso no macOS são verificações diferentes de executar a sondagem no iPad. Mesmo um sucesso no iPad só confirmaria a consulta do próprio processo. A visibilidade de `installd` e a custódia da IPA continuam em aberto.

### Resultado físico do controle de descritor

O proprietário reportou `WR_SELF_FD=CONTROL_LISTED` no app separado `com.example.WebReaderSelfFDProbe`. A [execução de QA](https://github.com/AugustoArbulu/MangaReader12/actions/runs/44867440037) compilou e assinou ad hoc a IPA iOS 12 ARM64. SHA-256 da IPA entregue: `265828bc975f7a4e7768c8f32e39204b9e691c5c20c74cac2dc58a7b8cb91bba`.

O código resolveu `proc_pidinfo` e encontrou, na consulta `PROC_PIDLISTFDS` do próprio PID, o descritor de controle aberto para `/dev/null`. Isso encerra a prova de disponibilidade e funcionamento para o próprio processo nessa configuração. Para avaliar a leitura do instalador, o próximo controle deve investigar a consulta de um processo separado antes de medir `installd`. Nenhum descritor do serviço nem arquivo IPA foi observado nesse teste.

### Retorno físico da sondagem em dois apps

O proprietário reportou `WR_PEER_FD=TARGET_UNCONFIRMED` no Observador dos [apps de QA emparelhados](https://github.com/AugustoArbulu/MangaReader12/actions/runs/44868046146). O diagnóstico usa `proc_name` para conferir o nome exato `WRFDTarget` antes e depois de consultar `proc_pidinfo`. O mesmo status cobre falha de leitura de nome, nome inesperado e insucesso na reconfirmação. Assim, esse retorno não distingue PID antigo ou processo encerrado, leitura de nome indisponível, e falha posterior à consulta. Ele não prova que a consulta de descritores de outro processo foi negada.

A próxima sonda deve distinguir as etapas de identificação e, se necessário, adicionar um sinal independente de que o alvo segue vivo com o mesmo PID. Evitar repetir a mesma build como prova de acesso ao `installd`. Nenhuma instalação pelo WebReader nem observação de IPA em `installd` ocorreu.

### Observador v2

O Observador v2 distingue ausência das APIs, nome inesperado, falha de leitura antes ou depois da consulta, falha da consulta de descritores e layout inválido. Uma falha de leitura de nome acrescenta o errno, um teste de existência com sinal zero e o controle de leitura do próprio nome. O sinal zero não entrega sinal algum. Só é feita a consulta de descritores quando a leitura inicial devolve o nome esperado. O resultado positivo exige reconfirmação posterior e descreve apenas o número de descritor do controle.

O alvo v1 já instalado continua compatível. Atualizar somente o Observador, reabrir o Alvo, anotar o código atual e mudar de app sem encerrá-lo. Coletar apenas a linha `WR_PEER_FD_V2=…`. Nenhum teste consulta `installd` ou o arquivo de uma IPA em instalação.
