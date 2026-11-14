# WebReader Build70 — Fase DF: preflight estático dos executáveis Mach-O ARM64 para iOS 12

**Data:** 10/11/2026. **Branch experimental:** `feat/chimera-updater-phase1-protocol-audit`. **PR #90:** Draft, sem merge na `main`. O iPad iOS12.5.8 mantém a Build70 estável, biblioteca, favoritos e capítulos offline intocados.

## Motivação e salto concreto

A DE introduziu dois candidatos C *somente leitura* com rótulos `MOBILE_CANDIDATE` e `HELPER_CANDIDATE`; ambos leem apenas a identidade de seu próprio processo, não autenticação de peer. Os testes anteriores provaram a consistência de um relatório host, mas ainda faltava verificar propriedades **do executável Mach-O ligado pelo Xcode para iOS12**, não apenas do código-fonte ou de um objeto C.

A DF cria um gate de ABI **estático e negativo** entre compilação e eventual inspeção física: um candidato malformado ou vinculado à plataforma errada é recusado. Mesmo um candidato aprovado permanece **não assinado, não implantado e sem autorização**.

## Arquivos

- `ci/build70_df_ios12_macho_preflight.py`: parser offline de cinco transcrições de ferramentas Apple (`file`, `otool -hv`, `otool -l`, `otool -L`, `nm -u`). Não executa o binário, não possui chamadas de subprocesso, rede, assinatura ou instalação. Exige formato Mach-O 64-bit executable arm64; header ARM64/EXECUTE/PIE; exatamente uma declaração `LC_BUILD_VERSION platform IOS minos 12.0` ou `LC_VERSION_MIN_IPHONEOS version 12.0`; dependência única na `/usr/lib/libSystem.B.dylib`; imports limitados aos esperados da CLI de identidade do próprio processo.
- `ci/test_build70_df_ios12_macho_preflight.py`: **17 testes offline** com fixtures de relatórios de ferramentas, que exercitam minOS iOS 11/12.1/13/17/18, destinos macOS e simulador, falta de PIE, arquivo não executável, bibliotecas externas, símbolos de socket, fork, appinst, instalação ou leitura de arquivos, duplicatas, truncamento e estrutura de report malformada.
- `.github/workflows/chimera-build70-phase-df-macho-preflight.yml`: job Ubuntu e job macOS para os testes offline. Um terceiro job seleciona Xcode16.4 e **compila e linka efetivamente** dois perfis C da DE com `-arch arm64 -miphoneos-version-min=12.0`; gera transcrições dos binários e passa pelo mesmo parser DF. Nenhum executável/asset/IPA/DEB é publicado, assinado ou executado no dispositivo.

## Protocolo de bloqueio

`DFPreflight` retorna `HOST_STATIC_ABI_ONLY_NOT_DEVICE_AUTHORIZED` quando todos os metadados host estão conformes, mantendo em `false`: `code_signature_validated_on_ios12`, `app_sandbox_entitlements_validated`, `actual_ipad_execution_proven`, `ios12_helper_identity_proven`, `ipc_peer_authenticated`, `editor_trust_provisioned`, `owner_install_consent_verified`, `installation_authorized` e `installation_performed`.

O conjunto de símbolos não é uma whitelist universal para todo o app: é **específico para os dois pequenos executáveis da DE**. Um símbolo inesperado é motivo para revisão, não para ampliar silenciosamente permissões. As bibliotecas permitidas são igualmente conservadoras; se o Xcode produzir uma dependência adicional legítima, verificar e documentar antes de mudar a política.

Essas restrições não são substituto para codesign/entitlements. As transcrições de `file` e `otool` são bytes de diagnóstico consumidos pelo teste, não prova de origem criptográfica. A CI só pode sustentar que o executável efêmero produzido por seu próprio runner apresenta propriedades ABI esperadas em análise estática. Não pode inferir compatibilidade dinâmica nem funcionamento no iPad.

## O que falta para chegar ao iPad

1. **Identidade de processo real:** comprovar, *no contexto real do futuro serviço*, UID/GID e seus privilégios, e medir separação em relação ao WebReader instalado. Executar o binário com rótulo `HELPER_CANDIDATE` no NewTerm não comprova que um helper independente exista.
2. **Código assinado e sandbox:** atestar a origem e a assinatura do programa efetivamente executado; conferir entitlements e as regras efetivas do sandbox iOS12/Chimera. Um helper privilegiado que recebe IPC não autenticado seria inseguro.
3. **Custódia protegida:** o app não pode conseguir alterar o diário/lock e seus ancestrais, nem limpar uma quarentena por conta própria; também são necessários anti-replay/rollback e prova de que trabalhadores anteriores pararam.
4. **Cadeia de instalação separada:** publisher production-v2 com chave/fingerprint reais revisados; origem fixa, SHA e code seal da IPA; os mesmos bytes até o instalador Apple; consentimento local verdadeiro. `WRCHK2\n` continua aviso de checagem passivo, nunca instrução para instalar.
5. **Ciclo de vida Chimera:** o jailbreak semi-untethered precisa ser reativado após reboot, portanto o WebReader deve falhar fechado se o serviço não estiver presente. Não prometer atualizações quando o helper estiver indisponível.

**Hard stops de produção preservados:** `WebReaderAppinstSocket.liveInstallationEnabled=false`, `WebReaderUpdateChannel.productionPublicKeyX963=nil`, `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256=nil`. Não modificar `main`, publicar Releases, IPAs, DEBs ou iniciar instalação.

**CI DF:** preencher a aprovação somente depois de examinar os logs Linux/macOS e o job Apple da análise de binário real. Caso haja falha de símbolo/import ou ABI, manter o bloqueio e corrigir sem promover o binário a uso físico.
