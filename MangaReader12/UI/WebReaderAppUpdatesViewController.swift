import UIKit

/// In-app home for future signed WebReader application releases.
/// This is deliberately SEPARATE from the existing chapter Updates tab and
/// background Library updater. This screen may stage an authenticated IPA but never installs or runs appinst.
final class WebReaderAppUpdatesViewController: UITableViewController {
    private var checker: WebReaderUpdateChecker?
    private var checking = false
    private var lastResult: WebReaderUpdateCheckResult = .disabled
    private var httpsProbe: WebReaderReleaseHTTPSProbe?
    private var testingHTTPS = false
    private var httpsResults: [WebReaderHTTPSProbeResult] = []
    private var testingHelper = false
    private var helperReport = "Ainda não testado"
    private var stager: WebReaderIPAStager?
    private var stagingIPA = false
    private var stagedIPAURL: URL?
    private var ipaStatus = "Aguardando validação do canal"

    // The isolated com.example.MangaReader12.ipcprobe IPA exposes only
    // version info and the local PING diagnostic; never the release controls.
    private var isIPCDiagnostic: Bool {
        return Bundle.main.bundleIdentifier == "com.example.MangaReader12.ipcprobe"
    }

    private func sectionType(_ displayedSection: Int) -> Int {
        return isIPCDiagnostic && displayedSection == 1 ? 5 : displayedSection
    }

    private var installedBuild: Int {
        let raw = Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String
        return Int(raw ?? "") ?? 0
    }

    private var installedBuildLabel: String {
        return "Build " + String(installedBuild)
    }

    private var availableUpdate: WebReaderVerifiedUpdate? {
        if case .updateAvailable(let update) = lastResult { return update }
        return nil
    }

    init() {
        super.init(style: .grouped)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Atualizações do WebReader"
        if isIPCDiagnostic { title = "WebReader IPC Test" }
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 72
        applyTheme()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        // Leaving this screen cannot accidentally trigger a later action.
        checker?.cancel()
        stager?.cancel()
        httpsProbe?.cancel()
        httpsProbe = nil
        testingHTTPS = false
    }

    override func numberOfSections(in tableView: UITableView) -> Int {
        return isIPCDiagnostic ? 2 : 6
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        let source = sectionType(section)
        if source == 1 { return 2 }
        if source == 2 { return availableUpdate != nil ? 4 : 1 }
        if source == 4 {
            return 1 + httpsResults.count + (httpsResults.isEmpty ? 0 : 1)
        }
        if source == 5 { return 3 }
        return 1
    }

    override func tableView(
        _ tableView: UITableView, titleForHeaderInSection section: Int
    ) -> String? {
        switch sectionType(section) {
        case 0: return "VERSÃO INSTALADA"
        case 1: return "CANAL DO APLICATIVO"
        case 2: return "ATUALIZAÇÕES DISPONÍVEIS"
        case 3: return "SEGURANÇA"
        case 4: return "DIAGNÓSTICO HTTPS (iOS 12)"
        default: return "HELPER LOCAL (DIAGNÓSTICO)"
        }
    }

    override func tableView(
        _ tableView: UITableView, titleForFooterInSection section: Int
    ) -> String? {
        switch sectionType(section) {
        case 1:
            return "Somente GitHub Releases públicos do repositório WebReader " +
                "são consultados. Commits ou artefatos temporários do " +
                "GitHub Actions não são atualizações disponíveis."
        case 2:
            return "O download exige sua confirmação e validação de SHA-256/IPA. " +
                "A instalação pelo Chimera ainda está em desenvolvimento."
        case 5:
            return "Este teste usa um socket local no sandbox e só envia " +
                "PING/PONG. Não verifica assinatura de código, não inicia um " +
                "helper, não instala IPA e não concede permissões do Chimera."
        case 4:
            return "Teste manual de TLS padrão usando apenas HEAD. " +
                "Uma resposta HTTP, inclusive 403/404, indica conexão HTTPS " +
                "com aquele servidor, não a existência de uma atualização. " +
                "A quarta sonda testa um asset público do GitHub CLI com " +
                "HEAD/redirects restritos, mas não baixa nem valida a IPA WebReader."
        default:
            return nil
        }
    }

    override func tableView(
        _ tableView: UITableView, cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "AppUpdatesCell")
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: "AppUpdatesCell")
        ThemeManager.shared.style(cell: cell)
        cell.textLabel?.numberOfLines = 0
        cell.detailTextLabel?.numberOfLines = 0
        cell.accessoryView = nil
        cell.accessibilityHint = nil
        cell.accessibilityLabel = nil
        cell.accessoryType = .none
        cell.selectionStyle = .none
        cell.isUserInteractionEnabled = true
        cell.textLabel?.textColor = ThemeManager.shared.palette.primaryText
        cell.detailTextLabel?.textColor = ThemeManager.shared.palette.secondaryText

        switch (sectionType(indexPath.section), indexPath.row) {
        case (0, _):
            cell.textLabel?.text = installedBuildLabel
            cell.detailTextLabel?.text = "WebReader • iOS 12.0 ou posterior"
            cell.accessibilityLabel = "Versão instalada: " + installedBuildLabel

        case (1, 0):
            cell.textLabel?.text = "Canal de lançamentos"
            cell.detailTextLabel?.text =
                "GitHub Releases público • HTTPS • verificação manual"

        case (1, 1):
            cell.textLabel?.text = "Abrir GitHub Releases"
            cell.detailTextLabel?.text = "Consultar lançamentos no GitHub"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        case (2, 0):
            cell.textLabel?.text = checking ?
                "Verificando GitHub Releases…" : "Verificar atualizações"
            cell.detailTextLabel?.text = checking ?
                "Consultando Release e hash SHA-256" : statusDescription
            if !checking {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
                cell.accessibilityHint =
                    "Consulta o GitHub; download só após confirmação"
            }

        case (2, 1):
            if let update = availableUpdate {
                cell.textLabel?.text = "Novidades da Build " + String(update.build)
                cell.detailTextLabel?.text = update.releaseNotes.joined(
                    separator: "\n"
                )
            }

        case (2, 2):
            if stagingIPA {
                cell.textLabel?.text = "Baixando e validando IPA…"
                cell.detailTextLabel?.text = "Saia da tela para cancelar"
            } else if let file = stagedIPAURL,
                FileManager.default.fileExists(atPath: file.path) {
                cell.textLabel?.text = "Compartilhar IPA verificada"
                cell.detailTextLabel?.text =
                    "Exportar para instalação manual; não instala sozinha"
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            } else {
                cell.textLabel?.text = "Baixar IPA verificada"
                cell.detailTextLabel?.text = ipaStatus
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (2, 3):
            if let file = stagedIPAURL,
                FileManager.default.fileExists(atPath: file.path) {
                cell.textLabel?.text = "Copiar comando appinst (manual)"
                cell.detailTextLabel?.text =
                    "Somente para teste • a instalação não será iniciada pelo app"
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            } else {
                cell.textLabel?.text = "appinst: aguarda IPA verificada"
                cell.detailTextLabel?.text =
                    "Instalação automática ainda não ativada"
            }

        case (3, _):
            cell.textLabel?.text = "Atualizações seguras"
            cell.detailTextLabel?.text =
                "Download de release oficial via HTTPS, SHA-256 e inspeção IPA. " +
                "Não há assinatura independente do editor neste modo. " +
                "Instalação automática via appinst ainda indisponível."

        case (4, 0):
            cell.textLabel?.text = testingHTTPS ?
                "Testando conexões HTTPS…" : "Testar HTTPS do GitHub"
            cell.detailTextLabel?.text =
                "Somente HEAD • TLS padrão • nenhum download"
            if !testingHTTPS {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (4, let row) where row <= httpsResults.count:
            let item = httpsResults[row - 1]
            cell.textLabel?.text = item.label
            cell.detailTextLabel?.text = item.reportLine
            cell.accessibilityLabel = item.reportLine

        case (4, _):
            cell.textLabel?.text = "Copiar relatório HTTPS"
            cell.detailTextLabel?.text =
                "Somente hosts, códigos HTTP e erros de conexão"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        case (5, 0):
            cell.textLabel?.text = testingHelper ?
                "Testando comunicação local…" : "Testar helper de diagnóstico"
            cell.detailTextLabel?.text = helperReport
            if !testingHelper {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (5, 1):
            cell.textLabel?.text = "Copiar pasta para o teste local"
            cell.detailTextLabel?.text =
                "Só para teste manual do PING/PONG; não é caminho de instalação"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        case (5, 2):
            cell.textLabel?.text = "Copiar relatório do helper"
            cell.detailTextLabel?.text =
                "Resultado, versão e iOS • sem copiar caminho privado"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        default:
            break
        }
        return cell
    }

    private var statusDescription: String {
        switch lastResult {
        case .disabled:
            return "Canal de consulta desabilitado"
        case .upToDate:
            return "Nenhum release assinado mais recente encontrado"
        case .updateAvailable(let update):
            return "Build " + String(update.build) +
                " encontrada no GitHub • instalação ainda indisponível"
        case .failed(let error):
            switch error {
            case .busy: return "Uma verificação já está em andamento"
            case .unsupportedManifestURL: return "Endereço do canal não autorizado"
            case .transport: return "Não foi possível acessar o manifesto HTTPS"
            case .unexpectedHTTPStatus(let status):
                return "Resposta HTTP " + String(status)
            case .unexpectedContentType:
                return "Resposta em formato não permitido"
            case .oversizedResponse:
                return "Manifesto maior que o limite permitido"
            case .invalidSignedManifest:
                return "A assinatura ou o conteúdo do manifesto é inválido"
            case .invalidGitHubRelease:
                return "GitHub Release sem IPA/hash confiável ou metadados inválidos"
            }
        }
    }

    override func tableView(
        _ tableView: UITableView, didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        let selectedSection = sectionType(indexPath.section)
        if selectedSection == 4 {
            if indexPath.row == 0 {
                startHTTPSProbe()
            } else if !httpsResults.isEmpty &&
                indexPath.row == httpsResults.count + 1 {
                copyHTTPSReport()
            }
            return
        }
        if selectedSection == 5 {
            if indexPath.row == 0 { startHelperProbe() }
            if indexPath.row == 1 { copyHelperDirectory() }
            if indexPath.row == 2 { copyHelperReport() }
            return
        }
        if selectedSection == 1, indexPath.row == 1 {
            let url = URL(string:
                "https://github.com/AugustoArbulu/MangaReader12/releases"
            )!
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
            return
        }
        if selectedSection == 2, indexPath.row == 2 {
            guard !stagingIPA else { return }
            if let file = stagedIPAURL,
               FileManager.default.fileExists(atPath: file.path) {
                shareStagedIPA(file)
            } else {
                confirmIPADownload()
            }
            return
        }
        if selectedSection == 2, indexPath.row == 3 {
            if let file = stagedIPAURL,
               FileManager.default.fileExists(atPath: file.path) {
                copyManualAppinstCommand(file)
            }
            return
        }
        guard selectedSection == 2, indexPath.row == 0,
              !isIPCDiagnostic, !checking
        else { return }
        checking = true
        tableView.reloadData()

        let current = WebReaderUpdateChecker(
            installedBuild: installedBuild,
            installedIOS: ProcessInfo.processInfo.operatingSystemVersion,
            usePublicGitHubReleases: true
        )
        checker = current
        current.check { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self, self.checker === current else { return }
                self.checker = nil
                self.checking = false
                self.lastResult = result
                self.tableView.reloadData()
            }
        }
    }

    private func confirmIPADownload() {
        guard !isIPCDiagnostic, !stagingIPA,
              let update = availableUpdate,
              update.provenance == .publicGitHubRelease ||
                WebReaderUpdateChannel.isConfigured else { return }
        let mb = Double(update.ipaSize) / (1024 * 1024)
        let message = String(format:
            "Build %d • %.1f MB. Baixar e validar agora? " +
            "O aplicativo NÃO será instalado automaticamente.", update.build, mb)
        let alert = UIAlertController(title: "Baixar IPA?", message: message,
            preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Baixar", style: .default) {
            [weak self] _ in self?.startIPADownload(update)
        })
        present(alert, animated: true)
    }

    private func startIPADownload(_ update: WebReaderVerifiedUpdate) {
        guard !isIPCDiagnostic, !stagingIPA,
              update.provenance == .publicGitHubRelease ||
                WebReaderUpdateChannel.isConfigured,
              let current = availableUpdate,
              current.build == update.build, current.sha256 == update.sha256
        else { return }
        stagingIPA = true
        ipaStatus = "Baixando e verificando hash, versão e conteúdo da IPA"
        tableView.reloadData()
        let downloader = WebReaderIPAStager(verifiedUpdate: update)
        stager = downloader
        downloader.stage { [weak self, weak downloader] result in
            DispatchQueue.main.async {
                guard let self = self, let downloader = downloader,
                      self.stager === downloader else { return }
                self.stager = nil
                self.stagingIPA = false
                switch result {
                case .staged(let url):
                    self.stagedIPAURL = url
                    self.ipaStatus = "IPA verificada e salva no aparelho"
                case .failed(let failure):
                    self.ipaStatus = self.stageFailureMessage(failure)
                }
                self.tableView.reloadData()
            }
        }
    }

    private func stageFailureMessage(_ failure: WebReaderIPAStageFailure) -> String {
        switch failure {
        case .disabled: return "Canal de lançamentos assinado não configurado"
        case .busy: return "Já existe um download em andamento"
        case .invalidRelease: return "Release fora das regras do WebReader"
        case .storage: return "Não foi possível salvar a IPA"
        case .transport: return "Download HTTPS não concluído"
        case .redirectRejected: return "Redirecionamento de download não permitido"
        case .unexpectedHTTPStatus(let code): return "Resposta HTTP " + String(code)
        case .unexpectedContentType: return "Formato HTTP inesperado"
        case .sizeMismatch: return "Tamanho da IPA não corresponde ao manifesto"
        case .integrityMismatch: return "SHA-256 da IPA incorreto"
        case .invalidIPA: return "Estrutura ou identidade da IPA inválida"
        }
    }

    private func shareStagedIPA(_ url: URL) {
        guard !isIPCDiagnostic,
              FileManager.default.fileExists(atPath: url.path) else { return }
        let activity = UIActivityViewController(activityItems: [url],
            applicationActivities: nil)
        if let popover = activity.popoverPresentationController {
            popover.sourceView = tableView
            popover.sourceRect = tableView.rectForRow(
                at: IndexPath(row: 2, section: 2))
        }
        present(activity, animated: true)
    }

    private func copyManualAppinstCommand(_ file: URL) {
        guard !isIPCDiagnostic, let update = availableUpdate,
              update.provenance == .publicGitHubRelease,
              stagedIPAURL == file,
              FileManager.default.fileExists(atPath: file.path)
        else { return }
        // Escape a POSIX single-quoted path. We only copy; never execute it.
        let quotedPath = "'" +
            file.path.replacingOccurrences(of: "'", with: "'\\''") + "'"
        UIPasteboard.general.string = "appinst " + quotedPath
        let alert = UIAlertController(
            title: "Comando copiado",
            message: "A IPA já foi baixada e verificada. O comando não foi " +
                "executado. Antes de atualizar o WebReader principal, " +
                "teste o appinst em um aplicativo descartável e faça backup.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    private func startHTTPSProbe() {
        guard !testingHTTPS else { return }
        testingHTTPS = true
        httpsResults = []
        tableView.reloadData()

        let current = WebReaderReleaseHTTPSProbe()
        httpsProbe = current
        current.run { [weak self] values in
            DispatchQueue.main.async {
                guard let self = self, self.httpsProbe === current else {
                    return
                }
                self.httpsProbe = nil
                self.testingHTTPS = false
                self.httpsResults = values
                self.tableView.reloadData()
            }
        }
    }

    private func startHelperProbe() {
        guard !testingHelper else { return }
        testingHelper = true
        helperReport = "Conexão local; nenhuma operação privilegiada"
        tableView.reloadData()
        WebReaderHelperPingProbe.run { [weak self] result in
            guard let self = self else { return }
            self.testingHelper = false
            self.helperReport = result.report
            self.tableView.reloadData()
        }
    }

    private func copyHelperDirectory() {
        UIPasteboard.general.string =
            WebReaderHelperPingProbe.diagnosticDirectory.path
        let alert = UIAlertController(
            title: "Pasta copiada",
            message: "Somente para teste manual do helper PING/PONG. " +
                "Esse caminho não autoriza nenhuma instalação.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    private func copyHelperReport() {
        let version = ProcessInfo.processInfo.operatingSystemVersion
        let ios = String(version.majorVersion) + "." +
            String(version.minorVersion) + "." + String(version.patchVersion)
        let lines = [
            "WebReader • Diagnóstico IPC não privilegiado",
            "App: " + installedBuildLabel,
            "iOS: " + ios,
            "Bundle: " + (Bundle.main.bundleIdentifier ?? "desconhecido"),
            "Socket: UNIX local • PING/PONG somente",
            "Pasta (comprimento UTF-8): " +
                String(WebReaderHelperPingProbe.diagnosticDirectory.path.utf8.count),
            helperReport,
            "Sem appinst, root, download ou instalação"
        ]
        UIPasteboard.general.string = lines.joined(separator: "\n")
        let alert = UIAlertController(
            title: "Relatório IPC copiado",
            message: "Pode compartilhar o resultado sem expor o caminho da pasta.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    private func copyHTTPSReport() {
        guard !httpsResults.isEmpty else { return }
        let version = ProcessInfo.processInfo.operatingSystemVersion
        let ios = String(version.majorVersion) + "." +
            String(version.minorVersion) + "." + String(version.patchVersion)
        let lines = [
            "WebReader • Diagnóstico HTTPS somente leitura",
            "App: " + installedBuildLabel,
            "iOS: " + ios,
            "HTTPS padrão; somente HEAD; sem login, IPA ou instalação"
        ] + httpsResults.map { $0.reportLine }
        UIPasteboard.general.string = lines.joined(separator: "\n")
        let alert = UIAlertController(
            title: "Relatório copiado",
            message: "Os resultados HTTPS estão prontos para compartilhar.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

extension WebReaderAppUpdatesViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
