# Build 66 — Auditoria de confiança do atualizador (06/11/2026)

Status: **DESIGN / NÃO HABILITADO**. Nenhuma instalação real, IPA nova, release ou merge.

## Base confirmada
- Build65 aprovada fisicamente: Biblioteca e capítulo legado offline preservados; não repetir esse QA.
- PR #90 aberta como Draft na branch `feat/chimera-updater-phase1-protocol-audit`.
- `WebReaderAppinstSocket.install()` rejeita incondicionalmente no cliente normal; `liveInstallationEnabled = false`. O caminho `WRINST1` só existe sob `WEBREADER_HOST_TEST`.
- `WebReaderUpdateChecker` não possui chave editorial de produção (`productionPublicKeyX963 = nil`). Há modo de consulta a releases públicos, mas isso NÃO constitui autorização criptográfica de instalação.
- `WebReaderUpdateManifestVerifier` verifica ECDSA P-256 SHA-256 e exige bundle, build crescente, mínimo iOS, hash, tamanho e URL restrita; essa verificação é feita no contexto do app, não no helper.
- O transporte TCP PING e o pareamento HMAC apenas demonstram comunicação/posse de código; não identificam com segurança o cliente nem autorizam `appinst`.

## Modelo de ameaça
Adversários relevantes: outro processo local com UID mobile, cliente IPC falsificado, resposta de GitHub manipulada, IPA substituída após download, arquivo trocado por symlink, downgrade, replay de autorização, identidade de assinatura divergente e encerramento do app durante a atualização.

## Decisões de segurança
1. **Não reutilizar** o serviço PING persistente, porta 38971 ou protocolo HMAC 38972 como endpoint de instalação.
2. O helper instalador deve validar independentemente o manifesto assinado com chave editorial pública fixada e chave privada mantida fora do repositório. Releases públicos sem manifesto assinado permanecem apenas informativos.
3. O helper deve abrir o arquivo de maneira resistente a symlink/substituição, verificar arquivo regular, limites de tamanho, SHA-256 dos bytes que serão efetivamente instalados e identidade do pacote (Bundle ID, App ID/entitlements e versão), sem confiar em caminhos ou hashes declarados pelo cliente.
4. Antes de habilitar instalação, especificar e demonstrar autenticação do cliente no Chimera iOS12. PID, UID, loopback, PONG e código HMAC isolados são insuficientes. Se não houver mecanismo defensável, permanecer no fluxo manual Filza.
5. Autorização **one-shot**, vinculada a hash/build/identidade e expiração, sem replay; confirmação inequívoca para cada operação e cancelamento seguro. A confirmação de UI não substitui a validação do helper.
6. Não executar `appinst` com caminho arbitrário do cliente; usar somente objeto previamente verificado em área controlada e não mutável pelo solicitante durante a instalação.
7. Rejeitar downgrades, reinstalações inesperadas, identidade divergente, manifesto expirado/revogado (política a definir), falhas de assinatura, interrupções e ambiguidades de parsing.
8. Nunca desinstalar WebReader antes de upgrade; preservar dados e recomendar backup antes de QA física.

## Próximo pacote de testes (sem instalação real)
- Manifesto: assinatura incorreta, chave diferente, campos duplicados, bundle errado, versão antiga, URL fora da allowlist, tamanho inválido.
- IPA: hash incorreto, bytes truncados, arquivo modificado entre verificação e uso, symlink, não-arquivo, entitlement divergente, build inconsistente.
- IPC: peer não autenticado, repetição do pedido, nonce reutilizado, timeout, pedido sem confirmação, cliente concorrente, pacote diferente do autorizado.
- Estado: queda do helper, queda do app, rollback seguro e logs sem segredos.
- Harness: FAKE-appinst e aplicativo descartável; testes iOS12 arm64 em CI. O WebReader Build65 instalado não participa.

## Gate para próxima implementação
A próxima mudança de código deve ser **somente de testes e verificador isolado**, sem remover `liveInstallationEnabled = false` e sem conectar o helper PING ao instalador. Antes de qualquer tentativa física com o WebReader, revisar identidade no dispositivo, evidências de CI e plano de backup. Nenhuma publicação automática.

## Observação de compatibilidade
O manifesto assinado atualmente restringe o nome do asset a `WebReader-iOS12-unsigned.ipa`, enquanto a Build65 de QA foi distribuída como IPA ad hoc assinada. Isso exige revisão explícita do contrato de release antes de integrar o instalador: não flexibilizar silenciosamente a URL nem aceitar IPA unsigned para upgrade.
