# WebReader Build 67 — Fase M: importação local e pacote de QA privado

**Data:** 2026-11-08 UTC
**Branch:** feat/chimera-updater-phase1-protocol-audit
**PR:** #90, Draft, base main.
**Build física estável:** 66, aprovada pelo usuário após atualização manual da Build65.

## 1. Resultado que motivou a fase

O proprietário confirmou que a Build66 funciona em iPad iOS12.5.8 com
Chimera, preservando biblioteca e leitura de capítulos baixados sem Wi-Fi.
Esse resultado foi salvo em
docs/WEBREADER_BUILD66_PHYSICAL_QA_APPROVAL_2026-11-08.md.

O repositório privado não garante acesso anônimo a GitHub Releases/Actions:
a API pública pode responder 404 sem que isso prove que não há versão nova.
Nunca colocar senhas, cookies ou tokens do GitHub no cliente ou helper.

O novo fluxo é uma alternativa **manual e sem rede** para QA de futuras IPAs
obtidas pelo proprietário através do Filza/Arquivos. **Não é uma instalação
automática e não é uma solução definitiva de autenticidade editorial.**

## 2. Novo componente Swift nativo: review local de IPA

O código foi acrescentado ao arquivo já compilado
MangaReader12/Core/WebReaderIPAStager.swift, sem modificar formatos da
biblioteca, download de capítulos, extensões ou banco de dados.

WebReaderLocalIPAReviewer.importForReview recebe uma URL de arquivo,
um Build esperado e o SHA-256 informado pelo usuário.

Controles de segurança:
- Apenas IPA local de tipo regular e extensão .ipa.
- Build maior que o instalado (sem downgrade, sem versões inventadas no
  manifesto, números positivos e limitados).
- SHA-256 completo, exatamente 64 caracteres hexadecimais.
- Tamanho estritamente positivo e limitado a 512 MiB.
- Cópia isolada no Application Support/WebReaderLocalQAImports, com UUID.
- Nova verificação após copiar, usando WebReaderNativeIPAAuditor:
  SHA real, ZIP completo, caminhos/entradas seguros, executável,
  Info.plist, Bundle ID, Build e versão mínima iOS.
- Qualquer falha remove somente a cópia temporária recém-criada.
- A ação Compartilhar revalida os mesmos bytes imediatamente antes
  de apresentar o compartilhamento iOS.
- A ação Descartar remove apenas a cópia de QA previamente registrada
  naquela pasta; não remove a IPA original, biblioteca ou downloads.

O recibo sempre carrega os estados:
publisherAuthenticated=false,
installationAuthorized=false,
installationPerformed=false.

A origem .manualLocalFile foi separada de .publicGitHubRelease e
.signedManifest; uma coincidência de SHA no arquivo **não autentica o
editor**, mesmo que o hash seja apresentado em GitHub Actions.

## 3. Nova interface iOS12, sem permissão privilegiada

A tela Ajustes > Atualizações do WebReader passou a ter a seção
IPA LOCAL (ARQUIVOS OU FILZA), inexistente nas builds descartáveis IPC.

As quatro ações da seção são:
- Importar IPA local para conferir: alerta com Build e SHA, seguido de
  UIDocumentPicker em modo importação.
- Compartilhar IPA local conferida: revalida o arquivo e abre
  UIActivityViewController, sem instalar.
- Copiar SHA-256 conferido: coloca o checksum na área de transferência.
- Descartar cópia local de QA: descarta apenas arquivo temporário do
  novo módulo.

Essa seção funciona sem chave editorial de produção e sem credenciais
GitHub, mas está restrita a QA manual. Não chama appinst, não gera
comandos de terminal e não envia arquivos a serviços externos.

## 4. Testes automatizados

A execução
https://github.com/AugustoArbulu/MangaReader12/actions/runs/42444998964
foi **SUCCESS**, commit de código 29aa75e324d7aed07e5ec6e6949b5e6fb7a8d90f.

- Linux: 12 testes do contrato de interface/sem privilégios e
  regressões da UI e da biblioteca previamente estável.
- macOS: suíte Swift nativa com 16 casos negativos de arquivo,
  downgrade, link simbólico, SHA inválido, pacote adulterado,
  bundle incorreto e iOS incompatível.
- O teste Swift validou uma cópia, adulterou os bytes após a
  verificação inicial e confirmou recusa na reverificação.
- Testes anteriores do stager HTTPS, do parser GitHub,
  da assinatura de manifesto e da recusa de appinst foram executados.
- Compilação completa Debug e Release para ARM64 iOS12:
  ambos BUILD SUCCEEDED.
- Nenhuma IPA foi produzida/instalada/publicada nesse workflow;
  foi compilado o código experimental.

## 5. Build66 congelada; Build67 com entrega separada

A Build66 que o usuário instalou foi gerada no GitHub Actions
#42351270670 (artifact 13565424419); SHA da IPA:
49ce402e6efba0aaad891d811e3b76bb78d02b627b5b8ad4fb2e8563aed51afd.

Seus dois workflows de distribuição foram congelados, eliminando
gatilhos push e exigindo o commit antigo 0939a5d7a480b2daa18d5a653a8ecf69f305f013.
Dessa forma, novas alterações não poderão ser rotuladas acidentalmente
como Build66. A Build66 e o banco de dados instalado permanecem intactos.

A Build67 ganhou scripts de empacotamento e auditoria próprios:
- ci/package_webreader_build67_rehearsal.sh
- ci/audit_webreader_build67_rehearsal.py
- ci/test_build67_rehearsal_readonly_gate.py
- ci/build67_private_manual_qa_delivery.py
- ci/test_build67_private_manual_qa_delivery.py
- .github/workflows/chimera-build67-private-manual-qa.yml
- docs/WEBREADER_BUILD67_MANUAL_QA_CHECKLIST_2026-11-08.md

O novo pipeline executa compilação iOS12, assina ad hoc a cópia
Build67, compara com o entitlement já aprovado, verifica SHA/estrutura
e exige revalidação do conteúdo antes de disponibilizar um artifact
privado e temporário. Não publica GitHub Release e não instala no iPad.

**Pipeline privado de Build67 validado e entrega realizada:**
workflow [#42445422628](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42445422628)
terminou **SUCCESS** no commit df6d8a44b56ed2fe693df4ad114b3de885f69542.
Compilou o aplicativo completo Debug e Release para ARM64/iOS12,
empacotou a cópia com versão 67, auditou a assinatura ad hoc
e submeteu os bytes à segunda verificação rigorosa do script de entrega.

- Artifact privado: WebReader-Build67-Private-ManualQA-Filza-iOS12
- Artifact ID: 13603049559 (retention: 14 dias)
- IPA: WebReader-Build67-iOS12-adhoc.ipa
- IPA bytes: **17.777.098**
- SHA-256: **56fca5893ef3c713bf91b163fc8fe11d6b7ee6cfc6614191f0b754dadb39e897**
- Bundle ID: com.example.MangaReader12
- Application identifier: AR5SFJC432.com.example.MangaReader12.AR5SFJC432
- Info.plist CFBundleVersion: 67; MinimumOSVersion: 12.0
- Publicador autenticado independentemente: NÃO
- Instalação automática/privilegiada: NÃO

O ZIP publicado no Actions foi baixado em um contêiner separado,
inspecionado, e a IPA dele foi extraída para disponibilização direta
nesta conversa. O SHA-256 recalculado da IPA coincide exatamente com
o .sha256 e com os dois JSONs do pacote. O Info.plist do arquivo dentro
da IPA foi conferido novamente, confirmando Build67, bundle e mínimo iOS.

O artifact contém a IPA, o checksum, o JSON da auditoria,
o JSON do gate de entrega e o checklist de QA físico. Nenhuma
chave editorial de produção foi configurada, nem GitHub Release publicado.

## 6. Limites ainda pendentes antes de autoinstalação

- Chave editorial de produção permanece ausente:
  WebReaderUpdateChannel.productionPublicKeyX963 = nil.
- O método LOCAL_PEERTOKEN não forneceu token no iOS12/Chimera mobile,
  e a Fase I demonstrou que ele não autentica bytes de cada mensagem
  em buffers compartilhados no macOS.
- WebReaderAppinstSocket.liveInstallationEnabled permanece false.
- Ainda não há política independente de consentimento, seleção dos
  bytes pelo executante, proteção durável contra replay/rollback e
  autenticação robusta do editor.
- Build67 **não foi testada no iPad** quando este documento foi criado.
  O usuário ainda usa a Build66 funcional.
- Uma IPA ad hoc não é assinatura de publicador; o SHA de um pacote
  privado só serve como referência de integridade após transferência.

## 7. Próximo marco

A IPA de QA Build67 está pronta para teste manual, **não aprovado fisicamente**.
O proprietário deve primeiro exportar e guardar fora do iPad um backup
da biblioteca da Build66, verificar o SHA do pacote e somente então,
se desejar, atualizar pelo Filza sem desinstalar o aplicativo.
Confirmar versão nos Ajustes, leitura offline e biblioteca antes de
testar a seção de IPA local. As cópias locais de QA ficam em uma
pasta separada e podem ser descartadas pela própria tela; evitar
acúmulo de arquivos temporários grandes.

Não confundir download de artifact privado com GitHub Release
assinado. O autor/editor não é autenticado apenas pelo digest.
Nenhum teste físico da Build67 deve ser considerado aprovado sem
confirmação direta do proprietário. Preservar main e PR #90 Draft.
