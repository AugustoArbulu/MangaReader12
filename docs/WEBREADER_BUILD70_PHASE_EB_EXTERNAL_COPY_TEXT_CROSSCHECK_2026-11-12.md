# WebReader — Fase EB: verificar contagens do iPad contra bytes da cópia externa (12/11/2026)

Escopo: PR #90 Draft, branch feat/chimera-updater-phase1-protocol-audit. Somente auditoria de arquivos em host. Sem acessar o iPad, sem IPA71, sem appinst, sem Release e sem alterações na main.

## Problema e implementação

A Fase DO interpreta o diagnóstico textual da Build70, emitido pelos dois botões existentes em Atualizações > Segurança: nove contagens SQLite e lotes de até 64 capítulos offline. A Fase EA abre uma cópia EXTERNA previamente extraída do contêiner de DADOS do WebReader, lê todos os arquivos de páginas marcadas como completas e calcula hashes. Os dois relatórios não estavam reconciliados entre si.

Novo utilitário: ci/build70_eb_copy_vs_device_text.py

Ele reutiliza os parsers DO/DJ existentes e o auditor EA, sem relaxar os protocolos, e confronta os totais de capítulos completos, arquivos sequenciais, recibos, legados, páginas existentes e cobertura completa dos lotes. Não lê dados no iPad, não cria backup nem modifica arquivos. Entradas:

- --snapshot: raiz da cópia já extraída do data container iOS; NÃO é MangaReader12.app e NÃO é .mr12backup.
- --counts: texto integral das contagens da Build70 iOS 12.5.8.
- --offline: um texto por lote de até 64 capítulos, em ordem, começando no lote zero; repetir para todos os lotes.

Uso FUTURO, somente após coleta física voluntária e backup em meio externo:

python3 ci/build70_eb_copy_vs_device_text.py --snapshot "/copia/externa/data-container" --counts "/dados/contagens.txt" --offline "/dados/lote0.txt" --offline "/dados/lote64.txt"

Os caminhos acima são placeholders, não diretórios reais do iPad. Não publicar banco, páginas, relatórios privados ou IDs no GitHub.

## Interpretação

- EB_COPIED_BYTES_AND_DEVICE_TEXT_TOTALS_AGREE_NOT_ATTESTED: somas coerentes somente em nível agregado; NÃO demonstra que são os MESMOS bytes, imagens ou capítulos do iPad.
- EB_LEGACY_OR_UNICODE_REQUIRES_PHYSICAL_READING: cópia contém capítulos legados sem recibo ou identificadores Unicode cuja equivalência exata com Foundation não foi verificada.
- EB_ZERO_DOWNLOADS_REPORTED_NOT_DEVICE_PROOF: relatórios indicam zero; não inferir ausência real de páginas no aparelho.
- EB_PARTIAL_DEVICE_TEXT_BATCHES_NOT_COMPARABLE: ainda faltam lotes; comparação de páginas totais seria indevida.
- EB_STOP_DEVICE_TEXT_REPORTS_MISSING_OR_UNSAFE_PAGES: texto do app informa arquivos inseguros.
- EB_STOP_COMPLETED_CHAPTER_COUNTS_DIFFER: banco copiado e texto relatam totais diferentes.
- EB_STOP_PAGE_OR_RECEIPT_COUNTS_DIFFER: quantidade de páginas/recibos/legados diverge.
- EB_STOP_NONCANONICAL_BUILD70_REPORT_TEXT ou EB_STOP_EXTERNAL_COPY_UNSAFE_OR_INCOMPLETE: dados inconsistentes, adulterados, WAL/journal pendente ou cópia rejeitada. Não realizar reparos por conta própria.

Os diagnósticos do app são textos NÃO autenticados e podem ser obtidos de outro dispositivo ou outro momento. O fato de uma cópia externa conter N imagens não comprova que elas correspondem aos N arquivos originais do iPad. O teste adversarial inclui conteúdo de página modificado com tamanho e contagem iguais; a EB não declara falsamente que detectou essa troca.

## Testes e invariantes

Arquivos novos:
- ci/test_build70_eb_copy_vs_device_text.py: dados SQLite e páginas fictícias, negativos de divergência/versão, WAL/journal, lote incompleto, legado e falsa equivalência de bytes.
- .github/workflows/chimera-build70-phase-eb-copy-text-crosscheck.yml: Linux/macOS, roda regressões EA + DO + EB sem artifact e sem instalação.

CI só pode ser declarada aprovada após observar os jobs finais. Fases EA/EB permanecem instrumentos host-only; nenhuma cópia externa real nem leitura offline física foi verificada. A assinatura/entitlement da Build70 instalada e a futura IPA71 continuam dependentes de controles separados.

Em TODOS os estados, readyToDistributeIPA=false, readyToInstallIPA=false, installationAuthorized=false, restorationAuthorized=false, automaticUpdaterEnabled=false. O marcador ci/build71_owner_approved_qa_trigger.txt deve continuar AUSENTE. Chave editorial e pin de produção continuam nil; liveInstallationEnabled permanece false. Não interpretar mensagens genéricas de continuidade como autorização para produzir uma IPA ou instalá-la.
