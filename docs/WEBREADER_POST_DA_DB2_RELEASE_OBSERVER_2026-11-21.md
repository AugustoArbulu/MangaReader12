# WebReader iOS12 — pós-DA DB2: descoberta de Releases, sem confiança editorial nem instalação

Data: 21/11/2026 UTC. Branch feat/chimera-updater-phase1-protocol-audit, PR #90 Draft. Nunca modificar main, Build70 física, downloads, banco de dados ou biblioteca.

## Atenção ao nome DB

Já existe uma fase histórica chamada **Build70 DB — UID custody boundary**, datada 10/11/2026, em docs/WEBREADER_BUILD70_PHASE_DB_UID_CUSTODY_BOUNDARY_2026-11-10.md. Este novo trabalho é chamado **pós-DA DB2** para não sobrescrever ou contradizer essa fase. Não reiniciar a investigação.

## Evidência de partida

O usuário instalou o CX checkonlylab e relatou que continuou acessível após fechar/reabrir NewTerm. Em seguida instalou o app DA independente; transcreveu iOS 12.5.8, UID/EUID 501/501, localhost 127.0.0.1:38973 e WR_DA=NOTICE_ACCEPTED. Isso valida fisicamente o transporte de um aviso não autenticado a partir de app sandboxed, não instalação.

A consulta via GitHub connector à lista de Releases de AugustoArbulu/MangaReader12 devolveu **array vazio** em 21/11/2026 UTC. A ausência de Releases na observação NÃO equivale a 'já atualizado'. O API /releases/latest pode responder 404 por várias causas (nenhuma release, repositório privado, falta de acesso, erros de origem).

Os validadores iOS12 EXISTENTES são reaproveitados sem fork de formato: WebReaderUpdateChecker.swift, WebReaderGitHubReleaseParser.swift, WebReaderStrictJSON.swift e WebReaderUpdateManifestVerifier.swift. O parser já rejeita URL fora do repositório, metadados incompletos, digest ausente, assets ambíguos, downgrade e duplicatas. Isso só verifica coerência de metadados públicos, NÃO assinatura editorial de um publisher.

## Implementação DB2

- ci/webreader_cx_release_observer.swift: executável CLI de laboratório que compila os mesmos arquivos Swift do leitor; --selftest valida JSON sintético Build70→71 e estados de erro sem rede; --live (ação explícita) chama WebReaderUpdateChecker com usePublicGitHubReleases=true para um único GET ao endpoint EXATO https://api.github.com/repos/AugustoArbulu/MangaReader12/releases/latest, sem baixar IPA.
- A saída usa WR_DB2_OBSERVATION e declara expressamente PUBLIC_RELEASE_IS_SIGNED_PUBLISHER=NO, OWNER_TRUST_PROVISIONED=NO, PEER_AUTHENTICATED=NO, IPA_DOWNLOADED=NO, INSTALL_AUTHORIZED=NO e INSTALL_PERFORMED=NO. Mesmo metadados de build maior só viram UNTRUSTED_NEWER_METADATA_BUILD_N, não autorização de atualização.
- ci/test_webreader_cx_release_observer.py: compila o código Swift no macOS e testa parser real, flags de autoridade negativas, argumentos sem URL variável e ausência de APIs de instalador ou escrita.
- .github/workflows/chimera-db2-fixed-release-observer.yml: CI macOS executa suites existentes de parsing e checagem HTTP simulada, compila binário ARM64 iOS12 **sem assinar/empacotar**, confere travas de produção. Há opção workflow_dispatch.live_public_metadata_probe para 1 GET real, desligada por padrão; nenhum request externo do novo observador em pushes.

## Limites e gates

1. A fase DB2 **não** altera o serviço CX instalado, cuja política permanece sem qualquer rede externa; não atualiza o app DA nem Build70.
2. Em produção falta o pin editorial de publicação validado independentemente: productionPublicKeyX963=nil e independentlyProvisionedSPKISHA256=nil. Metadata de GitHub e SHA-256 não provam autoria do publisher.
3. Os testes de host não provam que o futuro helper móvel vai conseguir TLS no Chimera; a versão iOS12 é compilada apenas para verificar API compatível. Não existe IPA/DEB DB2 instalada no iPad.
4. Não existe release oficial atual à qual ligar uma checagem signed-v2; não inventar Build71 nem publicar um asset apenas para satisfazer a tela.
5. Antes de qualquer instalação continuam pendentes custódia de bytes imutável entre verificador e instalador, proteção contra replay/downgrade, consentimento confiável, assinatura nativa, backup/recovery e teste de aplicativo descartável. Keep WebReaderAppinstSocket.liveInstallationEnabled=false.

**Regra de interpretação:** uma resposta 404 de /releases/latest é INDISPONÍVEL, não ATUALIZADO; metadata sintética de Build71 jamais representa uma release real. Mesmo 200 coerente é metadata não autenticada editorialmente, nunca install authorization.

## Validação CI fechada em 21/11/2026 UTC

GitHub Actions #44859883589: **SUCCESS** no commit de código bd0095b18177fc28b1a7d86fbf89a5d253e05e0e.
https://github.com/AugustoArbulu/MangaReader12/actions/runs/44859883589

- Os testes macOS compilaram e executaram o novo observador Swift com o próprio parser e fixture sintético Build70→71; resultado aponta metadados NÃO autenticados, não autorização de IPA.
- Os testes já existentes de parser de GitHub Releases e URLSession com resposta injetada passaram, incluindo HTTP 404/403, assets inválidos, URL do asset fora do repositório, SHA ausente, múltiplos assets e sem chave editorial.
- A compilação ARM64 para deployment target iOS 12 foi aprovada; o binário de prévia permaneceu no runner. Nenhum DEB ou IPA foi publicado, assinado para distribuição ou instalado.
- As travas de produção foram verificadas: liveInstallationEnabled=false, productionPublicKeyX963=nil, independentlyProvisionedSPKISHA256=nil.
- O job live-public-metadata-only foi SKIPPED intencionalmente, porque não houve workflow_dispatch com a opção explícita. Este resultado NÃO prova uma transação HTTPS real do novo executável em CI nem transporte TLS no iPad.

A lista de Releases foi consultada separadamente pelo conector GitHub: [] no momento da verificação. Logo, não há Release observável para o canal público neste momento, mas isso não demonstra publicação, autenticação ou instalação. `GET /releases/latest` / status HTTP ainda não foi executado pelo novo observador.

**Decisão seguinte:** antes de ligar consultas ao serviço CX já instalado, revisar limites de rede e autenticação editorial, executar opcionalmente a checagem live somente leitura no CI, e avaliar um laboratório de HTTPS físico separado. Não transformar respostas de metadata em WRNOTE2 como se houvesse atualização verificada, não modificar o daemon físico existente e não presumir que UID mobile 501 oferece armazenamento imutável contra clientes do mesmo UID.
