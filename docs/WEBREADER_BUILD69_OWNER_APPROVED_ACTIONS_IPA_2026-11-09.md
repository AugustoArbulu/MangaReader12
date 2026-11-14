## Resultado real do primeiro empacotamento (09/11/2026)

- [GitHub Actions #42699330354](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42699330354): **SUCCESS**, job único completo, incluindo testes, Xcode 16.4, build real ARM64/iOS12, assinatura ad hoc, auditoria BB sobre os bytes finais e upload.
- [Artifact QA #13709933178](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42699330354/artifacts/13709933178), nome `WebReader-Build69-OwnerApproved-iOS12-QA-Filza`, ZIP com IPA real, SHA-256 e recibos, retenção até **23/11/2026** segundo GitHub.
- IPA interna `WebReader-Build69-iOS12-adhoc.ipa`, **17.838.738 bytes**; SHA-256 **`ba3e6e550fc91b447f489a63cb965166d14ee053c3d796b1c524bf40f5968085`**.
- Bundle ID `com.example.MangaReader12`; build 69, iOS mínimo 12.0, thin ARM64; entitlement `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`. CodeDirectory CDHash `695bc5593ce3cf05816033de0dd1007729d9049a`; preflight nativo registra integridade ad hoc e compatibilidade estática com a identidade da Build68.
- Commit de origem do artifact: `db393133a0a631e54259a94a5d0e53d24b2f7192`. Commit revisado anterior: `51d9c3713d0fb9477624aae4c8aa4b4683ad1f94`.
- A IPA e o ZIP foram extraídos e o SHA-256 do arquivo verificado novamente após o download do artifact; `Info.plist` interno confirma Build69/iOS12.
- **NENHUMA instalação física foi executada**; nenhum Release público, nenhum `main` merge, nenhum instalador Chimera ativado. O usuário deve instalar por cima da Build68 via Filza se decidir testar, e verificar biblioteca e capítulos offline. O backup portátil não inclui páginas.

---

# WebReader Build 69 — autorização para uma IPA de QA no GitHub Actions

**Autorizado pelo proprietário em 09/11/2026:** produzir e disponibilizar **uma** IPA de teste da Build 69 por GitHub Actions. Autorização limitada a compilar, assinar ad hoc uma cópia, auditar e enviar um artifact de QA. NÃO concede autorização para instalar no iPad, alterar main, publicar GitHub Release de produção ou habilitar Chimera.

## Como foi implementado

- Workflow dedicado `.github/workflows/chimera-build69-owner-approved-one-shot-qa.yml` na branch experimental; gatilho exclusivamente por **push de um arquivo de autorização único**, não por PR, agendamento ou publicação automática.
- A execução exige um commit de trigger cujo **único arquivo modificado** é `ci/build69_owner_approved_qa_trigger.txt`, com marcador de consentimento exato e SHA do commit revisado pai.
- A partir do SHA de trigger, `git archive` cria uma pasta fonte temporária; todos os testes, imagens, dependência libwebp e build Xcode iOS12 usam essa cópia, para manter o checkout original limpo.
- Xcode compila o WebReader real como `CFBundleVersion=69` e ARM64/iOS12, sem alterar `CURRENT_PROJECT_VERSION=56` do projeto versionado.
- O empacotador de uso único `ci/build69_cb_actions_qa_package.py` valida branch, ação, origem e SHA, assina uma cópia do app com entitlements iguais à instalação Build68, prepara o ZIP IPA e audita o CodeDirectory, o executável ARM64/iOS12, tamanho, SHA-256 e bundle ID pela ferramenta BB.
- O nome final só aparece depois de auditoria e hash, e é revalidado depois de publicação por links exclusivos, com rollback em falhas. O artifact leva a IPA, SHA-256, recibos de preflight e proveniência (commit/run) e fica disponível por até 14 dias.
- Esse novo fluxo é deliberadamente separado de BY/BK, que continuam proibindo empacotamento genérico no CI; não se removeu esse controle.

## Limites

GitHub Actions em repositório público não é depósito sigiloso: artifact QA é distinto de Release e tem retenção curta, mas não deve ser tratado como um arquivo confidencial. Nenhum material privado, título de biblioteca, backup, senha ou segredo editorial é enviado.

**A IPA de teste inclui a tela de Atualizações e as funções de inspeção/download manual, mas NÃO inclui instalação automática funcional.** O app mantém `WebReaderAppinstSocket.liveInstallationEnabled = false` e a chave editorial de produção ausente. O primeiro teste é instalação manual in-place, sem remover a Build68 e sem restaurar backup.

## Validação e entrega

A revisão de código/CI não substitui a validação do artifact real. O workflow deve terminar com sucesso **incluindo** upload, gerar `WebReader-Build69-iOS12-adhoc.ipa` e checksum conferível. Após transferir, revalidar a integridade e executar os 16 checks físicos no iPad, começando por biblioteca/progresso e capítulos offline com Wi-Fi desligado.

**Nunca** apagar app, limpar downloads, reindexar ou restaurar `.mr12backup` para corrigir um upgrade: o backup portátil não contém as páginas offline.
