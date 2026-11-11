# WebReader Build70 — Fase DR: integração DQ + DO e execução ponta a ponta shell → parser

**11/11/2026.** Branch feat/chimera-updater-phase1-protocol-audit; PR #90 Draft. Main, iPad e dados offline intactos. Sem IPA, DEB, instalação, release ou chave editorial provisionada.

## Objetivo e diferença em relação à Fase DQ

DQ examina somente o texto de uma possível inspeção dos metadados do bundle instalado. DO examina os textos de nove contagens SQLite e lotes de até 64 capítulos offline gerados pela Build70. Nenhum desses textos é assinado ou prova que veio do iPad físico. Os testes unitários anteriores também não exerciam de ponta a ponta a saída efetiva de printf do script POSIX no mesmo processo do parser.

Nesta fase foram preparados dois instrumentos independentes e estritamente host-only:

1. Um teste de execução real do script DQ em Linux/macOS que substitui os caminhos fixos **somente em cópia temporária**, apontando para um bundle sintético descartável e duas ferramentas simuladas (plutil e ldid). Não é o executável iOS real, e não há assinatura, banco, imagens, Chimera, appinst ou rede. O script de produção preserva a allowlist e não foi modificado. São exercitados LF terminal, ferramenta indisponível, metacaracteres, versão/entitlement divergentes, symlinks, paths proibidos e tentativa de acrescentar autoridade ao stdout.
2. Um comparador DR host que reutiliza os parsers originais DQ e DO, aceitando relatórios textuais pré-upgrade. Recusa formatos adulterados, lotes ausentes e números contraditórios; nunca solicita instalação. O status mais favorável significa apenas que os metadados de duas fontes de texto se encaixam, não que sejam verdadeiros.

## Arquivos

- ci/test_build70_dq_shell_parser_e2e.py — execução do script host temporário de DQ e alimentação do stdout real no parser; testes sem rede e sem modificar a instalação.
- ci/build70_dr_preupgrade_crosscheck.py — CLI opcional para analisar relatórios já existentes, sem leitura do iPad: argumentos --dq, --counts e --offline (um por lote).
- ci/test_build70_dr_preupgrade_crosscheck.py — cenários positivos apenas textuais, campos UNAVAILABLE, divergência, falta de arquivos, lotes repetidos, legados sem recibo, amostra parcial, symlink e mutações adversariais.
- .github/workflows/chimera-build70-phase-dr-preupgrade-evidence.yml — execução Linux e macOS, sem artifacts, guardas contra instalação.

O comparador DR usa a leitura de arquivo regular com O_NOFOLLOW do contrato DJ, verifica limites e retorna exclusivamente um JSON de análise. Nunca escreve em disco, não enumera aplicativos, não acessa a biblioteca e não toma ações com o helper.

## Resultado do comparador DR

| Condição observada em textos fornecidos pelo usuário | Status |
| --- | --- |
| DQ apresenta Bundle ID, Build ou entitlement divergente | DR_REPORTED_IDENTITY_MISMATCH_STOP_QA |
| DO apresenta capítulos faltantes/inseguros | DR_REPORTED_OFFLINE_METADATA_FAILURE_STOP_QA |
| DQ retorna UNAVAILABLE para qualquer dos três campos | DR_REPORTED_INSTALLED_IDENTITY_UNAVAILABLE_NOT_READY |
| DO registra capítulos legados sem recibo | DR_REPORTED_LEGACY_OFFLINE_NEEDS_REAL_READING |
| DO apresenta lotes incompletos | DR_REPORTED_OFFLINE_BATCHES_INCOMPLETE |
| DO diz zero downloads completos | DR_REPORTED_NO_COMPLETED_OFFLINE_METADATA_NOT_DEVICE_PROOF |
| DQ coincide textualmente com histórico, DO cobre todos lotes sem contradição | DR_PREUPGRADE_TEXT_COHERENT_NOT_ATTESTED_NOT_INSTALLABLE |

As contradições explícitas têm precedência sobre campos desconhecidos. O atributo bothReportFormatsTextuallyCoherent pode ser verdadeiro, mas isso **não verifica criptograficamente a proveniência nem prova mesmo dispositivo ou mesmo instante de coleta**. Todos os booleanos de autenticação, assinatura nativa, confiança editorial, preservação de dados/imagens, consentimento, autorização de instalação e sucesso de atualização continuam false.

## Pré-requisitos futuros não cobertos

- A identidade efetiva da Build70 instalada ainda precisa ser observada no próprio iPad, opcionalmente, sem presumir disponibilidade de plutil/ldid e sem inventar o caminho da pasta do bundle. Nenhum relatório físico foi recebido nesta fase.
- A IPA 71 real e sua assinatura não foram inspecionadas pela DR. O preflight DI sobre os **mesmos bytes finais** e compatibilidade com a identidade instalada ainda serão exigidos.
- Um backup externo confiável não foi feito nesta fase. O arquivo de backup .mr12backup não inclui imagens e uma restauração pode remover downloads.
- Uma atualização manual por cima exigiria autorização específica e teste físico do mesmo capítulo offline com Wi-Fi desligado antes/depois. A atualização automática tem barreiras adicionais: autenticidade do editor, helper confiável, antirreplay, consentimento e vínculo dos bytes entregues ao instalador.
- Os testes host sintéticos **não podem substituir** essas etapas nem comprovar persistência de biblioteca, favoritos e progresso.

**Gates mantidos:** productionPublicKeyX963=nil; independentlyProvisionedSPKISHA256=nil; liveInstallationEnabled=false. Main e WebReader Build70 instalado não são alterados.

## CI

Os jobs Linux/macOS da Fase DR devem concluir antes de declarar a suíte aprovada. Registrar quaisquer falhas e correções, sem mascarar o histórico.
