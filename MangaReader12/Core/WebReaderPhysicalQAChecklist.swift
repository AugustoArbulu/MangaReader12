import Foundation

/// Phase AE / Build69 development: user-owned, read-only physical QA template.
/// It never reads the Library, user documents, chapters, login or IP address;
/// answers are filled in manually by the owner after a device-side test.
/// Copying the template cannot claim a passed physical check.
enum WebReaderPhysicalQAChecklist {
    static func report(installedBuild: Int, ios: OperatingSystemVersion) -> String {
        let build = installedBuild >= 1 && installedBuild <= 2_147_483_647
            ? String(installedBuild) : "desconhecida"
        let version = ios.majorVersion >= 0 && ios.majorVersion <= 99 &&
            ios.minorVersion >= 0 && ios.minorVersion <= 99 &&
            ios.patchVersion >= 0 && ios.patchVersion <= 99
            ? String(ios.majorVersion) + "." + String(ios.minorVersion) + "." +
                String(ios.patchVersion)
            : "desconhecido"
        return [
            "WebReader • roteiro de QA FÍSICA (não é diagnóstico automático)",
            "Build observada: " + build + " • iOS: " + version,
            "A instalação foi feita manualmente pelo Filza? [SIM/NÃO/NÃO TESTADO]",
            "Biblioteca, favoritos e progresso preservados? [SIM/NÃO/NÃO TESTADO]",
            "Capítulos previamente baixados com Wi-Fi DESLIGADO? [SIM/NÃO/NÃO TESTADO]",
            "Páginas do leitor e escala largura/altura? [SIM/NÃO/NÃO TESTADO]",
            "Fontes Webtoons / WeebCentral / Asura? [SIM/NÃO/NÃO TESTADO]",
            "Importação de IPA local e revalidação SHA? [SIM/NÃO/NÃO TESTADO]",
            "Cancelamento e limpeza de arquivo .partial? [SIM/NÃO/NÃO TESTADO]",
            "Recibo de integridade copiável? [SIM/NÃO/NÃO TESTADO]",
            "Instalação automática continua BLOQUEADA? [SIM/NÃO/NÃO TESTADO]",
            "Backup mantido fora do iPad? [SIM/NÃO/NÃO TESTADO]",
            "Mensagem de erro (sem dados pessoais):",
            "O relatório não lê biblioteca, senhas, documentos ou capítulos.",
            "Este roteiro não executa downloads, assinatura ou instalação."
        ].joined(separator: "\n")
    }
}
