import UIKit

/// In-app home for future signed WebReader application releases.
/// This is deliberately SEPARATE from the existing chapter Updates tab and
/// background Library updater. No appinst, IPA install, download, or IPC here.
final class WebReaderAppUpdatesViewController: UITableViewController {
    private var checker: WebReaderUpdateChecker?
    private var checking = false
    private var lastResult: WebReaderUpdateCheckResult = .disabled

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
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 72
        applyTheme()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        // Leaving this screen cannot accidentally trigger a later action.
        checker?.cancel()
    }

    override func numberOfSections(in tableView: UITableView) -> Int {
        return 4
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return section == 2 && availableUpdate != nil ? 2 : 1
    }

    override func tableView(
        _ tableView: UITableView, titleForHeaderInSection section: Int
    ) -> String? {
        switch section {
        case 0: return "VERSÃO INSTALADA"
        case 1: return "CANAL DO APLICATIVO"
        case 2: return "ATUALIZAÇÕES DISPONÍVEIS"
        default: return "SEGURANÇA"
        }
    }

    override func tableView(
        _ tableView: UITableView, titleForFooterInSection section: Int
    ) -> String? {
        switch section {
        case 1:
            return "Apenas releases publicados e autenticados do WebReader " +
                "serão reconhecidos. Commits ou artefatos temporários do " +
                "GitHub Actions não são atualizações disponíveis."
        case 2:
            return "Consultar a versão não baixa nem instala uma IPA. " +
                "A instalação pelo Chimera ainda está em desenvolvimento."
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
        cell.accessoryType = .none
        cell.selectionStyle = .none
        cell.isUserInteractionEnabled = true
        cell.textLabel?.textColor = ThemeManager.shared.palette.primaryText
        cell.detailTextLabel?.textColor = ThemeManager.shared.palette.secondaryText

        switch (indexPath.section, indexPath.row) {
        case (0, _):
            cell.textLabel?.text = installedBuildLabel
            cell.detailTextLabel?.text = "WebReader • iOS 12.0 ou posterior"
            cell.accessibilityLabel = "Versão instalada: " + installedBuildLabel

        case (1, _):
            cell.textLabel?.text = "Canal de lançamentos"
            if WebReaderUpdateChannel.isConfigured {
                cell.detailTextLabel?.text = "Assinatura configurada • consulta manual"
            } else {
                cell.detailTextLabel?.text =
                    "Não ativado • aguardando publicação e chave confiável"
            }

        case (2, 0):
            if checking {
                cell.textLabel?.text = "Verificando…"
                cell.detailTextLabel?.text = "Validando o manifesto assinado"
            } else if !WebReaderUpdateChannel.isConfigured {
                cell.textLabel?.text = "Verificação indisponível"
                cell.detailTextLabel?.text =
                    "O canal oficial ainda não está configurado"
            } else {
                cell.textLabel?.text = "Verificar atualizações"
                cell.detailTextLabel?.text = statusDescription
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
                cell.accessibilityHint =
                    "Consulta somente o manifesto assinado; não instala o app"
            }

        case (2, 1):
            if let update = availableUpdate {
                cell.textLabel?.text = "Novidades da Build " + String(update.build)
                cell.detailTextLabel?.text = update.releaseNotes.joined(
                    separator: "\n"
                )
            }

        default:
            cell.textLabel?.text = "Atualizações seguras"
            cell.detailTextLabel?.text =
                "O download e a instalação pelo Chimera só serão " +
                "habilitados depois da validação do canal e do instalador."
        }
        return cell
    }

    private var statusDescription: String {
        switch lastResult {
        case .disabled:
            return "Canal ainda não ativado"
        case .upToDate:
            return "Nenhum release assinado mais recente encontrado"
        case .updateAvailable(let update):
            return "Build " + String(update.build) +
                " identificada e autenticada • instalação indisponível"
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
            }
        }
    }

    override func tableView(
        _ tableView: UITableView, didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        guard indexPath.section == 2, indexPath.row == 0,
              WebReaderUpdateChannel.isConfigured, !checking
        else { return }
        checking = true
        tableView.reloadData()

        let current = WebReaderUpdateChecker(
            installedBuild: installedBuild,
            installedIOS: ProcessInfo.processInfo.operatingSystemVersion
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
}

extension WebReaderAppUpdatesViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
