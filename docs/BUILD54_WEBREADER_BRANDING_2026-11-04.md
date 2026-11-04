# Build 54 — mudança do nome visível para WebReader

Data: 2026-11-04. Repositório continua `AugustoArbulu/MangaReader12`. iOS mínimo **12.0**; aparelho de validação iOS **12.5.8**.

## O que mudou
- `Info.plist`: `CFBundleDisplayName` e `CFBundleName` agora são **WebReader**. O ícone na Tela de Início deve aparecer com o novo nome.
- Ajustes mostra **WebReader** e Build 54. Título de apresentação do repositório demo também alterado.
- O pacote gerado pelo CI chama-se `WebReader-iOS12-unsigned.ipa`.
- `ci/test_build54_branding.py` verifica arquivos fonte e `ci/verify_binary.sh` verifica os campos efetivos do **Info.plist do Release**.
- A versão interna `CFBundleVersion` aumenta para **54**.

## Regra de continuidade de dados (CRÍTICA)
- O bundle identifier permanece **`com.example.MangaReader12`**, sem troca de package ID.
- O executável, target e scheme Xcode permanecem **`MangaReader12`**, e o pacote compilado interno é `MangaReader12.app`.
- Banco SQLite, `Application Support/MangaReader12`, arquivos de downloads, caches, UserDefaults, backup `.mr12backup`, IDs de capítulos/sources e URLs de catálogos **não foram renomeados nem migrados**.
- Isso é intencional: trocar esses identificadores faria a nova instalação correr risco de perder acesso à Biblioteca existente.
- Para manter dados, instalar via Sideloadly **por cima** do app anterior com a mesma configuração de assinatura/identificador final. **Não desinstalar**.
- A etiqueta do ícone muda, não o desenho do ícone. Não há mudança de rede, decodificador, Cloudflare ou conteúdo das fontes.

## Checklist no iOS 12.5.8
1. Confirmar **WebReader** abaixo do ícone e **Build 54** em Ajustes.
2. Confirmar a presença da Biblioteca antiga, obras fixadas, histórico, fontes e downloads.
3. Abrir capítulo WebP online e capítulo já baixado em modo avião, sem erro `-1009`.
4. Confirmar que não apareceu uma **segunda instalação** com um novo banco vazio. Se aparecer, não apagar o original; comparar o identificador assinado/instalado.
5. Aplicação aprovada em CI **não equivale** a teste físico. Registrar o resultado do usuário antes de aceitar a Build 54 como checkpoint físico.

## Próximas prioridades
Retomar melhorias da Biblioteca e Downloads sem refazer funcionalidades já existentes, preservando iOS12 e a Build 53 como referência CI. AVIF segue apenas detectado; nenhuma biblioteca AV1 adicional foi integrada nesta mudança.
