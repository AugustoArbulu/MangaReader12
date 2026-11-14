# WebReader Build70 - Fase CP: manifesto production v2 assinado offline pelo proprietario

Data: 10/11/2026. Branch feat/chimera-updater-phase1-protocol-audit; PR #90 Draft. Main, Releases e a Build70 instalada no iPad nao foram alterados.

## Entrega

O novo script ci/webreader_owner_offline_v2_signer.py e um assinador local para quem ja criou uma identidade P-256 pela ferramenta da Fase CO. Ele nao gera chave permanente no CI, nao compartilha segredo, nao acessa rede e nao cria Releases.

O proprietario executa --sign **interativamente no proprio computador Windows/Linux**. A senha da chave privada PKCS#8 criptografada e digitada via getpass, nao em argumento, variavel de ambiente, stdout ou arquivo temporario. O script confere que:
- A chave privada criptografada corresponde ao PEM publico P-256 e ao fingerprint SHA-256 do DER SPKI.
- O pin publico informado pelo proprietario coincide com a chave publica, embora a ferramenta nao possa provar se o proprietario realmente obteve o pin por canal independente.
- O IPA local e um ZIP com limites, nomes canonicos, sem links ou membros duplicados, contendo exclusivamente o bundle WebReader. O build vem do Info.plist, precisa ser superior a baseline 70 e exige versao minima compativel com iOS12.5.8.
- O nome precisa ser WebReader-BuildN-iOS12-adhoc.ipa. O URL assinado e construido pelo proprio script como https://github.com/AugustoArbulu/MangaReader12/releases/download/buildN/WebReader-BuildN-iOS12-adhoc.ipa, sem aceitar URL externa.
- Tamanho e SHA256 sao computados sobre o snapshot local completo; releaseNotes e publishedAt UTC sao validados.
- O envelope possui exatamente schemaVersion=2, algorithm=ecdsa-p256-sha256, payload e signature. O payload inclui applicationIdentifier=AR5SFJC432.com.example.MangaReader12.AR5SFJC432, channel=production e SHA256 dos bytes IPA.
- Assinatura ECDSA sobre o payload JSON e verificada de volta pela chave publica antes da criacao exclusiva do arquivo local channel-production-v2.json.
- A saida e criada O_EXCL, sem sobrescrita e sem instalador, qualquer publicacao ou mudanca na configuracao do app.

## Limite de seguranca principal

**Manifesto assinado nao significa IPA segura nem instalavel.** O signer Windows nao verifica o selo de assinatura nativo Apple. O recibo declara nativeAppleIPACodeSealVerifiedByTool=false, macOSNativeProductionPreflightStillRequired=true, releasePublished=false e installationAuthorized=false.

Uma auditoria separada com ci/build69_production_release_preflight.py em **macOS** precisara validar a IPA real e seu selo nativo, juntamente ao manifesto e chave publica (sem precisar da chave privada), antes de qualquer publicacao editorial. Ate la, uma IPA sintetica pode ser assinada apenas para fins de teste. O snapshot de arquivo local nao resolve a passagem dos exatos bytes ao instalador: o futuro helper precisa verificar objeto imutavel e ter consentimento real, anti-replay e tratamento de downgrade. A comparacao de tamanho/mtime por pathname no Windows nao prova identidade imutavel: NTFS pode apresentar atributos distintos em stat(path) e fstat(fd). A comparacao mais forte ocorre dentro do handle de leitura; o recibo NAO oferece garantia contra TOCTOU privilegiado.

## Uso futuro pelo proprietario, nao exigido agora

Apos preparar um diretorio privado local no Windows e criar **pessoalmente** a chave editorial pela Fase CO, com backup criptografado, conferir o fingerprint publico independentemente. A chave privada e sua senha NUNCA devem ser enviadas ao chat, GitHub, iPad ou CI.

Instalar previamente Python 3.12 com a biblioteca cryptography 46.0.4 e baixar o codigo de revisao do repo. O comando de diagnostico de dependencias nao le chave nem assina:

~~~powershell
python ci/webreader_owner_offline_v2_signer.py --check
~~~

Quando houver uma IPA nova, testada e assinada, somente o proprietario podera executar manualmente com caminhos, hash e data substituidos por valores reais:

~~~powershell
python ci/webreader_owner_offline_v2_signer.py --sign --owner-dir "C:\PastaPrivadaWebReader" --ipa "C:\Candidatos\WebReader-BuildNN-iOS12-adhoc.ipa" --notes-file "C:\Candidatos\notes.json" --output "C:\Candidatos\channel-production-v2.json" --independent-spki-sha256 "HASH_PUBLICO_SHA256_CONFERIDO" --published-at "2026-11-11T10:00:00Z" --installed-build 70
~~~

A nota precisa ser um arquivo UTF-8 JSON array, p.ex. ["Correcao de leitura offline"]. O timestamp e caminho acima sao EXEMPLOS, nao estao relacionados a uma release real. Nao publicar esse resultado ate auditoria nativa independente no macOS e aprovacao editorial. O processo de cadastrar a chave publica na proxima IPA de confianca continua separado e exige revisao e instalacao manual.

## Validacao

Testes ci/test_webreader_owner_offline_v2_signer.py: assinatura real de manifesto production v2 com chave efemera de laboratorio, verificacao com cryptography e com o verificador Python/OpenSSL ja existente, confere SHA256/size/URL/version, e rejeita senha errada, pin errado, chave alterada, IPA adulterada, caminho errado, downgrade, UTC invalido, releaseNotes incorretas, saida existente, execucao automatica. A chave criada pela CI e descartavel, nunca editorial. CI multiplataforma Windows + Linux: https://github.com/AugustoArbulu/MangaReader12/actions/runs/42758008488 — **SUCCESS 2/2**.

## Situacao do atualizador

Chave publica editorial de producao: **nao provisionada**. GitHub Release de producao: **nenhuma**. Helper instalador: **desativado**. PR #90: Draft, sem merge. Main e biblioteca/downloads da Build70 intocados. O TOKEN_UNAVAILABLE reportado fisicamente em tres casos CM segue evidenciado; protocolo check-only nao confiavel Fase CN nunca pode autorizar instalacao.

Proximos gates: dono criar chave sob sua propria custodia, revisar public pin em futura IPA, criar uma release de verdade com assinatura e selo nativo auditados, resolver transferencia exata de bytes verificados e consentimento owner-local no helper antes da ativacao. Nao repetir testes de token sem uma hipotese tecnica que altere a decisao de seguranca.
