# WebReader Build69 — Fases BD/BE/BF: continuidade de biblioteca e baseline possível na Build68

**Data:** 2026-11-09 UTC. **Repositório:** `AugustoArbulu/MangaReader12`. **Branch:** `feat/chimera-updater-phase1-protocol-audit`; [PR #90 Draft](https://github.com/AugustoArbulu/MangaReader12/pull/90). **Não alterar `main`**, não assinar/publicar uma IPA real sem autorização, não habilitar instalação pelo Chimera. A Build68 continua instalada/aprovada no iPad com a biblioteca intacta.

## Base confirmada

[CI AC–BC #42562761441](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42562761441): **SUCCESS nos 2/2 jobs**. Inclui testes nativos macOS, proteção de transferência e preview unsigned de Build69 iOS12. O Xcode no repositório segue `CURRENT_PROJECT_VERSION=56`; o override 69 usado em CI é **temporário**. **Nenhuma IPA nova do WebReader foi distribuída ou instalada.**

## BD — diagnóstico nativo read-only de contagens

Nova classe `MangaReader12/Core/WebReaderUpgradeContinuitySnapshot.swift`, compilada no target iOS12 pela entrada Xcode ID 43. Tela `Atualizações do WebReader`, seção Segurança: nova opção **Copiar contagens da biblioteca para comparar**.

- Conexão SQLite `SQLITE_OPEN_READONLY | SQLITE_OPEN_FULLMUTEX` somente ao `Application Support/MangaReader12/library.sqlite` **já existente**, sem `CREATE`, migração, alterações de biblioteca ou restore.
- Verifica schema v1, usa transação de leitura consistente `BEGIN DEFERRED`/`ROLLBACK` e executa **nove consultas COUNT** internas: obras em biblioteca, capítulos, lidos, página lida, favoritos, downloads marcados `completed`, histórico, categorias e vínculos obra/categoria.
- Copia **apenas totais e Build/iOS** para a área de transferência. Não imprime títulos, source IDs, nomes de capítulo, caminhos, senhas ou imagens.
- Banco ausente, ocupado, ilegível ou incompatível é **INDISPONÍVEL**, nunca `biblioteca=0`. Tempo de espera SQLite limitado a 200ms.
- **Crítico:** `downloads.state=completed` é apenas índice no banco. A ferramenta **não verifica a existência nem a decodificação de imagens offline**. O usuário precisa ler os capítulos efetivamente sem Wi-Fi.
- A nova linha não existe nas versões anteriores; no atual iPad Build68 ela ainda **não pode fornecer baseline pré-upgrade**.

Tests: `ci/test_native_webreader_upgrade_continuity_snapshot.py` compila o Swift com SQLite3 no macOS e usa DB sintético com dados sensíveis fictícios; checa totais, nenhuma informação pessoal, report estável, perda de download detectada, schema futuro e ausência de DB rejeitados. `ci/test_build69_bd_upgrade_continuity_policy.py` exige leitura `SQLITE_OPEN_READONLY`, ausência de rede e de comandos de mutação, UI extra sem liberar Chimera. Os testes legados de UI foram ajustados de 6 para 7 linhas.

## BE — comparação de dois relatórios nativos

`ci/build69_be_compare_upgrade_counts.py` recebe dois **relatórios textuais** BD, um identificado `Build68 • iOS 12.5.8`, outro `Build69 • iOS 12.5.8`, com esquema rigoroso, nove totais e texto canônico. Falha se houver cabeçalhos faltando, métrica duplicada/trocada, valor negativo, iOS diferente ou dados textuais privados. Classifica `POTENTIAL_DATA_LOSS_STOP_REVIEW` se algum total diminuiu; `CHANGED_COUNTS_REVIEW_MANUALLY` se só houve aumento; e `DATABASE_RECORD_COUNTS_UNCHANGED_NOT_PHYSICAL_QA` se todos forem iguais. **Nunca concede aprovação física ou instala.**

**Limitação no upgrade atual:** a Build68 instalada ainda não possui BD; portanto **o fluxo BE com dois relatórios BD não está disponível para esta primeira atualização**. Ele serve como teste de contrato/reaproveitamento futuro. A Fase BF resolve o caso real abaixo.

## BF — baseline da Build68 por backup portátil já existente

`ci/build69_bf_portable_backup_baseline.py` oferece alternativa prática ao usuário:

- A Build68 já tem **Backup e restauração → Criar backup**, exportando `.mr12backup`. O arquivo é JSON `formatVersion=1`, contendo um SQLite base64 e preferências. O código BF lê **uma cópia local** do arquivo no PC, **em memória**, sem restaurar no iPad, alterar o banco original, imprimir títulos ou transmitir a backup pela rede.
- Aceita formato exato, base64 validado, SQLite schema1, `PRAGMA quick_check`, entradas delimitadas a 128 MiB de JSON/64 MiB SQLite. Rejeita arquivos malformados, schema incompatível, backups não sanitizados e strings duplicadas. O timestamp deve ser positivo e finito.
- Exige as regras de `BackupManager.sanitizePortableSnapshot` no conteúdo: `downloads` vazio, `chapters.downloaded=0`, `sources` vazia. Por esse motivo, a saída inclui **oito totais de biblioteca** e `Downloads marcados completos no banco = null`. Não tenta inferir quantos capítulos offline havia antes da atualização.
- `--after-report` opcional compara esses oito totais a um relatório BD coletado **na futura Build69 já instalada**. Possível diminuição gera `POTENTIAL_LIBRARY_LOSS_STOP_REVIEW`; aumentos geram `LIBRARY_COUNTS_CHANGED_REVIEW`; igualdade gera `LIBRARY_COUNTS_MATCH_OFFLINE_NOT_VERIFIED`. Todos os resultados continuam com `physicalUpdateVerified=false`, `offlineDownloadedPagesVerified=false`.
- A origem da Build68 **não pode ser comprovada pelo backup**; é responsabilidade do proprietário exportar antes da atualização, manter o arquivo fora do iPad e identificar o momento correto. Não publicar o `.mr12backup`: ele contém títulos, histórico e preferências; apenas as contagens geradas podem ser compartilhadas se desejado.

Testes `ci/test_build69_bf_portable_backup_baseline.py` montam banco real SQLite v1 **sintético**, preparam envelope equivalente ao backup portátil, asseguram que nenhum título/ajuste escapa no JSON de saída e testam schema2, base64 inválido, timestamp não finito, backup não sanitizado e suposta perda de categoria.

## Procedimento físico quando a IPA Build69 privada for autorizada

1. **ANTES (na Build68 atual):** abrir `Backup e restauração`, criar e exportar `.mr12backup` para armazenamento protegido no PC/Android. Preservar a Build68 instalada, não apagar nada. Anotar **quais capítulos já estão baixados** para o teste offline (eles não estão no backup).
2. No PC com Python, no checkout do repositório, rodar localmente:
   ```bash
   python3 ci/build69_bf_portable_backup_baseline.py --backup /fora/repo/meu_backup.mr12backup
   ```
   O recibo mostra oito contagens, nunca a lista de obras. **Não fazer upload desse arquivo ao GitHub/ChatGPT.**
3. Após a futura IPA assinada/validada e **somente quando sua instalação manual estiver aprovada**, instalar **por cima**, sem desinstalar, sem `Restaurar backup`.
4. Na Build69, abrir `Atualizações do WebReader → Segurança → Copiar contagens da biblioteca para comparar`. Transferir o **texto** copiado para um arquivo local `after-build69.txt` no PC.
5. Comparar localmente:
   ```bash
   python3 ci/build69_bf_portable_backup_baseline.py \
     --backup /fora/repo/meu_backup.mr12backup \
     --after-report /fora/repo/after-build69.txt
   ```
6. Mesmo se todos os totais coincidirem, **DESLIGAR Wi-Fi**, abrir os capítulos que já eram baixados e navegar por todas as páginas, fechar/reabrir o WebReader offline, verificar progresso e fontes. Esse é o teste físico real. Em caso de falha, **não apagar ou restaurar automaticamente**. Restaurar `.mr12backup` apaga os downloads existentes.

## CI e acompanhamento

A workflow integrada [AC–BF](https://github.com/AugustoArbulu/MangaReader12/actions) roda as três fases e toda a bateria antiga no Linux e macOS (inclusive `swiftc`, Xcode Debug/Release ARM64/iOS12 e preview temporária unsigned Build69). Agora roda também `python3 -m compileall -q ci` antes dos testes. **Confirmar o ID e o resultado mais recente, não confiar em runs canceladas por concorrência.**

| Item | Situação |
| --- | --- |
| Implementação BD/BE/BF | Na branch experimental, sem IPA |
| Nova UI de contagens | Código adicionado, pendente de QA física em Build69 |
| Comparação com Build68 real | Ferramenta BF pronta; ainda não executada em arquivo real do usuário |
| Build68 instalada e dados atuais | Preservados, não acessados |
| Build69 assinada, empacotada, distribuída ou instalada | **NÃO** |
| `main`, produção editorial, instalação Chimera | **NÃO ALTERADOS** |
| Chave privada real/editorial em CI | **NÃO EXISTE** |

## Próximo passo após CI verde

Preparar critérios finais de geração de uma IPA QA privada **somente após aprovação expressa do proprietário**, incluindo os gates BB/BC de identidade e SHA, e o teste físico de preservação guiado pelo baseline BF. Isso não deve ser confundido com disponibilizar atualizações automáticas pelo Chimera: root de confiança editorial e identidade do helper continuam bloqueados.
