# WebReader Build69 — Fase BK: empacotador privado com aprovação explícita

**Data:** 2026-11-09 UTC. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; [PR #90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). **Não alterar `main` nem a Build68 instalada.**

## Objetivo

Após as fases BA (compilação experimental unsigned), BB (preflight nativo de IPA ad hoc), BC (comparação de hash após transferência) e BH–BJ (preservação offline), o que falta para testar uma versão nova é **produzir um pacote privado verdadeiro** e validar sua identidade e bytes. A Fase BK **prepara a ferramenta de empacotamento, mas não a executa neste avanço e não distribui IPA**.

## Implementação

Arquivo: `ci/package_webreader_build69_private_qa_ipa.sh` (somente macOS, execução humana após consentimento específico).

O script é **bloqueado por padrão**. Exige `WR69_PRIVATE_QA_PACKAGE_APPROVAL=I-APPROVE-BUILD69-PRIVATE-QA-PACKAGING` fornecida conscientemente pelo proprietário na operação concreta. Esse marcador é uma confirmação de intenção, **não é uma chave, assinatura editorial, autenticação de identidade ou permissão para instalar**.

A execução autorizada também exige:

1. Usuário de sistema não-root, checkout da branch experimental, ferramentas macOS nativas e um `MangaReader12.app` já compilado separadamente com `CURRENT_PROJECT_VERSION=69` apenas para o build isolado.
2. Validação inicial de `Info.plist`, bundle ID, executável, ícone, iOS mínimo `12.0`, Mach-O ARM64 e invariantes de produção fechados via `ci/build69_ba_unsigned_candidate_audit.py`. O `project.pbxproj` no repositório continua em `56`.
3. Saída obrigatoriamente chamada `WebReader-Build69-iOS12-adhoc.ipa`, **fora do repositório e sem sobrescrever um arquivo existente**.
4. Cópia com `ditto` em diretório `mktemp`; assinatura ad hoc exclusivamente dessa cópia, com `ci/chimera_webreader_qa.entitlements`. A entitlement deve ser exatamente `AR5SFJC432.com.example.MangaReader12.AR5SFJC432`, igual à identidade historicamente constatada da instalação atual. A assinatura não autentica o editor.
5. `codesign --verify`, validação de identidade e criação do ZIP/IPA privado somente na pasta destino externa. Uma segunda inspeção sobre **os bytes finais** com `build66_ipa_preflight.inspect_ipa` e `build66_code_signature_gate.audit_code_signature_snapshot` exige versão 69, iOS12, SHA, estrutura ZIP, selo ad hoc e entitlements. Falhas removem o output recém-gerado, nunca arquivos do usuário.
6. Gera um `.sha256` **local**, mas não afirma ser uma fonte independente. O proprietário precisa conferir o digest e a origem por outro canal antes de transferir para Android/PC/Filza. A Fase BC revalida os mesmos bytes após cópia.
7. Não invoca `git push`, `git merge`, GitHub Releases, `upload-artifact`, `appinst`, `posix_spawn`, installer Chimera ou qualquer URL de rede.

**Não executar automaticamente:** apenas como referência futura, quando houver autorização da candidata e um macOS com app Build69 já compilado:

```bash
WR69_PRIVATE_QA_PACKAGE_APPROVAL=I-APPROVE-BUILD69-PRIVATE-QA-PACKAGING \
  bash ci/package_webreader_build69_private_qa_ipa.sh \
  /caminho/da/compilacao/MangaReader12.app \
  /fora/do/repositorio/WebReader-Build69-iOS12-adhoc.ipa
```

O sucesso do script demonstra apenas estrutura e assinatura ad hoc locais, **não** que a IPA foi assinada editorialmente por uma chave confiável, que é compatível com a instalação do iPad, ou que preserva as imagens. Não substitui os 16 checks físicos.

## Política e testes

Arquivo `ci/test_build69_bk_private_qa_packaging_gate.py`:

- Executa `bash -n` para verificar sintaxe da rotina.
- Chama o script com aprovação ausente/errada e diretório descartável. Todos os casos **devem rejeitar antes de criar qualquer arquivo**.
- Confere que os passos de cópia/assinatura acontecem só em `TMP`, que o nome de saída, a branch e a entitlement são fixos, e que as bibliotecas de preflight validam os bytes finais.
- Confere que o workflow integrado AC–BK **NÃO CHAMA O SCRIPT**, não fornece aprovação no ambiente e não envia artefatos. Apenas as políticas e testes são automáticos.

[CI integrada AC–BK #42567641859](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42567641859): verificar conclusão. O job Linux testa a negativa do empacotador e todas as políticas antigas; o macOS testa offline, assinatura **sintética de fixtures** e a compilação iOS12 sem IPA final.

## Estado

| Item | Situação |
|---|---|
| Build68 no iPad e dados do usuário | Intocados |
| Projeto fonte `CURRENT_PROJECT_VERSION` | 56 (intencional nesta fase) |
| Xcode preview 69 unsigned isolado | Testado em CI BA–BB |
| Código de empacotamento ad hoc privado | Criado, bloqueado por padrão |
| Empacotador executado sobre WebReader 69 real | **NÃO** |
| IPA Build69 pronta para download/instalação | **NÃO** |
| Root de confiança ECDSA do editor | Não provisionado |
| Automação de instalação Chimera | Desabilitada |
| PR #90 / `main` | Draft / intacta |

**Próximo passo:** concluir CI nativo BH–BK e, depois de aprovação específica do proprietário, escolher um processo privado e auditável no macOS para construir a IPA real e disponibilizá-la ao teste manual. A publicação pública e a automação de instalação permanecem etapas distintas e desativadas.
