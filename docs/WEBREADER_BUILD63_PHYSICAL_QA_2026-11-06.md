# Build 63 — QA físico de correspondência de PID no iOS 12.5.8

Data: 2026-11-06. Contexto: iPad com Chimera. Relato confirmado pelo usuário.

Ao executar `/usr/local/bin/webreader-peerprobe63 selftest` como usuário mobile, o diagnóstico retornou:

- `PROBE TCP_LOOPBACK PEER_PID=MATCH AUTHORIZATION=DENIED`
- `PROBE UNIX_LOCAL PEER_PID=MATCH AUTHORIZATION=DENIED`

Interpretação: os dois transportes forneceram o PID esperado no experimento CLI controlado. `AUTHORIZATION=DENIED` é obrigatório por design, inclusive nos casos de sucesso. O teste não autentica o app WebReader, não demonstra conectividade por AF_UNIX a partir do sandbox do aplicativo, não autoriza instalações e não comprova capacidade de atualização in-app.

Próxima investigação: token de auditoria do kernel associado a socket local e testes de origem forjada, sem integrar instalador. Preservar o WebReader Build 56, o PING Build 61, a branch main e os dados do usuário.