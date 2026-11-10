# WebReader Build70 — Fase CR: descritor herdado e troca adversarial de pathname

**Data:** 10/11/2026. **Branch:** feat/chimera-updater-phase1-protocol-audit. **PR:** #90 Draft. A Build70 instalada no iPad iOS 12.5.8, biblioteca, main e Releases permanecem intocados.

## Problema investigado

O helper legado da Fase CJ verificava uma IPA e depois passava um **nome mutável** ao instalador. Um processo com permissão de renomear/substituir esse caminho poderia trocar o conteúdo entre auditoria e abertura (TOCTOU). A cópia CK com permissões 0400 não torna um inode imutável nem obriga o instalador a consumir os mesmos bytes auditados.

## Entrega CR

- ci/build70_cr_fd_alias_lab.py: laboratório **host-only**, sem IPA real, rede, jailbreak, privilégios ou appinst. Produz arquivos sintéticos distintos, confere o original por descritor e substitui o pathname por um arquivo adversarial.
- Um filho Python controlado herda o FD explícito e lê /proc/self/fd/N (Linux) ou /dev/fd/N (macOS). Deve observar o SHA-256 original, enquanto o nome substituído aponta para bytes diferentes.
- O teste sem herança do FD precisa falhar; a observação não confere permissão de instalação.
- ci/test_build70_cr_fd_alias_lab.py: cinco testes de pathname swap, ausência do FD, divergência de digest, alias sem nome controlado pelo cliente e campos de autorização negativos.
- .github/workflows/chimera-build70-phase-cr-fd-alias.yml: executa o laboratório e regressão em Linux/macOS, verificando que os gates de produção seguem fechados.

## Alcance e limites

O ensaio demonstra apenas a leitura do mesmo arquivo pelo **processo Python simulado**, apesar da troca de pathname. NÃO demonstra que appinst no Chimera/iOS12 aceite /dev/fd/N, herde um FD até o término da instalação, aceite esse formato de caminho, preserve o objeto ao extrair ou não reabra um pathname substituível.

Trocar um **nome** não equivale a alterar os **bytes do mesmo inode**: outro descritor gravável pode ainda modificar os bytes. Um FD herdado também não demonstra que o código Apple da IPA é íntegro, que a editora real é autenticada, que houve consentimento do dono, nem que o replay e rollback estão bloqueados.

FdAliasObservation deve manter ios12_verified=false, appinst_fd_alias_compatible=false, immutable_install_bytes_proven=false, publisher_authenticated=false, consent_verified=false, install_authorized=false e installation_performed=false. O resultado jamais ativa o helper.

## Gates seguintes

1. Teste de compatibilidade real com appinst SOMENTE em ambiente físico descartável e sem instalar a Build70; até então nenhuma compatibilidade é presumida.
2. Serviço com diretório isolado de processos não confiáveis, proteção contra mutação do mesmo inode e validação nativa do arquivo consumido.
3. Chave editorial real criada e retida exclusivamente pelo proprietário, fingerprint público conferido de forma independente, e root de confiança provisionada em nova Build aprovada.
4. Consentimento local inequívoco e diário durável de anti-replay/anti-rollback, mais testes de recuperação, preservação da biblioteca e QA física iOS12.

**Nenhuma Build71, IPA, .deb ou Release foi gerada. Nenhum app foi instalado.** Main, WebReader Build70 e dados locais preservados.
