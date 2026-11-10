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

**GitHub Actions CM:** https://github.com/AugustoArbulu/MangaReader12/actions/runs/42749171758 — conferir conclusão antes de anunciar sucesso.

## Restrições preservadas

O modo de instalação automática continua desativado (`WebReaderAppinstSocket.liveInstallationEnabled=false`). Mesmo resultados positivos não autenticam o aplicativo e não estabelecem custódia de chave editorial, consentimento local, ledger anti-replay nem consumo de bytes imutáveis pelo instalador. Build70 iPad, biblioteca, offline, backups, main e releases intactos. O pacote CM é um teste opcional externo; não gera IPA WebReader.
