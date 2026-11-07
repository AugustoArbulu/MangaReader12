# WebReader Build 66 — Fase G: processos separados e identidade de código (2026-11-07)

**Projeto:** `AugustoArbulu/MangaReader12` · Branch `feat/chimera-updater-phase1-protocol-audit` · PR #90 **Draft**. Não modificar `main`, não produzir IPA nova e não instalar nada no iPad Build 65.

## Objetivo

A Fase F havia demonstrado no macOS que `LOCAL_PEERTOKEN` e `csops_audittoken` identificavam o CDHash de um filho criado por `fork()` a partir de um executável assinado. **Limite desse desenho:** filho e pai herdam a mesma imagem de código, então isso não testa um cliente executável *diferente* que abre uma conexão.

A Fase G corrige essa lacuna com **dois processos executados independentemente**, cada um assinado ad hoc. O servidor do ensaio recebe `LOCAL_PEERTOKEN` da conexão UNIX aceita, chama `csops_audittoken` e confronta o CDHash do processo que mantém a conexão aberta com uma referência obtida, **antes de abrir o servidor**, por `codesign -d --verbose=4` após `codesign --verify` no arquivo do cliente esperado.

## Implementação

| Caminho | Descrição |
| --- | --- |
| `ci/build66_separate_signed_peer_lab.c` | Programa macOS não-root com modos estritos `serve-once` e `client-once`. Socket UNIX curto em pasta temporária privada, um único cliente, prazo curto, `LOCAL_PEERTOKEN`, `csops_audittoken(CS_OPS_CDHASH)`, negação de token com `pidversion` alterado e PID cruzado. Não instala nada. |
| `ci/test_build66_separate_signed_peer_lab.py` | Compila e assina **três binários distintos** (servidor, cliente esperado, cliente diferente); executa clientes independentes, hashes falsos e cópia byte a byte. |
| `ci/build66_independent_peer_report.py` | Parser de log **não confiável** que devolve `installation_authorized=False`, `publisher_authenticated=False`, `authenticated_webreader_peer=False`, inclusive quando o CDHash coincide. |
| `ci/test_build66_independent_peer_report.py` | 30 casos de status falsificado, tokens/PIDs divulgados, campos inesperados, mensagens de instalação e estados ambíguos. |
| `.github/workflows/chimera-build66-separate-peers.yml` | CI independente em Linux/macOS. Nenhum artefato IPA/DEB nem instalador distribuído por este laboratório. |

### Matriz de testes

1. Mesmo arquivo cliente assinado e CDHash independente: deve haver `MATCH_ONLY_NO_AUTH`, **não autorização**.
2. Cliente B com código assinado diferente apresentado como cliente A: deve haver `MISMATCH_REJECTED`.
3. Cliente A com referência CDHash propositalmente adulterada: deve rejeitar.
4. Cliente B com seu **próprio** CDHash: correspondência; demonstra que verificação vincula o código em execução, não apenas que um servidor está presente.
5. Cliente A comparado com CDHash do **servidor**: rejeitado.
6. **Cópia idêntica** do cliente A executada sob outro caminho: mesmo CDHash. A igualdade não comprova identidade do publicador, origem do app, caminho original ou ausência de duplicação.
7. Referência inválida, comando não previsto ou tentativa repetida: rejeitar e não deixar listener persistente.
8. Relatórios de texto são apenas diagnóstico; não são evidência autenticada de runtime.

O servidor não lê bytes de IPA, não usa portos TCP, não solicita root e não chama `appinst`. Os caminhos, CDHashes e tokens de processos não são incluídos nos relatórios. `serve-once` recebe CDHash do harness **por argumento**: o usuário que executa o laboratório pode escolher esse valor. Portanto, este utilitário **nunca** deve ser conectado a um helper de produção.

## Fundamentos verificados

- [Apple TN3126 — Inside Code Signing: Hashes](https://developer.apple.com/documentation/technotes/tn3126-inside-code-signing-hashes): CDHash deriva do CodeDirectory, é específico do código/arquitetura e, para SHA-256, costuma ter 20 bytes truncados no campo CDHash.
- [XNU — kern_proc.c](https://github.com/apple-oss-distributions/xnu/blob/main/bsd/kern/kern_proc.c): no código-fonte publicado de `csops_audittoken`, o kernel confronta PID e versão de processo com o token, além de aplicar a política de acesso para consultar assinatura.

**Limites:** código-fonte publicado de versões modernas e testes macOS não estabelecem comportamento no **iOS 12.5.8 com Chimera**. O `LOCAL_PEERTOKEN` deve ainda ser analisado em cenários de **transferência de descritores de socket entre processos** e modificações no proprietário efetivo; obter token não demonstra origem imutável de cada mensagem individual. Uma assinatura ad hoc autentica integridade, não o publicador. Mesmo um CDHash previamente fixado e igual não substitui consentimento de instalação, verificação do manifesto e bytes do helper ou proteção do estado persistente.

## CI e próximos bloqueadores

- A execução inicial do novo workflow está em: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42344581447
- Acrescentar resultados macOS **somente quando efetivamente concluídos**; o parser Linux inicialmente passou.
- O utilitário separado de diagnóstico no iPad da Fase E/F continua **opcional**. Nenhum teste runtime no iOS12 foi relatado pelo usuário.
- Até validar autenticação do peer independentemente no iOS12 e consentimento seguro no helper, manter `WebReaderAppinstSocket.liveInstallationEnabled = false` e `WebReaderUpdateChannel.productionPublicKeyX963 = nil`.
- A Build 65 instalada e seus dados não foram tocados.

**Próximo lote técnico:** testar, em host, como a identidade observada se comporta em transferência de sockets (`SCM_RIGHTS`) e discutir arquitetura em que somente o helper escolhe release/política; não reutilizar esta prova de conceito como instalador.
