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
