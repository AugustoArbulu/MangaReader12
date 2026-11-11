# WebReader Build70 — Fase DS: cadeia pré-upgrade read-only DQ → DO/DR → DI/DK (Build71)

**11/11/2026.** Trabalho exclusivo em `feat/chimera-updater-phase1-protocol-audit`, PR #90 Draft. Não modifica a `main`, não gera IPA/DEB para distribuição, não publica Release, não instala nada nem acessa o iPad.

## Motivação

As fases recentes produzem evidências diferentes, que NÃO devem ser confundidas com provas físicas:

- **DQ**: coleta opcional somente leitura, a ser realizada no futuro, dos três valores de identidade textual da **Build70 já instalada**. Mesmo `ldid -e` não valida criptograficamente o selo do código e os campos reportados podem ser adulterados.
- **DO/DR**: aceita relatórios textuais da Build70 sobre nove contagens SQLite e lotes offline de até 64 capítulos cada; cruza a coerência com DQ. Não lê o conteúdo das páginas nem atesta que os textos foram obtidos no mesmo iPad.
- **DI/DK**: inspeciona no macOS o ZIP IPA candidato **por bytes SHA256 fixados**, Bundle ID, build 71, mínimo iOS 12, ARM64, entitlement histórico e selo Apple ad-hoc. Mesmo um selo ad-hoc autêntico para os bytes lidos em host NÃO autentica editor, não comprova a assinatura efetiva do aplicativo já instalado, não garante aprovação do instalador iOS12 e não demonstra preservação dos dados.

A Fase DS une os três subsistemas e falha de modo seguro se as evidências forem contraditórias ou incompletas. A união **não cria** uma permissão de distribuição, instalação ou ativação do helper; somente pode produzir um recibo positivo de **consistência de laboratório**, explicitamente não instalável.

## Implementação entregue

- `ci/build70_ds_candidate_evidence_gate.py`: recebe `--dq`, `--counts`, `--offline` (repetido), `--ipa` e `--checksum-file`. Primeiro executa o comparador DR. Só se os textos forem canônicos, todos os lotes offline forem cobertos e DQ reportar os três valores históricos é que invoca o preflight DI dos bytes reais do candidato. Na sequência reutiliza a validação do recibo DI da Fase DK e confronta Bundle ID e application-identifier reportados. Nenhuma operação de instalação, download, publicação, assinatura, mutação de arquivo ou rede.
- `ci/test_build70_ds_candidate_evidence_gate.py`: suíte de host que usa apenas recibos DI **simulados** para testar rejeições antes da assinatura, precedência de divergências, incapacidade de promover flags de autorização e mutações adversariais.
- `ci/test_build70_ds_candidate_evidence_native.py`: suíte macOS que reutiliza o construtor de IPA **sintética e descartável** existente na Fase DI. Compila um Mach-O mínimo ARM64 para iOS12, assina ad-hoc pelo `codesign` do runner macOS, monta ZIP local e envia os bytes ao DS. Faz ensaios positivos e negativos de entitlement, adulteração após code seal, downgrade e alteração pós-checksum. Este arquivo nunca contém o código real do WebReader e nunca deve ser enviado ao dispositivo.
- `.github/workflows/chimera-build70-phase-ds-candidate-evidence.yml`: Linux, testes mockados e regressões DI/DR; macOS com Xcode 16.4, testes de assinatura nativa somente em arquivo sintético; sem upload de artifacts.
- Esta documentação permite retomar o projeto preservando limites, ressalvas e os próximos bloqueios físicos.

## Comportamento e distinções importantes

O DS exige um estado textual `DR_PREUPGRADE_TEXT_COHERENT_NOT_ATTESTED_NOT_INSTALLABLE`, isto é, um texto DQ completo e conhecido e uma sequência DO sem erros ou lotes faltantes. Caso falte `ldid`, o entitlement venha `UNAVAILABLE`, haja divergência textual ou um capítulo offline esteja marcado inseguro, o DS retorna erro **antes mesmo de invocar a validação da IPA**. Isso minimiza o risco de confundir uma assinatura candidata perfeita com evidências físicas insuficientes.

O status máximo `DS_HOST_TEXT_AND_SIGNED_CANDIDATE_COHERENT_NOT_INSTALLABLE` significa somente:
1. Os relatos DQ e DO fornecidos se encaixam no formato e nos valores esperados.
2. O host macOS validou o selo ad-hoc e os metadados da **cópia de bytes do candidato** examinada.
3. Todos os booleanos de prova física, autenticação editorial, consentimento, retenção de contêiner e instalação seguem explicitamente `false`.

**Esse status não comprova que o iPad atualmente contém a Build70 alegada.** O texto poderia ter sido forjado ou coletado em outro momento; o app instalado poderia diferir na assinatura ou entitlement. Também não demonstra que o instalador verá os mesmos bytes que foram examinados em host. Não inferir atualização automática viável a partir do sucesso do DS.

## Limites operacionais e proteção de dados

- Nenhum script deve procurar a pasta do app por varredura de todos os contêineres. A coleta DQ futura dependerá de caminho explicitamente selecionado no Filza, e pode retornar `UNAVAILABLE` se as ferramentas opcionais não existirem.
- Nenhum relatório privado de biblioteca, capítulos, paths, credenciais, imagens ou arquivos `.mr12backup` deve ser anexado ao GitHub. Os contratos textuais DQ e DO contêm somente valores de versão/identidade e **contagens**.
- A validação DI usa os bytes fornecidos pelo teste local, mas não distribui e não instala a IPA. Para um ensaio futuro, a Build71 deverá ter o MESMO identificador de aplicativo, entitlement adequado, código compatível e consentimento explícito. Mesmo assim será necessário backup externo de dados e teste físico por cima, inclusive ler o mesmo capítulo offline com Wi-Fi desativado antes e depois.
- O backup `.mr12backup` não inclui páginas de imagens; restaurá-lo por cima pode eliminar downloads. NÃO realizar uma restauração automática como condição de upgrade.
- A atualização automatizada exige confiança independente do editor, origem/manifestações assinadas, helper autenticado, antirreplay/rollback, vínculo atômico dos mesmos bytes ao instalador e consentimento confiável. Nada disso foi implementado ou habilitado pela DS.

## Travas permanentes

- `productionPublicKeyX963=nil`
- `independentlyProvisionedSPKISHA256=nil`
- `liveInstallationEnabled=false`
- PR #90 Draft; `main` intocada; Build70 física e biblioteca/offline não tocadas.

## CI e avaliação

Os testes Linux usam recibos de assinatura **simulados**, por isso não equivalem ao macOS. A suíte macOS executa códigos de assinatura Apple **reais em IPAs temporárias e sintéticas**, mas não realiza instalação no iPad. Só declarar DS aprovada após conferir os resultados finais de cada job. Relatar qualquer falha e correção, sem ocultar o histórico.

## Próximo passo significativo

Antes de preparar qualquer IPA71 para o usuário, coletar somente os metadados não sensíveis da Build70 instalada no iPad e comparar com o contrato histórico, sem supor que o resultado do shell autentica o iPad. Em caso de dados indisponíveis ou divergentes, interromper a QA e investigar sem substituir o app. Após isso, validar um backup externo e a IPA 71 **real**, obter aprovação específica para distribuição e somente então considerar uma atualização manual por cima. A atualização automática permanece bloqueada.
