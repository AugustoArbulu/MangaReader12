# WebReader — Fase CM: diagnóstico físico iOS12 com causas específicas de falha

**Data:** 10/11/2026. **Branch:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90 Draft**; nenhuma mudança em main, release de produção, WebReader Build70 instalado ou appinst.

## Evidência física recebida

A Fase CL foi executada no iPad iOS12.5.8 com Chimera/NewTerm 2. Resultados reportados:

~~~text
OBSERVATION_a=INCONCLUSIVE AUTHORIZATION=DENIED
OBSERVATION_b=INCONCLUSIVE AUTHORIZATION=DENIED
OBSERVATION_c=MINCONCLUSIVE AUTHORIZATION=DENIED
~~~

**Interpretação:** não houve observação do padrão controlado esperado. O resultado não prova incompatibilidade definitiva e não permite tratar o helper como autenticador. A string `MINCONCLUSIVE` não existe no shell CL original; pode ter sido transcrita incorretamente. Se realmente emitida no dispositivo, deve ser considerada saída não prevista, jamais autorização.

**Causa confirmada no código:** o script CL convertia todas as respostas do processo servidor diferentes de `MATCH_ONLY_NO_AUTH` e `MISMATCH_REJECTED` em `INCONCLUSIVE`, escondendo uma possível falha de token ou CDHash. Repetir a versão CL não acrescentaria informação.

## Implementação CM

- Novo `ci/package_chimera_signed_peer_cm.py`: reutiliza três executáveis ARM64 de teste, assinados ad hoc separadamente. O runner exibe somente enumerações previstas: `TOKEN_UNAVAILABLE`, `CSOPS_MISSING`, `CDHASH_UNAVAILABLE`, `TOKEN_MUTATION_UNSAFE`, `CROSS_PID_UNSAFE`, `PROTOCOL_REJECTED`, `TRANSPORT_FAILED`, além dos pares match/mismatch e falhas de transporte local.
- Relatório exige **exatamente um RESULT** e **exatamente um FINAL_INSTALL_AUTHORIZATION=DENIED** do servidor para classificar qualquer enumeração. Linhas inesperadas ou duplicadas retornam INCONCLUSIVE. Nunca imprime token, CDHash, UID, PID, caminho, logs ou detalhes pessoais.
- Atualiza exclusivamente o pacote diagnóstico `com.example.webreader.peercl` da versão 0.1.0 para **0.2.0**; o mesmo comando `webreader-peercl-report` funciona após upgrade do pacote via Sileo. O WebReader Build70 não é reinstalado ou modificado.
- Parser estrito `ci/build71_cm_peer_reason_report.py` recusa `MINCONCLUSIVE` e relatórios forjados, malformados ou que indiquem autorização.
- Testes negativos Linux `ci/test_build71_cm_peer_reason_report.py`; auditoria macOS de Mach-O ARM64, assinaturas, hashes embutidos, entitlements iOS12 e pacote DEB em `ci/test_chimera_signed_peer_cm_deb.py`, reutilizando a auditoria independente CL.
- Workflow adicional `.github/workflows/chimera-ios12-phase-cm-peer-reason.yml`; não modifica fluxos de produção.

## Teste físico opcional

Após instalar **somente o pacote CM auditado** no Sileo, execute manualmente no NewTerm 2 como usuário mobile:

~~~sh
webreader-peercl-report
~~~

Envie apenas as três linhas `OBSERVATION_a/b/c`, todas com `AUTHORIZATION=DENIED`.

| Resultado | Possível significado |
| --- | --- |
| `TOKEN_UNAVAILABLE` | Kernel/sandbox não forneceu token do peer do socket ao diagnóstico |
| `CSOPS_MISSING` | Símbolo csops_audittoken não disponível no processo |
| `CDHASH_UNAVAILABLE` | Token recuperado, consulta da assinatura recusada |
| `TOKEN_MUTATION_UNSAFE` | Implementação aceitou token alterado, insegura |
| `CROSS_PID_UNSAFE` | Implementação aceitou PID incorreto, insegura |
| `TRANSPORT_FAILED`, `SOCKET_UNAVAILABLE`, `CLIENT_FAILED` | Problema com o transporte/local IPC |
| `MATCH_ONLY_NO_AUTH / MISMATCH_REJECTED / MATCH_ONLY_NO_AUTH` | Padrão de laboratório favorável, mas NÃO identidade do WebReader real |

**GitHub Actions CM final:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42749403094 — **SUCCESS 2/2** (Linux threat-model e macOS assinaturas ARM64/iOS12, auditoria DEB). A primeira execução teve falha puramente de codificação ASCII do campo de nome do pacote, corrigida antes desta execução aprovada.

**Artefato auditado independentemente e recuperado:** `WebReader-Chimera-PhaseCM-PeerReason-iOS12.deb`, **14.200 bytes**, SHA-256 `6284e8eb85eeb54353d23a028053a3c5f51f6917f252bc332cb400a53f2c9587`; `.deb.sha256` bate com SHA real, somente `debian-binary`, `control.tar.gz` (apenas `./control`) e `data.tar.gz` (três CLI Mach-O ARM64 e script). Controle Debian versão `0.2.0`, pacote `com.example.webreader.peercl`; nenhum script pós-instalação, nenhum binário `appinst`, nenhum opcode `WRINST1`. [Artefato temporário CI CM](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42749403094), disponível até 24/11/2026. O testador físico **ainda não foi repetido** depois da correção.

## Resultado físico CM confirmado pelo proprietário — 10/11/2026

O proprietário executou o diagnóstico **CM 0.2.0** no iPad com Chimera e informou que os casos **A, B e C retornaram**:

~~~text
OBSERVATION_a=TOKEN_UNAVAILABLE AUTHORIZATION=DENIED
OBSERVATION_b=TOKEN_UNAVAILABLE AUTHORIZATION=DENIED
OBSERVATION_c=TOKEN_UNAVAILABLE AUTHORIZATION=DENIED
~~~

A comunicação Unix local chegou ao servidor nativo e o servidor emitiu exatamente um código classificado, validado pelo wrapper CM. Isso elimina a hipótese de que o resultado CL era **apenas** o filtro genérico do script.

**Cuidado técnico:** no código nativo `ci/build66_separate_signed_peer_lab.c`, `TOKEN_UNAVAILABLE` é **um único estado para quatro casos**: `getsockopt(SOL_LOCAL, LOCAL_PEERTOKEN)` falhou; comprimento retornado difere do `sizeof(audit_token_t)`; campo numérico do PID é zero; ou campo numérico de versão do PID é zero. Não foi coletado `errno` nem distinguida qual dessas verificações falhou. Portanto, **não** afirmar que o kernel iOS12 inteiro não suporta `LOCAL_PEERTOKEN`; também não afirmar que se obteve token com sucesso. A constante `LOCAL_PEERTOKEN=0x006` é a definida em `sys/un.h` Darwin, mas disponibilidade no iPad físico permanece não comprovada.

Diante de falha idêntica nos três casos, esta rota de **autenticação de processo via audit token não pode ser usada como bloqueio ou autorização** do helper. Ausência de sinal útil não significa que o app seja falso; é simplesmente um gate NÃO PROVADO. `getpeereid`, `LOCAL_PEERPID`, TCP loopback e HMAC de pareamento também não bastam para demonstrar identidade editorial do processo. Nenhuma instalação foi realizada ou autorizada.

**Direção revisada:** avançar com arquitetura de pedido não confiável `request-check-only`, no qual a ligação IPC não transporta parâmetros capazes de instalar, e um futuro helper só seria autorizado a agir depois de obter e verificar uma release **independentemente**, usando trust anchor do proprietário provisionado fora do app, bytes exatos, proteção contra replay/downgrade e confirmação confiável do usuário. Mesmo isso permanece apenas design até haver implementação e QA física. Evitar exigir novo DEB apenas para distinguir `errno` quando isso não desbloqueia o fluxo de atualização.

## Restrições preservadas

O modo de instalação automática continua desativado (`WebReaderAppinstSocket.liveInstallationEnabled=false`). Mesmo resultados positivos não autenticam o aplicativo e não estabelecem custódia de chave editorial, consentimento local, ledger anti-replay nem consumo de bytes imutáveis pelo instalador. Build70 iPad, biblioteca, offline, backups, main e releases intactos. O pacote CM é um teste opcional externo; não gera IPA WebReader.
