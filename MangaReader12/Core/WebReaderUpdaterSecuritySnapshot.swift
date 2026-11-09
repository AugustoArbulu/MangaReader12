import Foundation

/// Phase U: non-privileged user-facing read-only status of updater gates.
///
/// Does not obtain credentials or establish any trust anchor. All report lines
/// intentionally avoid filesystem paths, secrets and network tokens.
/// The status of the diagnostic IPC helper is NOT an installer identity.
enum WebReaderUpdaterSecuritySnapshot {
    static var keyDescription: String {
        // Presence is NOT authentication of the owner or publisher. In the
        // current production configuration this remains absent (nil).
        return WebReaderUpdateChannel.isConfigured
            ? "Chave pública presente • identidade editorial ainda exige auditoria"
            : "Chave editorial de produção ausente • release não autenticado"
    }

    static let peerDescription =
        "Chimera: identidade do solicitante não atestada pelo sistema"
    static let allowedDescription =
        "Permitido: consultar, conferir, importar e compartilhar IPA manualmente"
    static let deniedDescription =
        "Instalação automática: bloqueada • PING/HMAC não autorizam appinst"

    static var installEnabled: Bool {
        // Deliberately a one-way *status* observation. It is not an
        // installation capability; no caller can set the property.
        return WebReaderAppinstSocket.liveInstallationEnabled
    }

    /// A copyable *offline* diagnostic for the future signed release channel.
    /// Callers supply only present/absent status of the independently compiled
    /// PUBLIC trust root. No PEM, SPKI fingerprint, private key or file path is
    /// included. A positive readiness status is not permission to install.
    static func signedChannelReadinessReport(
        installedBuild: Int, iosVersion: String,
        publicKeyPresent: Bool, independentPinPresent: Bool,
        trustGeneration: Int, verifiedReadiness: Bool
    ) -> String {
        let build = installedBuild >= 0 && installedBuild <= 2_147_483_647
            ? String(installedBuild) : "desconhecida"
        let ios = iosVersion.range(
            of: "^[0-9]{1,2}\\.[0-9]{1,2}\\.[0-9]{1,2}$",
            options: .regularExpression
        ) != nil ? iosVersion : "desconhecido"
        let generation = trustGeneration >= 0 && trustGeneration <= 2_147_483_647
            ? String(trustGeneration) : "inválida"
        let ready = publicKeyPresent && independentPinPresent &&
            trustGeneration >= 1 && verifiedReadiness
        return [
            "WebReader • diagnóstico offline do canal assinado",
            "Build instalada: " + build + " • iOS: " + ios,
            "Chave pública editorial embutida: " + (publicKeyPresent ? "SIM" : "NÃO"),
            "Fingerprint SPKI independente embutido: " +
                (independentPinPresent ? "SIM" : "NÃO"),
            "Geração editorial compilada: " + generation,
            "Chave P-256 e fingerprint conferidos: " + (ready ? "SIM" : "NÃO"),
            "Consulta autenticada pronta: " + (ready ? "SIM" : "NÃO"),
            "GitHub Release público: canal separado, sem assinatura editorial",
            "Builds privadas do Actions: transferência manual via Android/PC e Filza",
            "Este relatório não consulta a rede, nem abre ou modifica sua biblioteca.",
            "Nenhuma IPA foi baixada ou instalada por este relatório.",
            "Instalação direta pelo Chimera: BLOQUEADA; exige autenticação do helper."
        ].joined(separator: "\\n")
    }

    static func safeReport(installedBuild: Int, iosVersion: String) -> String {
        let build = installedBuild >= 0 && installedBuild <= 2_147_483_647
            ? String(installedBuild) : "desconhecida"
        let ios = iosVersion.range(
            of: "^[0-9]{1,2}\\.[0-9]{1,2}\\.[0-9]{1,2}$",
            options: .regularExpression
        ) != nil ? iosVersion : "desconhecido"
        return [
            "WebReader • segurança do atualizador",
            "Build: " + build + " • iOS: " + ios,
            "Origem atual: GitHub Releases público (metadados não autenticados)",
            keyDescription,
            peerDescription,
            allowedDescription,
            deniedDescription,
            "Verificador ECDSA v2: laboratório somente leitura, sem chave de produção",
            "Nenhuma instalação foi solicitada por este relatório"
        ].joined(separator: "\n")
    }
}
