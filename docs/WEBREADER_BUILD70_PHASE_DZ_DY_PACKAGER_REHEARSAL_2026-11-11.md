# WebReader — Fase DZ: ensaio descartável do empacotador real da Build71

Data: **11/11/2026**. Branch: `feat/chimera-updater-phase1-protocol-audit`. PR #90 permanece **Draft**. Não modificar `main`. Não publicar nem instalar uma IPA71 sem uma autorização específica de entrega e uma autorização de instalação separada.

## Lacuna descoberta

A Fase DV já tinha comprovado que o WebReader inteiro podia ser compilado como Build71 Release ARM64/iOS12 e assinado temporariamente no macOS, mas o **código exato do novo empacotador** `ci/build71_owner_approved_actions_qa_package.py` nunca tinha feito o percurso completo em máquina Apple. Apenas seus 18 testes de segurança rodaram em Linux. Isso deixa risco de falhas no método de hardlink, arquivo final, double-check e proveniência durante a primeira entrega autorizada.

## Ensaio DZ

Esta fase usa uma nova CI especial que compila o aplicativo completo, não uma IPA mínima artificial. Em uma pasta temporária da máquina macOS, executa o **código DY real**, cobrindo:

- Controle do .app compilado, arquitetura e versão 71.
- Cópia do app e assinatura ad hoc com entitlement histórico.
- Geração do pacote ZIP IPA e checksum de SHA-256.
- Dupla inspeção DI e DS dos mesmos bytes reais em pasta temporária.
- Hardlinks dos arquivos de QA revisados, conferência de SHA/CDHash e recibos de proveniência.
- Leitura de cinco arquivos resultantes e destruição **obrigatória** da pasta temporária. Não armazena IPA em artifact, GitHub Release, cache de downloads do WebReader nem biblioteca do iPad.

### O teste NÃO é uma autorização real

A Fase DZ executa `package_one_shot_build71_qa` com **um mock restrito à função do gatilho**, usando `unittest.mock.patch.object` e uma identidade de origem sintética do run. A finalidade é testar o mecanismo real de assinatura e empacotamento **sem criar o arquivo de gatilho do usuário**. O mock não substitui o código de assinatura, `codesign`, DI, DS ou os bytes da IPA. A pasta é descartada ao final.

**Atenção:** durante o ensaio os recibos do empacotador podem conter afirmações operacionais referentes ao gatilho simulado. Por isso nenhum desses arquivos é distribuído, carregado como artifact, destinado ao dispositivo ou usado como evidência de consentimento do proprietário. O **único relatório publicável** do ensaio afirma explicitamente `actualOwnerTriggerUsed=false`, `temporaryMockOwnerContextUsed=true`, `deliverableRetained=false` e `installationAuthorized=false`.

O próprio executor DZ recusa execução fora do workflow exato de macOS no projeto, sem revisão da branch correspondente, em qualquer rerun, sem SHA válido, com checkout alterado ou quando existe o gatilho real da Fase DY. Os testes Linux verificam essas recusas e a ausência de upload. Sua execução não depende de o usuário fazer algo no iPad.

## Arquivos implementados

- `ci/build71_dz_qa_packaging_rehearsal.py`: ensaio de ponta a ponta descartável no macOS com apenas a simulação do contexto do gatilho.
- `ci/test_build71_dz_qa_packaging_rehearsal.py`: 8 testes Linux de fonte, condições de execução e negativas de autoridade.
- `.github/workflows/chimera-build70-phase-dz-build71-package-rehearsal.yml`: Linux regressivo + macOS compilação/assinatura/DI/DS com eliminação da IPA.
- Documento presente.

## Critério estrito

Só registrar Fase DZ como concluída depois que ambos os jobs **Linux e macOS** terminarem em `success`, e o runner Apple imprimir o status `DZ_FULL_APP_OWNER_PACKAGER_REHEARSED_AND_DESTROYED` e `deliverableRetained=false`. Testes Linux não comprovam o empacotamento Apple.

O sucesso não autentica proprietário/editor, nem certifica que o iPad está usando o mesmo entitlement; não verifica a biblioteca real, a integridade de todas as páginas offline, a sobrevivência do contêiner após atualização nem concede permissão para instalar. `productionPublicKeyX963=nil`; `independentlyProvisionedSPKISHA256=nil`; `liveInstallationEnabled=false`.

Não criar nem acionar `ci/build71_owner_approved_qa_trigger.txt` com base em `continue`; somente após um pedido explícito futuro para preparar e entregar uma IPA71 privada de teste.


## Diagnóstico de CI e correção da revisão seguinte

O primeiro ensaio real DZ executou `xcodebuild` e obteve `BUILD SUCCEEDED`, mas o script foi recusado **antes de assinar**, com `DZRejected: source checkout not clean`. O checkout não tem um `.gitignore`; as importações Python em `ci/` criam entradas `__pycache__` não rastreadas. Esta condição é causada pelo próprio executor durante a tentativa de diagnóstico, não por uma modificação de código revisado.

A correção é **`PYTHONDONTWRITEBYTECODE: "1"` nos jobs macOS DZ e DY**. O Python não grava `.pyc` ou `__pycache__` no checkout; a verificação `git status --porcelain=v1 --untracked-files=all` permanece **estrita e sem exceções**. Não criar um `.gitignore` geral, não remover arquivos de checkout antes de verificar integridade e não desabilitar a verificação.

Os testes DZ/DY de contrato verificam a presença dessa configuração nos dois workflows. A aprovação completa do ensaio de empacotamento ainda depende da **nova execução macOS**. A execução anterior falhou e não publicou IPA.
