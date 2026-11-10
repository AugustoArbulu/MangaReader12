# WebReader Build70 — Fase CO: cerimônia offline da chave editorial do proprietário

**10/11/2026.** Desenvolvimento exclusivo na branch `feat/chimera-updater-phase1-protocol-audit`, PR #90 ainda Draft. A Build70 do iPad iOS 12.5.8 permanece a versão física aprovada. `main` e os Releases de produção não são alterados.

## O que este trabalho realmente destrava

No teste físico CM, os três clientes de diagnóstico devolveram `TOKEN_UNAVAILABLE AUTHORIZATION=DENIED`. Decidimos **não** depender de identidade de processo de uma conexão IPC não autenticada para verificar a origem de uma atualização.

O futuro helper independente pode receber no máximo uma notificação sem parâmetros para *checar* uma versão, mas antes de fazer qualquer instalação precisa reconhecer **a assinatura editorial do proprietário** e conferir a integridade da IPA e a proteção antirreplay. A identidade editorial já é modelada no WebReader por:

- `WebReaderProductionPublisherTrust.independentlyProvisionedSPKISHA256` (ainda `nil`);
- `WebReaderUpdateChannel.productionPublicKeyX963` (ainda `nil`);
- manifesto de atualização **v2** assinado por ECDSA P-256 + SHA-256, com build, canal e SHA-256 da IPA;
- auditoria adicional da assinatura nativa/ad hoc **do pacote IPA**. A chave editorial privada assina o **manifesto**, não substitui a assinatura Mach-O usada pelo iOS.

Faltava um procedimento de criação **local, sem rede e sem custódia pelo GitHub ou assistente**, que o proprietário possa usar em seu Windows quando decidir provisionar a confiança real.

## Implementação entregue

`ci/webreader_owner_key_ceremony.py`:

- `--check` verifica a disponibilidade local da biblioteca `cryptography`; **não gera arquivos nem chave**.
- `--create --output-dir CAMINHO` **exige terminal humano interativo** e duas entradas idênticas de uma senha longa via `getpass`; não aceita senha como argumento ou variável mostrada no processo. Não roda autonomamente por um workflow/CI.
- Gera P-256 (`secp256r1`) via CSPRNG local; serializa a chave privada em **PKCS#8 PEM criptografado** com `BestAvailableEncryption`; a parte pública é exportada separadamente em PEM SPKI.
- Calcula SHA-256 do DER SPKI canônico, compatível com `ci/build68_release_public_key_handoff.py` e o preview `ci/build70_owner_public_root_patch_preview.py`; exige SPKI X9.63 descomprimido da curva P-256.
- Usa **diretório existente, absoluto, fora do repositório**, recusa symlinks/junctions e arquivos de saída já existentes, grava cada arquivo com abertura exclusiva `O_EXCL` e `fsync`. No POSIX exige diretório 0700 do próprio usuário e arquivos 0600. No Windows a proteção de ACL/BitLocker continua responsabilidade do proprietário: senha na chave privada **não** substitui proteção de disco.
- Arquivos de saída, somente no computador do proprietário:
  - `webreader-owner-private-encrypted.pem` (**privado, nunca enviar**);
  - `webreader-owner-public.pem` (**público, futuramente revisável**);
  - `webreader-owner-public-spki-sha256.txt` (**fingerprint público**).
- Nenhum endpoint de rede, invocação de git, appinst, IPA, lançamento ou instalação. Chave privada nunca passa para o WebReader, GitHub Actions, chat nem iPad. Não há configuração de chave real no código.

### Como o proprietário pode usar futuramente — NÃO é obrigatório agora

No Windows, uma vez instalado Python e a biblioteca `cryptography` (a instalação das dependências pode ser feita **antes** de desconectar da internet), em uma cópia local da branch de desenvolvimento:

~~~powershell
python -m pip install cryptography==46.0.4
python ci/webreader_owner_key_ceremony.py --check
~~~

Quando o proprietário estiver pronto e com um **diretório local preexistente não sincronizado**, fora de Git/OneDrive/Dropbox e preferencialmente sob BitLocker, executará **expressamente**, em uma janela de terminal local:

~~~powershell
python ci/webreader_owner_key_ceremony.py --create --output-dir "C:\MeuDiretorioPrivadoWebReader"
~~~

O script pede uma senha forte **interativamente**, duas vezes; o exemplo de caminho é ilustrativo, não é criado automaticamente. Proteger o backup da chave e o backup da senha **separadamente**. Não compartilhar senha, PEM privado nem tela do terminal durante a criação. **Não enviar para este chat a chave privada**.

O hash público de 64 caracteres SHA-256 deve ser registrado e confirmado em uma via independente, controlada pelo proprietário, antes de aceitar a implantação de um pin compilado. Receber o PEM público e o hash do mesmo ZIP ou Release remoto **não** é confirmação independente da identidade do editor.

Quando (e somente quando) o proprietário autorizar uma nova Build com confiança editorial, o **preview público CG** pode gerar um diff de revisão sem importar nem ler a chave privada:

~~~sh
python3 ci/build70_owner_public_root_patch_preview.py \
  --public-key /caminho/seguro/webreader-owner-public.pem \
  --independent-spki-sha256 HASH_PUBLICO_CONFERIDO_POR_FORA \
  --installed-build 70 \
  --output-patch /caminho/seguro/webreader-owner-public-root.patch
~~~

Esse comando existente depende também de OpenSSL instalado e é exemplo ilustrativo de revisão; ele **não** aplica o patch nem publica uma versão. Uma Build futura precisará ser assinada, testada e instalada manualmente para cadastrar o pin público no iPad. O proprietário não precisa executar nada disso durante a Fase CO.

## Testes e limites honestos

- `ci/test_webreader_owner_key_ceremony.py`: utiliza **somente chaves descartáveis de laboratório** em diretórios temporários, não chaves de produção. Verifica que PEM privado permanece criptografado, senha errada é recusada, public key e SPKI fingerprint conferem, arquivos pré-existentes nunca são substituídos, symlinks e diretório do repositório são recusados, permissão POSIX é restrita, `--check` não gera chave, e `--create` falha sem terminal interativo.
- `.github/workflows/chimera-build70-phase-co-owner-ceremony.yml`: CI Windows e Linux, sem artefatos que contenham chave; também verifica `productionPublicKeyX963 = nil`, `independentlyProvisionedSPKISHA256 = nil` e `liveInstallationEnabled = false`.
- [GitHub Actions Fase CO — 2/2 SUCCESS](https://github.com/AugustoArbulu/MangaReader12/actions/runs/42756711143).
- A biblioteca Python e a senha são geridas pelo proprietário. A linguagem Python não assegura zeroização física de todos os buffers de senha na RAM; o script evita logs, linha de comando e arquivos com chave privada sem criptografia.
- Esta ferramenta **não** basta para atualizar automaticamente o WebReader: o serviço instalador ainda requer origem fixa, validação independente da versão publicada, bytes idênticos auditados e consumidos no instalador, autorização local inequívoca, proteção contra rollback/replay e teste físico iOS 12.

**Status:** entrega de código e testes somente; **nenhuma chave editorial de produção criada, compartilhada, provisionada ou ativada**. `main`, produção, releases, Build70 instalada e dados de leitura mantidos.
