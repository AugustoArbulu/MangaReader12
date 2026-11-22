# WebReader — Fase 5F: pré-inspeção de arquivo IPA por descritor (offline)

Data: 2026-11-05.
Branch: feat/chimera-updater-phase1-protocol-audit (PR #90 Draft).
Base física: WebReader Build 56 aprovada, iOS 12.5.8; sem alterações na main.

## Resultado

Foi desenvolvido um protótipo Python somente host, em
ci/webreader_helper_file_preflight.py, com testes em
ci/test_webreader_helper_file_preflight.py. Ele inspeciona um arquivo
preparado e confirma apenas se seus bytes coincidem com tamanho/hash
esperados fornecidos ao teste. Não autentica manifesto, não valida toda
a estrutura ZIP, não instala IPA e não roda com privilégios especiais.

O nome aceito corresponde ao padrão de saída do
WebReaderIPAStager.swift: WebReader-build<N>-<UUID>.ipa.
Caminhos absolutos, traversal, nomes sem UUID e builds diferentes
são rejeitados. O futuro helper NÃO poderá aceitar o diretório
confiável como caminho escolhido pelo cliente.

## Verificações modeladas

1. Metadados estritos: build inteiro maior que zero, tamanho entre 4 bytes
   e 512 MiB, SHA-256 hexadecimal minúsculo. No helper real, esses
   valores devem vir de manifesto autenticado independentemente, nunca
   de simples IPC do aplicativo.
2. Diretório: aberto usando O_DIRECTORY e O_NOFOLLOW; verifica tipo
   e permissões que não permitam gravação por grupo/outros. A raiz
   precisa ser previamente confiável.
3. Arquivo: aberto relativamente ao descritor do diretório (dir_fd),
   usando O_NOFOLLOW e O_NONBLOCK; rejeita symlink, hardlink,
   FIFO/dispositivos, dono incompatível, permissões permissivas e
   tamanho divergente.
4. Conteúdo: SHA-256 integral por blocos limitados, compare_digest,
   limite de bytes e prefixo ZIP PK\x03\x04. O prefixo não valida um ZIP.
5. Troca do arquivo: compara fstat antes/depois (device, inode, size,
   mtime_ns e ctime_ns) e stat do nome relativo ao fim. Testes injetam
   mutação e troca por renomeação durante a leitura.
6. Resultado: FilePreflightReport.installer_authorized sempre False,
   somente leitura. A função fecha o descritor no fim; portanto o
   relatório NÃO impede que o arquivo mude após a verificação.

A suíte adversarial local em Linux passou em 13 testes. A execução
no macOS do GitHub Actions ainda exige confirmação no HEAD exato.

## Riscos pendentes

- TOCTOU após a inspeção: como o descritor é fechado, outro processo
  pode trocar o arquivo. O helper real deve manter o mesmo descritor
  até o uso ou fazer uma cópia protegida/imútavel com revalidação
  imediata dos bytes entregues ao instalador.
- Symlinks ancestrais: O_NOFOLLOW protege a entrada aberta, mas não
  automaticamente todos os componentes ancestrais; usar diretório
  raiz autenticado e caminhada por descritores em implementação real.
- Hash vindo do app: igualdade de hash não comprova origem oficial.
  O helper precisará verificar assinatura P-256 e manifesto estrito
  com sua própria chave pública pinada.
- Estrutura IPA: ZIP central directory, CRC, Info.plist, bundle/build
  e iOS mínimo devem ser auditados independentemente pelo helper.
  O script não substitui WebReaderNativeIPAAuditor.swift.
- Nenhum IPC privilegiado real, appinst, AppSync, Chimera, Release
  assinado, atualização ou preservação de sandbox foi validado.

## Critérios de avanço

1. CI verde da Fase 5F, com testes Python e compilação iOS12.
2. Origem oficial do appinst e hash do binário no aparelho verificados
   independentemente.
3. Projetar IPC com autenticação forte, passagem por descritor ou
   armazenamento protegido e revalidação no ponto real de instalação.
4. Testes primeiro em app descartável e dados de teste, sem tocar na
   Biblioteca real ou capítulos offline.

Esta fase não cria uma Build 57, não faz merge, não habilita download
nem instalação e não autoriza executar appinst.
