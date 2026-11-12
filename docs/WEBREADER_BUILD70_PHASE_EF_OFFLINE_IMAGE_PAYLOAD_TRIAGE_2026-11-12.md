# WebReader Build70 — Fase EF: triagem de bytes offline por assinatura de imagem (12/11/2026)

PR #90 Draft, branch feat/chimera-updater-phase1-protocol-audit; main preservada. O software nesta fase é HOST-ONLY, não contata o iPad, não cria backup, não faz download, não repara arquivos, não restaura, não instala IPA e não habilita atualização automática.

## Motivação e alcance

A EA verifica se os bytes de arquivos page-00000.bin etc. existem em uma cópia EXTERNA já extraída e se os recibos e o SQLite copiado são coerentes. Isso não impede que um arquivo com nome de página contenha a resposta "HTTP 200" de uma página HTML de erro, JSON ou uma imagem claramente truncada.

O app real usa ChapterDownloadImageValidator.canStore(data:headers:) em ChapterDownloadManager.swift. Em produção, o WebP é decodificado com WebPImageDecoder, enquanto PNG/JPEG contam com marcadores de conclusão e ImageIO. A nova EF NÃO replica nem substitui esses decodificadores; executa verificações baratas das assinaturas e dos rodapés na CÓPIA já exportada, sem carregar as imagens inteiras.

## Implementação

- ci/build70_ef_offline_payload_triage.py: invocado com --snapshot para raiz de uma cópia externa do DATA CONTAINER com Library/Application Support/MangaReader12/library.sqlite e Downloads.
- Reaproveita a EA para verificar SQLite schema v1, WAL/journal, hashes de páginas, recibos e sequência de arquivos. Reutiliza o carregamento SQLite em memória de ED vinculado ao SHA-256 que a EA leu.
- Lê até 96 bytes do início/fim de cada página marcada completa. Identifica assinaturas JPEG FF D8 FF com EOI nos últimos 64 bytes, PNG com IEND no final, GIF87a/GIF89a com trailer, WebP RIFF/WEBP e tamanho RIFF coerente. Identifica HTML, JSON, XML, erro textual e marcadores claramente incompletos.
- Formatos desconhecidos não são automaticamente chamados de arquivo inválido; são marcados como pendentes de leitura física no iOS12. Arquivos malformados ou respostas não-imagem geram EF_STOP_HTML_OR_TRUNCATED_OFFLINE_FILES. Nenhum nome de capítulo, URL, ID, caminho privado, hash de imagem ou conteúdo de arquivo é exibido: apenas contadores agregados.
- Os testes ci/test_build70_ef_offline_payload_triage.py geram bytes fictícios que podem passar em verificações de assinatura SEM serem imagens decodificáveis. Esse comportamento é proposital e prova a necessidade de validação física. Verificam truncamento, HTML/JSON, tamanho RIFF, arquivo vazio/symlink, WAL pendente, troca de arquivo entre abertura e leitura, e ausência de permissões.
- A CI .github/workflows/chimera-build70-phase-ef-payload-triage.yml roda regressões EA, ED e EF em Linux/macOS, sem artifacts ou Releases. Só marcar aprovado após logs concluídos.

## Status e limites críticos

EF_KNOWN_IMAGE_SIGNATURES_PLAUSIBLE_NOT_DECODED: marcadores mínimos plausíveis dos formatos reconhecidos. NÃO comprova decodificação, integridade completa, mesma origem ou legibilidade no iOS 12. O payload pode conter bytes arbitrários entre cabeçalho e trailer.

EF_UNKNOWN_FORMATS_REQUIRE_REAL_IOS12_READ: formato desconhecido; não confundir com conteúdo malicioso nem com imagem comprovada.

EF_STOP_HTML_OR_TRUNCATED_OFFLINE_FILES: ao menos uma página é resposta não-imagem (HTML/JSON/XML/erro textual) ou assinatura incompleta de formato conhecido. É necessário revisar a cópia antes de QUALQUER operação física.

EF_STOP_EXTERNAL_COPY_INVALID e EF_STOP_EXTERNAL_COPY_CHANGED_OR_UNREADABLE: invalidez da cópia/SQLite/recibos, arquivos inseguros ou alterações durante a inspeção. NÃO reparar, deletar, rescrever ou restaurar.

NENHUM resultado comprova iPad físico, bytes originais do dispositivo, backup completo ou decodificação WebP/PNG/JPEG no iOS12. Ainda é obrigatório abrir o MESMO capítulo sem Wi-Fi antes e após qualquer upgrade futuro, caso o proprietário autorize.

## Uso futuro opcional, não realizado

python3 ci/build70_ef_offline_payload_triage.py --snapshot "/copia/externa/do-data-container"

O path é ilustrativo. Não foram recebidos backups, dados reais ou arquivos privados. Nenhum arquivo ou relatório deve ser publicado no GitHub. O .mr12backup NÃO contém páginas offline; restaurá-lo substitui o banco e remove Downloads.

Trigger ci/build71_owner_approved_qa_trigger.txt AUSENTE; productionPublicKeyX963=nil; independentlyProvisionedSPKISHA256=nil; liveInstallationEnabled=false. Entrega IPA71 e instalação exigem aprovações explícitas separadas. PR #90 não deve ser mesclada na main sem revisão.
