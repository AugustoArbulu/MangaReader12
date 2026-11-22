# WebReader — Fase J / Consolidação pós-teste físico iOS 12.5.8

**Data:** 2026-11-07 · **Repositório:** `AugustoArbulu/MangaReader12`  
**Branch:** `feat/chimera-updater-phase1-protocol-audit` · **PR:** #90, Draft, com base `main`  
**Build em uso:** 65, iPad com Chimera; biblioteca, capítulos e offline testados pelo proprietário e preservados.

## 1. Decisão técnica após o ensaio no iPad real

O proprietário executou `/usr/local/bin/webreader-csopsprobe66 selftest` como usuário `mobile` no iOS 12.5.8. Resultado:

```text
WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only
PROBE UNIX_PEERTOKEN=UNAVAILABLE AUTHORIZATION=DENIED
PROBE CSOPS_TOKEN_BINDING=NOT_TESTED AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithAuditToken=MISSING AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCopyGuestWithAttributes=MISSING AUTHORIZATION=DENIED
PROBE SECURITY_SecCodeCreateWithPID=MISSING AUTHORIZATION=DENIED
FINAL_INSTALL_AUTHORIZATION=DENIED
```

O diagnóstico foi executado, mas `LOCAL_PEERTOKEN` não retornou uma estrutura utilizável. O programa **não tentou** `csops_audittoken` sem token; portanto `NOT_TESTED` não significa que essa syscall falhou por si só. Os três símbolos de Security consultados estavam ausentes nesse runtime. O programa original não exibe `errno`, então **não inferir** a causa exata (API não suportada, permissão, tamanho, ambiente etc.).

A Fase I também provou no **macOS**, usando A e B escrevendo em um mesmo `SOCK_STREAM`, que os bytes da primeira mensagem podem ser lidos com o token do último remetente B. Portanto `LOCAL_PEERTOKEN` amostrado após `recv` **não autentica a autoria criptográfica de cada mensagem** quando há dados no buffer, independentemente da disponibilidade da API no iOS12.

**Conclusão operacional:** `LOCAL_PEERTOKEN` + `csops_audittoken` não constitui a política de autenticação do atualizador no Chimera. Não promover os ensaios de macOS a autorização de instalar. Não habilitar um daemon root ou tentar executar o diagnóstico como root.

## 2. Entregas concretas deste lote

### A. Política codificada para o resultado físico

Arquivos:
- `ci/build66_ios12_physical_capability_policy.py`
- `ci/test_build66_ios12_physical_capability_policy.py`

Parser exato para as sete linhas realmente observadas, usando a infraestrutura de relatórios da Fase E. Recusa dados inesperados, tokens/PIDs incluídos no log, campos de autorização, texto forjado e observações sem usuário `mobile`. A saída permanece explicitamente `installation_authorized=False`, `device_report_attested=False` e `root_escalation_permitted_for_diagnostic=False`. Mesmo um resultado futuro `MUTATION_REJECTED` de um processo de laboratório não significa identidade do WebReader.

### B. Revisão manual de release v2 assinado, sem instalação

Arquivos:
- `ci/build66_manual_review_receipt.py`
- `ci/test_build66_manual_review_receipt.py`

Um host de QA, usando chave pública P-256 cuja impressão digital SPKI já foi **pinada independentemente**, pode verificar um manifesto v2, o caminho exato `WebReader-Build{N}-iOS12-adhoc.ipa`, os bytes SHA-256/estrutura da IPA e a progressão de build. Somente então produz um recibo imutável com nome de arquivo e SHA-256 para **revisão humana**. O recibo não divulga caminhos pessoais, não permite install e exige nova checagem do hash após a transferência. A chave usada nas suítes é efêmera de teste: **não existe chave editorial de produção no app**.

### C. Corrigido o contrato de nome de IPA entre descoberta e download

`MangaReader12/Core/WebReaderGitHubReleaseParser.swift` agora reconhece **exatamente** um dos dois contratos conhecidos, vinculados à mesma tag `buildN`:

- legado v1: `WebReader-iOS12-unsigned.ipa`;
- ad hoc v2: `WebReader-BuildN-iOS12-adhoc.ipa`.

Se ambos aparecem no mesmo Release, se há entradas duplicadas ou se nome/URL divergem, **rejeitar por ambiguidade**. Nunca escolher silenciosamente um deles.

`MangaReader12/Core/WebReaderIPAStager.swift` foi alinhado ao mesmo contrato de URLs. Antes, encontrar um release v2 poderia dar certo na consulta, mas falharia com `invalidRelease` ao tentar baixar; o stager ainda exigia o arquivo legado. Agora o download é permitido apenas para os dois caminhos exatos; SHA-256, tamanho e estrutura ZIP/Info.plist continuam obrigatórios antes de permitir compartilhamento manual. O programa **nunca executa appinst**.

### D. Diagnóstico de GitHub privado e interface mais precisa

`MangaReader12/Core/WebReaderUpdateChecker.swift` não classifica mais HTTP **404** de `releases/latest` como “atualizado”. Uma resposta 404 pode indicar ausência de release, repositório privado ou falta de autorização — **não prova** que não exista build mais nova. O resultado agora é `unexpectedHTTPStatus(404)`, sem iniciar download.

A tela `MangaReader12/UI/WebReaderAppUpdatesViewController.swift` diferencia integridade de SHA/ZIP de **autenticidade editorial**. Os rótulos dizem agora “Baixar e conferir IPA” e “Compartilhar IPA conferida”, sem insinuar que um digest do GitHub autentica a assinatura do editor. Metadados públicos do GitHub por HTTPS não substituem uma assinatura independente do publicador. A instalação pelo Chimera permanece indisponível; a alternativa é compartilhar a IPA conferida e escolher, manualmente, como instalar pelo Filza após backup.

### E. Suítes e integração de CI

- `ci/test_native_webreader_update_checker.py` inclui casos Swift reais para release ad hoc v2, metadados ambíguos, nomes duplicados, hash inválido, troca de nome, URI falsa, 404 privado/inacessível, e versão v1 preservada.
- `ci/test_native_webreader_ipa_stager.py` exerce download da IPA v2 com `URLProtocol` sintético, bytes de ZIP válidos, exportação sem appinst e rejeição de URL de outro build, domínio estranho, query e fragmento.
- `.github/workflows/chimera-build66-preflight.yml` incorpora as duas suítes Python com manifesta/IPA assinadas sintéticas, exige execução nativa Swift em macOS e verifica que as duas travas de produção permanecem desligadas.

**Status final de QA do código desta fase:** workflow
[WebReader Build66 IPA Preflight Security QA #189](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42349174443),
run `42349174443`, **SUCCESS nos dois jobs**:

- **309 testes Python** aprovados no job Linux, incluindo **33** casos de
  relatório do iPad real e **22** testes do recibo de release v2 assinado
  para revisão manual.
- macOS: verificador nativo Swift/Security.framework, Swift URLSession com
  GitHub Release v1/v2 e HTTP 404, Swift `WebReaderIPAStager` com download
  simulado de IPA v2 e negativa de URL fora da política, parser nativo
  independente de GitHub Releases, auditoria de assinatura de código e
  compilação do caminho `WebReaderAppinstSocket.install` que rejeita sempre.
- Testes usam chaves P-256 efêmeras e URLs via `URLProtocol` local, sem
  baixar releases reais, sem publicar IPA, sem usar `appinst`.
- O workflow [#186](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42348975466)
  também passou em ambos os jobs após as correções de Swift/stager anteriores.
- As verificações específicas de Build65 arquivada e as Fases E-I de
  diagnóstico já haviam passado; **o resultado físico do iPad continuou
  `UNIX_PEERTOKEN=UNAVAILABLE`** e não é alterado por testes macOS.

**Limite de QA:** os testes Swift acima executam no macOS com fixtures.
Não houve nova execução do WebReader modificado em um iPad iOS12 nem
uma nova IPA Build66 aprovada fisicamente. O workflow geral `iOS 12
Milestone 0` não concluiu uma compilação integral nessa sequência de
commits (execuções canceladas), portanto não afirmar que a build iOS
completa já passou.

## 3. Separação rigorosa de confiança

| Componente | Confirma | Não confirma |
| --- | --- | --- |
| PING/PONG mobile da Build 65 | Transporte de comunicação em dispositivo real | Identidade de código ou permissão para instalar |
| Diagnóstico físico `UNIX_PEERTOKEN=UNAVAILABLE` | Opção de token não utilizável no ensaio como mobile | Inexistência de qualquer outro mecanismo seguro no iOS |
| GitHub Releases API + digest SHA-256 | Consistência dos bytes com os metadados retornados via HTTPS | Assinatura editorial independente; repositório privado acessível |
| Manifesto v2 assinado + SPKI pinado | Conteúdo aprovado pela chave previamente confiada pelo host de QA | Custódia da chave de produção, consentimento e identidade no iPad |
| `WebReaderNativeIPAAuditor` | Hash e estrutura/versão/bundle da IPA | Assinatura do publicador ou segurança de um futuro helper |
| Exportação pelo menu Compartilhar | Usuário pode transportar o arquivo validado | Que o arquivo não mudou após a transferência |
| Comando `appinst` | **NÃO UTILIZADO NESTA FASE** | Não deve ser ativado por resultado de diagnóstico |

## 4. Bloqueadores honestos antes da instalação automática

1. **Custódia editorial da chave:** não há chave pública de produção aprovada/pinada no app; `productionPublicKeyX963 = nil`. Não criar uma chave privada fictícia ou aplicar a chave sintética dos testes.
2. **Autorização do helper no Chimera:** o token por socket não serve como autenticação de pedido. Precisaria existir autorização independente com ação explícita do proprietário, proteção contra replay/rollback e acesso a bytes que o solicitante não possa substituir.
3. **Validação pelo executante:** um futuro instalador deve abrir e validar a IPA **novamente**, no contexto que realmente instala, e garantir que os bytes usados sejam os mesmos que foram verificados.
4. **Distribuição autêntica e compatível com repositório privado:** GitHub Releases privado sem credenciais pode responder 404. Não contornar isso passando cookies/tokens inseguros para uma ponte privilegiada.
5. **QA físico de nova build:** preservar e testar biblioteca, cache offline e dados do WebReader antes de qualquer troca de versão. A Build 65 continua instalada, e esta fase **não produziu IPA nova**.

## 5. Próxima decisão sugerida

Seguir em direção a uma **Build 66 de QA não privilegiada** que mostre mensagens de origem e tratamento correto da consulta GitHub (404 e nomes v2), com exportação manual. Antes de disponibilizar qualquer IPA, verificar workflow iOS completo e decidir com o usuário quando testar no aparelho, garantindo backup e substituição não destrutiva.

Não reabrir fases de `SCM_RIGHTS`/peer token indefinidamente se não houver hipótese diretamente relevante para um mecanismo de autorização alternativo. O resultado negativo já orientou a arquitetura.

**Proteções permanentes:** PR #90 Draft, `main` intocada, `WebReaderAppinstSocket.liveInstallationEnabled = false`, `WebReaderUpdateChannel.productionPublicKeyX963 = nil`, sem instalador root, sem download real do Comix, sem ativação automática e sem modificar a Build65.
