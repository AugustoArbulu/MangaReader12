import UIKit

/// In-app release discovery and manual IPA export; public GitHub metadata is
/// NOT an independently signed publisher manifest.
/// This is deliberately SEPARATE from the existing chapter Updates tab and
/// background Library updater. This screen verifies SHA/ZIP metadata for
/// manually exported IPAs; it never installs or runs appinst.
final class WebReaderAppUpdatesViewController: UITableViewController, UIDocumentPickerDelegate {
    private var checker: WebReaderUpdateChecker?
    private var signedChecker: WebReaderProductionSignedReleaseChecker?
    private var signedChannelBusy = false
    private var signedChannelStatus =
        "Chave editorial independente ainda não provisionada • sem requisições"
    private var checking = false
    private var lastResult: WebReaderUpdateCheckResult = .disabled
    private var httpsProbe: WebReaderReleaseHTTPSProbe?
    private var testingHTTPS = false
    private var httpsResults: [WebReaderHTTPSProbeResult] = []
    private var testingHelper = false
    private var helperReport = "Ainda não testado"
    private var testingAppinstBridge = false
    private var appinstBridgeReport = "Ponte appinst não testada"
    private var pairingInProgress = false
    private var pairingReport = "Pareamento temporário ainda não testado"
    private var stager: WebReaderIPAStager?
    private var stagingIPA = false
    private var downloadSessionID: UUID?
    private var verifyingExport = false
    private var stagedIPAURL: URL?
    private var ipaStatus = "Aguardando consulta aos metadados do GitHub"
    private var stagedSHA256: String?
    // Local, manually selected QA IPAs are separate from GitHub releases:
    // a matching owner-entered SHA-256 does NOT authenticate the publisher.
    private var manualIPAReview: WebReaderLocalIPAReview?
    private var manualImportInProgress = false
    private var manualReviewInProgress = false
    private var manualExpectedBuild: Int?
    private var manualExpectedSHA256: String?
    private var manualImportStatus = "Escolha uma IPA e informe SHA-256 externo"
    private var localQASpaceBusy = false
    private var localQASpaceStatus = "Toque para contar cópias antigas e espaço ocupado"
    private var releaseCacheBusy = false
    private var didInspectRecoveryOnOpen = false
    private var releaseCacheStatus = "Toque para conferir downloads antigos do atualizador"
    private var runningOneAppTest = false
    private var oneAppReport = "Toque em Testar Chimera para começar."

    // The isolated com.example.MangaReader12.ipcprobe IPA exposes only
    // version info and the local PING diagnostic; never the release controls.
    private var isChimeraOneApp: Bool {
        return Bundle.main.bundleIdentifier ==
            "com.example.MangaReader12.chimeraoneapp"
    }

    private var isIPCDiagnostic: Bool {
        return Bundle.main.bundleIdentifier == "com.example.MangaReader12.ipcprobe" ||
            isChimeraOneApp
    }

    private func sectionType(_ displayedSection: Int) -> Int {
        return isIPCDiagnostic && displayedSection == 1 ? 5 : displayedSection
    }

    private var pairingDiagnosticAvailable: Bool {
        return Bundle.main.bundleIdentifier == "com.example.MangaReader12.ipcprobe" &&
            installedBuild >= 59
    }

    private var build60DisposableAvailable: Bool {
        return Bundle.main.bundleIdentifier == "com.example.MangaReader12.ipcprobe" &&
            installedBuild >= 60
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
        if isChimeraOneApp { title = "WebReader Chimera Test" }
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 72
        applyTheme()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)
        // After an app kill, only inspect old partial downloads. Never
        // resume or delete on startup. User confirmation remains mandatory
        // for any later removal of aged cache files.
        guard !isIPCDiagnostic, !didInspectRecoveryOnOpen else { return }
        didInspectRecoveryOnOpen = true
        inspectReleaseCache(cleanup: false)
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        // Leaving this screen cannot accidentally trigger a later action.
        checker?.cancel()
        signedChecker?.cancel()
        // Invalidate any progress dispatch that was queued before leaving.
        // Its session ID must no longer match the current screen state.
        downloadSessionID = nil
        stager?.cancel()
        httpsProbe?.cancel()
        httpsProbe = nil
        testingHTTPS = false
    }

    override func numberOfSections(in tableView: UITableView) -> Int {
        return isIPCDiagnostic ? 2 : 7
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        let source = sectionType(section)
        if isChimeraOneApp {
            return source == 5 ? 2 : 1
        }
        if source == 1 { return 4 }
        if source == 6 { return 8 }
        if source == 2 { return availableUpdate != nil ? 6 : 1 }
        if source == 3 { return 6 }
        if source == 4 {
            return 1 + httpsResults.count + (httpsResults.isEmpty ? 0 : 1)
        }
        if source == 5 { return build60DisposableAvailable ? 6 : (pairingDiagnosticAvailable ? 5 : 4) }
        return 1
    }

    override func tableView(
        _ tableView: UITableView, titleForHeaderInSection section: Int
    ) -> String? {
        if isChimeraOneApp && sectionType(section) == 5 {
            return "TESTE AUTOMÁTICO (SEM INSTALAÇÃO)"
        }
        switch sectionType(section) {
        case 0: return "VERSÃO INSTALADA"
        case 1: return "CANAL DO APLICATIVO"
        case 2: return "ATUALIZAÇÕES DISPONÍVEIS"
        case 3: return "SEGURANÇA"
        case 4: return "DIAGNÓSTICO HTTPS (iOS 12)"
        case 6: return "IPA LOCAL (ARQUIVOS OU FILZA)"
        default: return "HELPER LOCAL (DIAGNÓSTICO)"
        }
    }

    override func tableView(
        _ tableView: UITableView, titleForFooterInSection section: Int
    ) -> String? {
        if isChimeraOneApp && sectionType(section) == 5 {
            return "Um único teste local. Não baixa IPAs e não executa appinst. " +
                "A Build 56 principal permanece instalada separadamente."
        }
        switch sectionType(section) {
        case 1:
            return "A consulta pública usa apenas GitHub Releases, sem " +
                "autenticação editorial. O canal assinado exige chave e pin " +
                "conferidos independentemente; Builds privadas do Actions " +
                "continuam manuais, sem token no aplicativo."
        case 2:
            return "O download exige sua confirmação e validação de SHA-256/IPA. " +
                "A instalação pelo Chimera ainda está em desenvolvimento."
        case 6:
            return "Use o SHA-256 obtido separadamente no GitHub Actions. " +
                "O arquivo local é copiado para uma pasta exclusiva de QA e " +
                "sua estrutura é verificada. Isso NÃO autentica o publicador " +
                "nem permite instalação automática."
        case 5:
            return "Testes locais PING/PONG, sem instalação. " +
                "A ponte appinst usa um socket separado e encerra depois " +
                "de uma conexão. Para instalar, é necessário reiniciá-la."
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

        if isChimeraOneApp && sectionType(indexPath.section) == 5 {
            if indexPath.row == 0 {
                cell.textLabel?.text = runningOneAppTest ?
                    "Testando Chimera…" : "Testar Chimera"
                cell.detailTextLabel?.text = oneAppReport
                if !runningOneAppTest {
                    cell.accessoryType = .disclosureIndicator
                    cell.selectionStyle = .default
                }
            } else {
                cell.textLabel?.text = "Copiar resultado"
                cell.detailTextLabel?.text = "Cole o relatório aqui no chat"
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }
            return cell
        }

        switch (sectionType(indexPath.section), indexPath.row) {
        case (0, _):
            cell.textLabel?.text = installedBuildLabel
            cell.detailTextLabel?.text = "WebReader • iOS 12.0 ou posterior"
            cell.accessibilityLabel = "Versão instalada: " + installedBuildLabel

        case (1, 0):
            cell.textLabel?.text = "Canal de lançamentos"
            cell.detailTextLabel?.text =
                "GitHub Releases • HTTPS • sem autenticação editorial independente"

        case (1, 1):
            cell.textLabel?.text = "Abrir GitHub Releases"
            cell.detailTextLabel?.text = "Consultar lançamentos no GitHub"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        case (1, 2):
            cell.textLabel?.text = signedChannelBusy ?
                "Verificando assinatura editorial…" : "Verificar canal assinado"
            cell.detailTextLabel?.text = signedChannelStatus
            if !signedChannelBusy {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (1, 3):
            cell.textLabel?.text = "Abrir Builds privadas no GitHub Actions"
            cell.detailTextLabel?.text =
                "Abrir no navegador com sua conta GitHub • IPA manual via Filza"
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
                cell.textLabel?.text = "Cancelar download em andamento"
                cell.detailTextLabel?.text = ipaStatus +
                    "\nToque para interromper • arquivo parcial será removido"
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            } else if verifyingExport {
                cell.textLabel?.text = "Conferindo IPA antes de compartilhar…"
                cell.detailTextLabel?.text = "Verificando novamente SHA-256, ZIP e Bundle ID"
            } else if let file = stagedIPAURL,
                FileManager.default.fileExists(atPath: file.path) {
                cell.textLabel?.text = "Compartilhar IPA conferida"
                cell.detailTextLabel?.text =
                    "Salvar pelo menu Compartilhar; instalar manualmente no Filza"
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            } else {
                cell.textLabel?.text = "Baixar e conferir IPA"
                cell.detailTextLabel?.text = ipaStatus
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (2, 3):
            cell.textLabel?.text = "Como instalar pelo Filza"
            cell.detailTextLabel?.text =
                "Instruções para abrir a IPA exportada sem computador"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        case (2, 4):
            cell.textLabel?.text = "Instalação pelo Chimera bloqueada"
            cell.detailTextLabel?.text =
                "Aguardando política independente de autorização e chave editorial"
            cell.accessoryType = .none
            cell.selectionStyle = .none

        case (2, 5):
            cell.textLabel?.text = "Copiar recibo de integridade da IPA"
            cell.detailTextLabel?.text = stagedIPAURL == nil ?
                "Disponível após baixar e conferir uma IPA • sem instalação" :
                "Confere o arquivo novamente e copia Build, tamanho e SHA-256"
            if stagedIPAURL != nil && !stagingIPA && !verifyingExport {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (3, 0):
            cell.textLabel?.text = "Segurança das atualizações"
            cell.detailTextLabel?.text =
                "GitHub Releases via HTTPS e SHA-256 não autenticam o editor"
        case (3, 1):
            cell.textLabel?.text = "Assinatura editorial"
            cell.detailTextLabel?.text = WebReaderUpdaterSecuritySnapshot.keyDescription
        case (3, 2):
            cell.textLabel?.text = "Autorização do Chimera"
            cell.detailTextLabel?.text = WebReaderUpdaterSecuritySnapshot.peerDescription
        case (3, 3):
            cell.textLabel?.text = "Operações permitidas"
            cell.detailTextLabel?.text =
                WebReaderUpdaterSecuritySnapshot.allowedDescription + "\n" +
                WebReaderUpdaterSecuritySnapshot.deniedDescription
        case (3, 4):
            cell.textLabel?.text = "Copiar diagnóstico de segurança"
            cell.detailTextLabel?.text =
                "Resumo sem caminhos, chaves privadas ou dados da biblioteca"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        case (3, 5):
            cell.textLabel?.text = "Copiar roteiro de testes físicos"
            cell.detailTextLabel?.text =
                "Biblioteca, Wi-Fi desligado, leitor, IPA e segurança • tudo não testado"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

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
            cell.textLabel?.text = "Copiar pasta do socket (Chimera)"
            cell.detailTextLabel?.text =
                "Pasta WR do app • usada pelos dois testes locais"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        case (5, 2):
            cell.textLabel?.text = "Copiar relatório do helper"
            cell.detailTextLabel?.text =
                "Resultado, versão e iOS • sem copiar caminho privado"
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default

        case (5, 3):
            if isIPCDiagnostic {
                cell.textLabel?.text = testingAppinstBridge ?
                    "Testando TCP localhost…" : "Testar ponte localhost (PING)"
            } else {
                cell.textLabel?.text = testingAppinstBridge ?
                    "Testando socket appinst…" : "Testar ponte appinst (PING)"
            }
            cell.detailTextLabel?.text = appinstBridgeReport
            if !testingAppinstBridge {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (5, 4):
            if pairingDiagnosticAvailable {
                cell.textLabel?.text = pairingInProgress ?
                    "Validando código temporário…" : "Testar código temporário (sem instalar)"
                cell.detailTextLabel?.text = pairingReport
                if !pairingInProgress {
                    cell.accessoryType = .disclosureIndicator
                    cell.selectionStyle = .default
                }
            }

        case (5, 5):
            if build60DisposableAvailable {
                cell.textLabel?.text = "Teste completo Build 60"
                cell.detailTextLabel?.text =
                    "Copiar roteiro único • app descartável v1 → v2 • sem tocar no WebReader"
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (6, 0):
            cell.textLabel?.text = manualImportInProgress ?
                "Conferindo IPA local…" : "Importar IPA local para conferir"
            cell.detailTextLabel?.text =
                "Arquivos/Filza • informe Build e SHA-256 do artefato QA"
            if !manualImportInProgress && !manualReviewInProgress {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (6, 1):
            if let receipt = manualIPAReview {
                cell.textLabel?.text = manualReviewInProgress ?
                    "Conferindo novamente antes de compartilhar…" :
                    "Compartilhar IPA local conferida"
                cell.detailTextLabel?.text =
                    "Build " + String(receipt.build) + " • " +
                    String(receipt.zipEntries) + " entradas ZIP • uso manual"
                if !manualReviewInProgress && !manualImportInProgress {
                    cell.accessoryType = .disclosureIndicator
                    cell.selectionStyle = .default
                }
            } else {
                cell.textLabel?.text = "Nenhuma IPA local conferida"
                cell.detailTextLabel?.text = manualImportStatus
            }

        case (6, 2):
            cell.textLabel?.text = "Copiar SHA-256 conferido"
            cell.detailTextLabel?.text = manualIPAReview == nil ?
                "Disponível depois de conferir o arquivo" :
                "64 caracteres • comparar com o checksum do GitHub Actions"
            if manualIPAReview != nil && !manualImportInProgress &&
                !manualReviewInProgress {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (6, 3):
            cell.textLabel?.text = "Descartar cópia local de QA"
            cell.detailTextLabel?.text = manualIPAReview == nil ?
                "Nenhum arquivo para descartar" :
                "Remove apenas a cópia importada, nunca a biblioteca"
            if manualIPAReview != nil && !manualImportInProgress &&
                !manualReviewInProgress && !localQASpaceBusy {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (6, 4):
            cell.textLabel?.text = localQASpaceBusy ?
                "Conferindo armazenamento local…" : "Espaço ocupado por IPAs antigas"
            cell.detailTextLabel?.text = localQASpaceStatus
            if !localQASpaceBusy && !manualImportInProgress &&
                !manualReviewInProgress {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (6, 5):
            cell.textLabel?.text = "Limpar cópias antigas de QA…"
            cell.detailTextLabel?.text =
                "Confirmação obrigatória • apenas arquivos de QA com mais de 24 h"
            if !localQASpaceBusy && !manualImportInProgress &&
                !manualReviewInProgress {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (6, 6):
            cell.textLabel?.text = releaseCacheBusy ?
                "Conferindo downloads do atualizador…" :
                "Espaço usado por downloads antigos"
            cell.detailTextLabel?.text = releaseCacheStatus
            if !releaseCacheBusy && !stagingIPA && !verifyingExport &&
                !localQASpaceBusy {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

        case (6, 7):
            cell.textLabel?.text = "Limpar downloads antigos…"
            cell.detailTextLabel?.text =
                "Só cache WebReaderUpdates com mais de 24 h • sem retomada parcial"
            if !releaseCacheBusy && !stagingIPA && !verifyingExport &&
                !localQASpaceBusy {
                cell.accessoryType = .disclosureIndicator
                cell.selectionStyle = .default
            }

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
            return "Nenhuma Build mais recente encontrada nos metadados consultados"
        case .updateAvailable(let update):
            return "Build " + String(update.build) +
                " encontrada • verificar IPA antes da instalação manual"
        case .failed(let error):
            switch error {
            case .busy: return "Uma verificação já está em andamento"
            case .unsupportedManifestURL: return "Endereço do canal não autorizado"
            case .transport: return "Não foi possível acessar o manifesto HTTPS"
            case .unexpectedHTTPStatus(let status):
                if status == 404 {
                    return "GitHub Releases indisponível: sem release ou repositório privado"
                }
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
        if isChimeraOneApp && selectedSection == 5 {
            if indexPath.row == 0 { runOneAppTest() }
            if indexPath.row == 1 { copyOneAppReport() }
            return
        }
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
            if indexPath.row == 3 { testAppinstBridgeConnection() }
            if indexPath.row == 4 && pairingDiagnosticAvailable {
                promptOneTimePairingCode()
            }
            if indexPath.row == 5 && build60DisposableAvailable {
                copyBuild60DisposableProcedure()
            }
            return
        }
        if selectedSection == 6 {
            guard !localQASpaceBusy, !releaseCacheBusy else { return }
            if indexPath.row == 0 && !manualImportInProgress &&
                !manualReviewInProgress { promptLocalIPAImport() }
            if indexPath.row == 1 && !manualImportInProgress &&
                !manualReviewInProgress { shareLocalIPA() }
            if indexPath.row == 2 && !manualImportInProgress &&
                !manualReviewInProgress { copyLocalIPAHash() }
            if indexPath.row == 3 && !manualImportInProgress &&
                !manualReviewInProgress { discardLocalIPA() }
            if indexPath.row == 4 && !manualImportInProgress &&
                !manualReviewInProgress { inspectLocalQAStorage(cleanup: false) }
            if indexPath.row == 5 && !manualImportInProgress &&
                !manualReviewInProgress { inspectLocalQAStorage(cleanup: true) }
            if indexPath.row == 6 { inspectReleaseCache(cleanup: false) }
            if indexPath.row == 7 { inspectReleaseCache(cleanup: true) }
            return
        }
        if selectedSection == 3, indexPath.row == 4, !isIPCDiagnostic {
            copyUpdaterSecurityReport()
            return
        }
        if selectedSection == 3, indexPath.row == 5, !isIPCDiagnostic {
            UIPasteboard.general.string = WebReaderPhysicalQAChecklist.report(
                installedBuild: installedBuild,
                ios: ProcessInfo.processInfo.operatingSystemVersion
            )
            let alert = UIAlertController(
                title: "Roteiro copiado",
                message: "O roteiro contém campos NÃO TESTADO. Preencha somente " +
                    "após realizar cada teste; não envia nem lê a biblioteca.",
                preferredStyle: .alert
            )
            alert.addAction(UIAlertAction(title: "OK", style: .default))
            present(alert, animated: true)
            return
        }
        if selectedSection == 1, indexPath.row == 1 {
            let url = URL(string:
                "https://github.com/AugustoArbulu/MangaReader12/releases"
            )!
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
            return
        }
        if selectedSection == 1, indexPath.row == 2 {
            checkSignedProductionChannel()
            return
        }
        if selectedSection == 1, indexPath.row == 3 {
            // Private GitHub Actions artifacts cannot be discovered without
            // authentication. Open GitHub in the browser; NEVER collect or
            // embed a token in iOS12 app preferences or an API request.
            let url = URL(string:
                "https://github.com/AugustoArbulu/MangaReader12/actions"
            )!
            UIApplication.shared.open(url, options: [:], completionHandler: nil)
            return
        }
        if selectedSection == 2, indexPath.row == 2 {
            if stagingIPA {
                ipaStatus = "Cancelando transferência e descartando IPA parcial…"
                // Progress is dispatched asynchronously from URLSession.
                // Invalidate its ID BEFORE stopping transfer so stale UI
                // updates cannot replace the cancellation message.
                downloadSessionID = nil
                stager?.cancel()
                tableView.reloadData()
                return
            }
            guard !verifyingExport else { return }
            if let file = stagedIPAURL,
               FileManager.default.fileExists(atPath: file.path) {
                shareStagedIPA(file)
            } else {
                confirmIPADownload()
            }
            return
        }
        // Both rows remain non-installing. Manual Filza instructions are
        // available; privileged Chimera installation is still disabled.
        if selectedSection == 2, indexPath.row == 3 {
            showFilzaInstructions()
            return
        }
        if selectedSection == 2, indexPath.row == 4 { return }
        if selectedSection == 2, indexPath.row == 5 {
            copyStagedIPAReceipt()
            return
        }
        guard selectedSection == 2, indexPath.row == 0,
              !isIPCDiagnostic, !checking, !signedChannelBusy,
              !stagingIPA, !verifyingExport
        else { return }
        checking = true
        stagedIPAURL = nil
        stagedSHA256 = nil
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


    /// Production-only signed discovery. The shipped key and independently
    /// trusted SPKI pin are both absent. No key is imported from GitHub or
    /// user preferences, and no HTTP request occurs until owner provisioning.
    private func checkSignedProductionChannel() {
        guard !isIPCDiagnostic, !checking, !signedChannelBusy,
              !stagingIPA, !verifyingExport else { return }
        guard WebReaderProductionPublisherTrust.isProvisioned else {
            signedChannelStatus =
                "Canal bloqueado: falta chave editorial e SPKI independente"
            tableView.reloadData()
            return
        }
        signedChannelBusy = true
        signedChannelStatus = "Conferindo manifesto ECDSA P-256 assinado…"
        // Do not mix metadata from a previous unsigned public release
        // with a newly requested signed-source inspection.
        lastResult = .disabled
        stagedIPAURL = nil
        stagedSHA256 = nil
        tableView.reloadData()
        let signed = WebReaderProductionSignedReleaseChecker(
            installedBuild: installedBuild,
            installedIOS: ProcessInfo.processInfo.operatingSystemVersion
        )
        signedChecker = signed
        signed.check { [weak self, weak signed] result in
            DispatchQueue.main.async { [weak self] in
                guard let self = self, let signed = signed,
                      self.signedChecker === signed else { return }
                self.signedChecker = nil
                self.signedChannelBusy = false
                switch result {
                case .disabled:
                    self.signedChannelStatus =
                        "Canal assinado não provisionado; nenhuma atualização autenticada"
                    self.lastResult = .disabled
                case .updateAvailable(let update):
                    self.signedChannelStatus = "Manifesto editorial ECDSA verificado • Build " +
                        String(update.build) + " • instalação manual"
                    self.lastResult = .updateAvailable(update)
                case .upToDate:
                    self.signedChannelStatus =
                        "Manifesto assinado verificado • nenhuma Build mais recente"
                    self.lastResult = .upToDate
                case .failed(.unexpectedHTTPStatus(let code)):
                    self.signedChannelStatus = "Manifesto assinado indisponível • HTTP " +
                        String(code) + " • não afirmar versão atualizada"
                    self.lastResult = .disabled
                case .failed:
                    self.signedChannelStatus =
                        "Falha na autenticação ou transporte do canal assinado"
                    self.lastResult = .disabled
                }
                self.tableView.reloadData()
            }
        }
    }

    // MARK: - User-owned local IPA QA, independent of GitHub Releases

    private func promptLocalIPAImport() {
        guard !isIPCDiagnostic, !manualImportInProgress,
              !manualReviewInProgress else { return }
        let alert = UIAlertController(
            title: "Conferir IPA local",
            message: "Informe a Build e o SHA-256 exato que aparece no " +
                "artefato do GitHub Actions. Isso verifica os bytes e o pacote, " +
                "mas NÃO autentica o editor nem instala o aplicativo.",
            preferredStyle: .alert
        )
        alert.addTextField { field in
            field.placeholder = "Build (ex.: 67)"
            field.keyboardType = .numberPad
            field.autocorrectionType = .no
        }
        alert.addTextField { field in
            field.placeholder = "SHA-256 (64 caracteres hexadecimais)"
            field.keyboardType = .asciiCapable
            field.autocapitalizationType = .none
            field.autocorrectionType = .no
        }
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Selecionar IPA", style: .default) {
            [weak self, weak alert] _ in
            guard let self = self, let fields = alert?.textFields,
                  fields.count == 2 else { return }
            let rawBuild = fields[0].text?.trimmingCharacters(
                in: .whitespacesAndNewlines
            ) ?? ""
            let rawSHA = fields[1].text?.trimmingCharacters(
                in: .whitespacesAndNewlines
            ).lowercased() ?? ""
            guard rawBuild.range(
                of: "^[1-9][0-9]{0,8}$", options: .regularExpression
            ) != nil,
                  let build = Int(rawBuild), build > self.installedBuild,
                  rawSHA.range(
                    of: "^[0-9a-f]{64}$", options: .regularExpression
                  ) != nil else {
                self.manualImportStatus =
                    "Build deve ser maior que a instalada; SHA-256 deve ter 64 caracteres"
                self.tableView.reloadData()
                return
            }
            self.manualExpectedBuild = build
            self.manualExpectedSHA256 = rawSHA
            let picker = UIDocumentPickerViewController(
                documentTypes: ["public.data"], in: .import
            )
            picker.delegate = self
            picker.modalPresentationStyle = .formSheet
            self.present(picker, animated: true)
        })
        present(alert, animated: true)
    }

    func documentPicker(
        _ controller: UIDocumentPickerViewController,
        didPickDocumentsAt urls: [URL]
    ) {
        guard !isIPCDiagnostic, !manualImportInProgress,
              let source = urls.first,
              let expectedBuild = manualExpectedBuild,
              let expectedSHA = manualExpectedSHA256 else { return }
        manualExpectedBuild = nil
        manualExpectedSHA256 = nil
        manualImportInProgress = true
        manualImportStatus = "Copiando e conferindo IPA local sem instalar"
        tableView.reloadData()
        let currentBuild = installedBuild
        let currentIOS = ProcessInfo.processInfo.operatingSystemVersion
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let access = source.startAccessingSecurityScopedResource()
            defer {
                if access { source.stopAccessingSecurityScopedResource() }
            }
            var result: WebReaderLocalIPAReview?
            var failureReason =
                "IPA ou SHA-256 inválidos, versão antiga ou arquivo inacessível"
            do {
                result = try WebReaderLocalIPAReviewer.importForReview(
                    sourceURL: source, expectedBuild: expectedBuild,
                    expectedSHA256: expectedSHA,
                    installedBuild: currentBuild, installedIOS: currentIOS
                )
            } catch WebReaderLocalIPAReviewError.insufficientSpace {
                failureReason =
                    "Espaço insuficiente para copiar a IPA e manter reserva livre"
            } catch WebReaderLocalIPAReviewError.tooLarge {
                failureReason = "IPA excede o limite de 512 MB"
            } catch WebReaderLocalIPAReviewError.failedToCopy {
                failureReason = "Não foi possível criar a cópia local de QA"
            } catch {
                // Invalid identity or checksum: never stage an unaudited IPA.
            }
            DispatchQueue.main.async { [weak self] in
                guard let self = self else {
                    if let result = result {
                        WebReaderLocalIPAReviewer.discard(result)
                    }
                    return
                }
                self.manualImportInProgress = false
                if let receipt = result {
                    if let old = self.manualIPAReview {
                        WebReaderLocalIPAReviewer.discard(old)
                    }
                    self.manualIPAReview = receipt
                    self.manualImportStatus = "SHA-256, ZIP e identidade conferidos"
                } else {
                    self.manualImportStatus = failureReason
                }
                self.tableView.reloadData()
            }
        }
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        manualExpectedBuild = nil
        manualExpectedSHA256 = nil
    }

    private func shareLocalIPA() {
        guard !isIPCDiagnostic, !manualImportInProgress,
              !manualReviewInProgress, let receipt = manualIPAReview else { return }
        manualReviewInProgress = true
        tableView.reloadData()
        let currentBuild = installedBuild
        let currentIOS = ProcessInfo.processInfo.operatingSystemVersion
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let safe = (try? WebReaderLocalIPAReviewer.recheck(
                receipt, installedBuild: currentBuild,
                installedIOS: currentIOS
            )) != nil
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { return }
                self.manualReviewInProgress = false
                guard self.manualIPAReview?.copiedIPAURL ==
                    receipt.copiedIPAURL else { return }
                if !safe {
                    WebReaderLocalIPAReviewer.discard(receipt)
                    self.manualIPAReview = nil
                    self.manualImportStatus =
                        "IPA local alterada; importe e confira novamente"
                    self.tableView.reloadData()
                    return
                }
                let share = UIActivityViewController(
                    activityItems: [receipt.copiedIPAURL],
                    applicationActivities: nil
                )
                if let popover = share.popoverPresentationController {
                    let index = IndexPath(row: 1, section: 6)
                    popover.sourceView = self.tableView
                    popover.sourceRect = self.tableView.rectForRow(at: index)
                }
                self.tableView.reloadData()
                guard self.view.window != nil else { return }
                self.present(share, animated: true)
            }
        }
    }

    private func copyLocalIPAHash() {
        guard !isIPCDiagnostic, !manualImportInProgress,
              !manualReviewInProgress, let receipt = manualIPAReview else { return }
        // A cached SHA-256 is NOT evidence that the current file still has
        // those bytes. Recheck the same inode, size, ZIP and digest before
        // copying the hash, exactly as when sharing an imported IPA.
        manualReviewInProgress = true
        manualImportStatus = "Revalidando a IPA antes de copiar SHA-256…"
        tableView.reloadData()
        let currentBuild = installedBuild
        let currentIOS = ProcessInfo.processInfo.operatingSystemVersion
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let verified = (try? WebReaderLocalIPAReviewer.recheck(
                receipt, installedBuild: currentBuild, installedIOS: currentIOS
            )) != nil
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { return }
                self.manualReviewInProgress = false
                guard self.manualIPAReview?.copiedIPAURL ==
                    receipt.copiedIPAURL else { return }
                guard verified else {
                    WebReaderLocalIPAReviewer.discard(receipt)
                    self.manualIPAReview = nil
                    self.manualImportStatus =
                        "IPA local mudou • SHA-256 não copiado; importe novamente"
                    self.tableView.reloadData()
                    return
                }
                // No clipboard write is possible on a failed recheck.
                guard self.view.window != nil else {
                    self.tableView.reloadData()
                    return
                }
                UIPasteboard.general.string = receipt.expectedSHA256
                self.manualImportStatus =
                    "SHA-256 da IPA revalidada copiado • comparar com Actions"
                self.tableView.reloadData()
            }
        }
    }

    private func discardLocalIPA() {
        guard !manualImportInProgress, !manualReviewInProgress,
              let receipt = manualIPAReview else { return }
        WebReaderLocalIPAReviewer.discard(receipt)
        manualIPAReview = nil
        manualImportStatus = "Cópia de QA descartada; a biblioteca permanece intacta"
        tableView.reloadData()
    }

    // MARK: - User-confirmed stale QA copy storage management

    private func inspectLocalQAStorage(cleanup: Bool) {
        guard !isIPCDiagnostic, !localQASpaceBusy, !manualImportInProgress,
              !manualReviewInProgress else { return }
        localQASpaceBusy = true
        localQASpaceStatus = "Contando apenas arquivos da pasta QA…"
        tableView.reloadData()
        let active = manualIPAReview
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let scan = try? WebReaderLocalQAStorage.inventory(
                protected: active
            )
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { return }
                self.localQASpaceBusy = false
                guard let scan = scan else {
                    self.localQASpaceStatus =
                        "Pasta de QA indisponível ou entradas demais; nenhum arquivo apagado"
                    self.tableView.reloadData()
                    return
                }
                let mb = Double(scan.eligibleBytes) / 1_048_576
                self.localQASpaceStatus = String(
                    format: "%d cópia(s) antigas • %.1f MB • %d item(ns) preservados",
                    scan.eligible.count, mb, scan.ignoredEntries
                )
                self.tableView.reloadData()
                if cleanup { self.confirmStaleQACleanup(scan) }
            }
        }
    }

    private func confirmStaleQACleanup(_ scan: WebReaderLocalQAStorageInventory) {
        guard !isIPCDiagnostic, !manualImportInProgress,
              !manualReviewInProgress, !localQASpaceBusy,
              !scan.eligible.isEmpty else { return }
        let size = Double(scan.eligibleBytes) / 1_048_576
        let message = String(
            format: "%d cópia(s) antigas • %.1f MB. Só arquivos IPA de QA com " +
                "mais de 24 horas, dentro da pasta temporária do WebReader. " +
                "Arquivos novos, sua IPA atual, biblioteca e capítulos ficam " +
                "preservados. Deseja excluir essas cópias?",
            scan.eligible.count, size
        )
        let alert = UIAlertController(
            title: "Limpar cópias antigas de QA?", message: message,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Excluir cópias antigas",
                                      style: .destructive) { [weak self] _ in
            self?.discardStaleQAAfterConfirmation(scan)
        })
        present(alert, animated: true)
    }

    private func discardStaleQAAfterConfirmation(
        _ scan: WebReaderLocalQAStorageInventory
    ) {
        guard !isIPCDiagnostic, !localQASpaceBusy,
              !manualImportInProgress, !manualReviewInProgress else { return }
        localQASpaceBusy = true
        localQASpaceStatus = "Removendo somente cópias antigas confirmadas…"
        tableView.reloadData()
        let active = manualIPAReview
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            var removed = 0
            var released: Int64 = 0
            for candidate in scan.eligible {
                if WebReaderLocalQAStorage.discardConfirmed(
                    candidate, protected: active
                ) {
                    removed += 1
                    released += candidate.byteCount
                }
            }
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { return }
                self.localQASpaceBusy = false
                self.localQASpaceStatus = String(
                    format: "%d cópia(s) removidas • %.1f MB liberados • " +
                        "demais arquivos preservados",
                    removed, Double(released) / 1_048_576
                )
                self.tableView.reloadData()
            }
        }
    }

    // MARK: - Nonprivileged security status, without installation capabilities

    private func copyUpdaterSecurityReport() {
        guard !isIPCDiagnostic else { return }
        let ios = ProcessInfo.processInfo.operatingSystemVersion
        let version = String(ios.majorVersion) + "." +
            String(ios.minorVersion) + "." + String(ios.patchVersion)
        UIPasteboard.general.string = WebReaderUpdaterSecuritySnapshot.safeReport(
            installedBuild: installedBuild, iosVersion: version
        )
        let alert = UIAlertController(
            title: "Diagnóstico copiado",
            message: "O relatório é somente leitura e não executa instalação. " +
                "Não inclui arquivos pessoais nem credenciais.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    // MARK: - Release download cache (separate from manually imported QA IPAs)

    private func activeReleaseCacheName() -> String? {
        guard let file = stagedIPAURL,
            file.deletingLastPathComponent().standardizedFileURL ==
                WebReaderReleaseCacheStorage.defaultDirectory.standardizedFileURL
        else { return nil }
        return file.lastPathComponent
    }

    private func inspectReleaseCache(cleanup: Bool) {
        guard !isIPCDiagnostic, !releaseCacheBusy, !localQASpaceBusy,
              !stagingIPA, !verifyingExport else { return }
        releaseCacheBusy = true
        releaseCacheStatus = "Inspecionando só a pasta WebReaderUpdates…"
        tableView.reloadData()
        let protectedName = activeReleaseCacheName()
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let scan = try? WebReaderReleaseCacheStorage.inventory(
                protectedName: protectedName
            )
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { return }
                self.releaseCacheBusy = false
                guard let scan = scan else {
                    self.releaseCacheStatus =
                        "Cache indisponível ou entradas demais; nada foi removido"
                    self.tableView.reloadData()
                    return
                }
                let summary = WebReaderReleaseRecoverySummary.readOnly(scan)
                self.releaseCacheStatus = String(
                    format: "%d download(s) incompleto(s) antigo(s) • %.1f MB " +
                        "• %d IPA(s) antiga(s) • %d preservado(s). " +
                        "Sem retomada de arquivos parciais; limpeza só com confirmação.",
                    summary.interruptedFiles,
                    Double(summary.interruptedBytes) / 1_048_576,
                    summary.completedFiles,
                    summary.ignoredEntries
                )
                self.tableView.reloadData()
                if cleanup { self.confirmReleaseCacheCleanup(scan) }
            }
        }
    }

    private func confirmReleaseCacheCleanup(
        _ scan: WebReaderLocalQAStorageInventory
    ) {
        guard !isIPCDiagnostic, !releaseCacheBusy, !localQASpaceBusy,
              !stagingIPA, !verifyingExport, !scan.eligible.isEmpty else { return }
        let message = String(
            format: "%d arquivo(s) • %.1f MB. Apenas cópias baixadas ou " +
                "downloads parciais abandonados há mais de 24 h em " +
                "WebReaderUpdates. A IPA selecionada, capítulos, biblioteca, " +
                "backups e arquivos do Filza permanecem intactos. Excluir?",
            scan.eligible.count, Double(scan.eligibleBytes) / 1_048_576
        )
        let alert = UIAlertController(
            title: "Limpar downloads antigos?", message: message,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(
            title: "Excluir cache antigo", style: .destructive
        ) { [weak self] _ in
            self?.discardReleaseCacheAfterConfirmation(scan)
        })
        present(alert, animated: true)
    }

    private func discardReleaseCacheAfterConfirmation(
        _ scan: WebReaderLocalQAStorageInventory
    ) {
        guard !isIPCDiagnostic, !releaseCacheBusy, !localQASpaceBusy,
              !stagingIPA, !verifyingExport else { return }
        releaseCacheBusy = true
        releaseCacheStatus = "Removendo somente cópias antigas confirmadas…"
        tableView.reloadData()
        // Never remove the IPA currently selected for manual export.
        let protectedName = activeReleaseCacheName()
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            var removed = 0
            var released: Int64 = 0
            for candidate in scan.eligible {
                if WebReaderReleaseCacheStorage.discardConfirmed(
                    candidate, protectedName: protectedName
                ) {
                    removed += 1
                    released += candidate.byteCount
                }
            }
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { return }
                self.releaseCacheBusy = false
                self.releaseCacheStatus = String(
                    format: "%d removido(s) • %.1f MB liberados • demais preservados",
                    removed, Double(released) / 1_048_576
                )
                self.tableView.reloadData()
            }
        }
    }

    private func confirmIPADownload() {
        guard !isIPCDiagnostic, !stagingIPA, !verifyingExport,
              let update = availableUpdate,
              update.provenance == .publicGitHubRelease ||
                WebReaderUpdateChannel.isConfigured else { return }
        let mb = Double(update.ipaSize) / (1024 * 1024)
        let channelNotice = update.provenance == .publicGitHubRelease ?
            "Metadados do GitHub não têm assinatura editorial independente. " : ""
        let message = String(format:
            "Build %d • %.1f MB. Baixar e validar agora? " +
            channelNotice +
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
        guard !isIPCDiagnostic, !stagingIPA, !verifyingExport,
              update.provenance == .publicGitHubRelease ||
                WebReaderUpdateChannel.isConfigured,
              let current = availableUpdate,
              current.build == update.build, current.sha256 == update.sha256
        else { return }
        stagingIPA = true
        ipaStatus = "Baixando e verificando hash, versão e conteúdo da IPA"
        tableView.reloadData()
        let id = UUID()
        downloadSessionID = id
        let downloader = WebReaderIPAStager(
            verifiedUpdate: update,
            onProgress: { [weak self] percent in
                DispatchQueue.main.async { [weak self] in
                    guard let self = self, self.downloadSessionID == id,
                          self.stagingIPA else { return }
                    self.ipaStatus = "Recebidos " + String(percent) +
                        "% • hash e ZIP são conferidos ao concluir"
                    self.tableView.reloadData()
                }
            }
        )
        stager = downloader
        downloader.stage { [weak self, weak downloader] result in
            DispatchQueue.main.async {
                guard let self = self, let downloader = downloader,
                      self.stager === downloader else { return }
                self.stager = nil
                self.stagingIPA = false
                self.downloadSessionID = nil
                switch result {
                case .staged(let url):
                    self.stagedIPAURL = url
                    self.stagedSHA256 = update.sha256
                    self.ipaStatus = "SHA-256 e estrutura IPA conferidos • instalação manual"
                case .failed(let failure):
                    self.stagedIPAURL = nil
                    self.stagedSHA256 = nil
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
        case .notNewerThanInstalled: return "Build anterior ou igual à instalada • download bloqueado"
        case .storage: return "Não foi possível salvar a IPA"
        case .insufficientSpace: return "Espaço livre insuficiente • preserve os capítulos offline"
        case .cancelled: return "Download cancelado • cópia parcial removida"
        case .transport: return "Download HTTPS não concluído"
        case .redirectRejected: return "Redirecionamento de download não permitido"
        case .unexpectedHTTPStatus(let code): return "Resposta HTTP " + String(code)
        case .unexpectedContentType: return "Formato HTTP inesperado"
        case .sizeMismatch: return "Tamanho da IPA não corresponde ao manifesto"
        case .integrityMismatch: return "SHA-256 da IPA incorreto"
        case .invalidIPA: return "Estrutura ou identidade da IPA inválida"
        }
    }

    private func showFilzaInstructions() {
        guard !isIPCDiagnostic else { return }
        let text = "1. Toque em Baixar e conferir IPA.\n" +
            "2. Selecione Compartilhar IPA conferida e escolha Filza " +
            "ou Salvar em Arquivos, se disponível.\n" +
            "3. Abra a IPA no Filza e toque em Install.\n" +
            "Não remova o WebReader instalado: faça backup da biblioteca " +
            "e dos capítulos offline antes de atualizar."
        let alert = UIAlertController(
            title: "Instalação manual no Filza",
            message: text, preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Entendi", style: .default))
        present(alert, animated: true)
    }

    private func shareStagedIPA(_ url: URL) {
        guard !isIPCDiagnostic, !verifyingExport,
              let update = availableUpdate,
              stagedIPAURL == url, stagedSHA256 == update.sha256,
              FileManager.default.fileExists(atPath: url.path) else {
            ipaStatus = "IPA indisponível; baixe novamente"
            stagedIPAURL = nil
            stagedSHA256 = nil
            tableView.reloadData()
            return
        }
        // Files in Application Support can change after initial download.
        // Re-audit the exact IPA just before presenting the iOS share sheet.
        verifyingExport = true
        tableView.reloadData()
        let currentBuild = installedBuild
        let currentIOS = ProcessInfo.processInfo.operatingSystemVersion
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let valid = (try? WebReaderNativeIPAAuditor.inspect(
                ipaURL: url, signedUpdate: update,
                installedBuild: currentBuild, installedIOS: currentIOS
            )) != nil
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { return }
                self.verifyingExport = false
                guard self.stagedIPAURL == url else { return }
                if !valid {
                    self.stagedIPAURL = nil
                    self.stagedSHA256 = nil
                    self.ipaStatus = "IPA alterada ou inválida; baixe novamente"
                    self.tableView.reloadData()
                    return
                }
                self.tableView.reloadData()
                guard self.view.window != nil else { return }
                let activity = UIActivityViewController(activityItems: [url],
                    applicationActivities: nil)
                if let popover = activity.popoverPresentationController {
                    popover.sourceView = self.tableView
                    popover.sourceRect = self.tableView.rectForRow(
                        at: IndexPath(row: 2, section: 2))
                }
                self.present(activity, animated: true)
            }
        }
    }

    /// Owner-requested read-only integrity receipt for the *current* IPA.
    /// GitHub SHA-256 is not an independent publisher signature.
    /// The same-FD ZIP/Info.plist/SHA256 review is repeated before copying.
    private func copyStagedIPAReceipt() {
        guard !isIPCDiagnostic, !stagingIPA, !verifyingExport,
              let update = availableUpdate,
              let url = stagedIPAURL,
              stagedSHA256 == update.sha256 else { return }
        verifyingExport = true
        tableView.reloadData()
        let currentBuild = installedBuild
        let currentIOS = ProcessInfo.processInfo.operatingSystemVersion
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let report = try? WebReaderNativeIPAAuditor.inspect(
                ipaURL: url, signedUpdate: update,
                installedBuild: currentBuild, installedIOS: currentIOS
            )
            DispatchQueue.main.async { [weak self] in
                guard let self = self else { return }
                self.verifyingExport = false
                guard self.stagedIPAURL == url else { return }
                guard let report = report,
                      report.verifiedSHA256 == update.sha256 else {
                    self.stagedIPAURL = nil
                    self.stagedSHA256 = nil
                    self.ipaStatus = "IPA local modificada; baixe novamente"
                    self.tableView.reloadData()
                    return
                }
                self.tableView.reloadData()
                guard self.view.window != nil else { return }
                let provenance = update.provenance == .publicGitHubRelease ?
                    "GitHub Release público; editor NÃO autenticado" :
                    "Manifesto assinado; confiança editorial exige verificação separada"
                let lines = [
                    "WebReader • recibo de integridade, NÃO de instalação",
                    "Build: " + String(report.build),
                    "Bundle: " + report.bundleID,
                    "iOS mínimo: " + report.minimumIOS,
                    "Tamanho: " + String(update.ipaSize) + " bytes",
                    "SHA-256: " + report.verifiedSHA256,
                    "Entradas ZIP: " + String(report.zipEntries),
                    "Origem: " + provenance,
                    "IPA revalidada localmente; arquivo pode mudar após a revisão",
                    "Instalação automática: NÃO autorizada e NÃO realizada"
                ]
                UIPasteboard.general.string = lines.joined(separator: "\n")
                let alert = UIAlertController(
                    title: "Recibo copiado",
                    message: "SHA-256 e identidade local conferidos novamente. " +
                        "Não substitui autenticação editorial, backup ou Filza.",
                    preferredStyle: .alert
                )
                alert.addAction(UIAlertAction(title: "OK", style: .default))
                self.present(alert, animated: true)
            }
        }
    }

    private func runOneAppTest() {
        guard isChimeraOneApp, !runningOneAppTest else { return }
        runningOneAppTest = true
        oneAppReport = "Iniciando helper local • sem instalar aplicativos"
        tableView.reloadData()
        WebReaderChimeraSelfTest.run { [weak self] report in
            guard let self = self else { return }
            self.runningOneAppTest = false
            self.oneAppReport = report.text
            self.tableView.reloadData()
        }
    }

    private func copyOneAppReport() {
        guard isChimeraOneApp else { return }
        UIPasteboard.general.string = oneAppReport
        let alert = UIAlertController(
            title: "Resultado copiado",
            message: "Cole o relatório aqui no chat. Nenhum app foi instalado.",
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

    private func testAppinstBridgeConnection() {
        guard !testingAppinstBridge else { return }
        testingAppinstBridge = true
        appinstBridgeReport = isIPCDiagnostic ?
            "PING por TCP 127.0.0.1:38971 • sem instalar IPAs" :
            "PING em socket wri.sock • sem executar appinst"
        tableView.reloadData()
        let finished: (WebReaderAppinstSocket.Result) -> Void = { [weak self] result in
            guard let self = self else { return }
            self.testingAppinstBridge = false
            self.appinstBridgeReport = result.text
            self.tableView.reloadData()
        }
        // The disposable IPC Test IPA probes the local TCP route only.
        // The production WebReader keeps its original UNIX socket behavior.
        if isIPCDiagnostic {
            WebReaderAppinstSocket.checkLoopbackConnection(completion: finished)
        } else {
            WebReaderAppinstSocket.checkConnection(completion: finished)
        }
    }

    private func promptOneTimePairingCode() {
        guard pairingDiagnosticAvailable && !pairingInProgress else { return }
        let dialog = UIAlertController(
            title: "Código temporário do NewTerm",
            message: "Digite os 16 caracteres exibidos por serve-pair-once. " +
                "Não compartilhe esse código no chat. " +
                "O teste verifica apenas a posse do código e NÃO instala IPAs.",
            preferredStyle: .alert
        )
        dialog.addTextField { field in
            field.placeholder = "16 caracteres (0–9, A–F)"
            field.keyboardType = .asciiCapable
            field.autocorrectionType = .no
            field.autocapitalizationType = .allCharacters
        }
        dialog.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        dialog.addAction(UIAlertAction(
            title: "Validar código", style: .default,
            handler: { [weak self, weak dialog] _ in
                guard let self = self, self.pairingDiagnosticAvailable else { return }
                let code = dialog?.textFields?.first?.text ?? ""
                self.pairingInProgress = true
                self.pairingReport = "Validando posse do código por TCP 127.0.0.1:38972"
                self.tableView.reloadData()
                WebReaderAppinstSocket.checkPairedLoopback(code: code) {
                    [weak self] result in
                    guard let self = self else { return }
                    self.pairingInProgress = false
                    self.pairingReport = result.text
                    self.tableView.reloadData()
                }
            }
        ))
        present(dialog, animated: true)
    }

    /// A single consolidated manual field session, using only hard-pinned
    /// throwaway app IPAs. No installation is performed from this UI.
    private func copyBuild60DisposableProcedure() {
        guard build60DisposableAvailable else { return }
        let executable =
            "/var/mobile/Documents/WebReader-Chimera-Disposable-Gate-iOS12"
        let instructions = [
            "Build60 • atualização APENAS do app descartável",
            "Transferir do ZIP Build60 para /var/mobile/Documents:",
            "WebReader-Chimera-Disposable-Gate-iOS12",
            "WebReader-Appinst-Disposable-v1-iOS12-adhoc.ipa",
            "WebReader-Appinst-Disposable-v2-iOS12-adhoc.ipa",
            "No NewTerm 2 como mobile (id -u = 501), um comando:",
            executable + " run-disposable-qa I-CONFIRM-DISPOSABLE-ONLY",
            "Após v1 instalada, abrir WR Appinst Test v1 para criar dados.",
            "Retornar ao NewTerm: digitar NEXT e Enter.",
            "Aguardar v2 e abrir WR Appinst Test v2: persistência SIM.",
            "NÃO usar essa ferramenta com IPA WebReader.",
            "O helper aceita apenas os dois hashes fixos; não abre TCP.",
            "main e WebReader Build56 permanecem preservados."
        ].joined(separator: "\n")
        UIPasteboard.general.string = instructions
        let alert = UIAlertController(
            title: "Roteiro Build 60 copiado",
            message: "O roteiro completo foi copiado. O teste instala " +
                "somente o app descartável, mediante comandos explícitos no NewTerm. " +
                "Nenhuma instalação foi iniciada pelo WebReader.",
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
            build60DisposableAvailable ?
                "Transporte PING: TCP 127.0.0.1:38971 • sem instalação" :
                (isIPCDiagnostic ?
                    "Transporte PING: TCP 127.0.0.1:38971 • sem instalação" :
                    "Socket: UNIX local • PING/PONG somente"),
            build60DisposableAvailable ?
                "Pareamento: TCP 127.0.0.1:38972 • somente posse de código" :
                "Pareamento: ver campo de resultado abaixo",
            "Pasta (comprimento UTF-8): " +
                String(WebReaderHelperPingProbe.diagnosticDirectory.path.utf8.count),
            helperReport,
            "Ponte appinst (PING): " + appinstBridgeReport,
            "Pareamento sem instalação: " +
                (pairingDiagnosticAvailable ? pairingReport : "indisponível"),
            "Nenhum comando appinst executado neste diagnóstico",
            build60DisposableAvailable ?
                "Instalação do app descartável: teste SEPARADO no NewTerm" :
                "Instalação do app descartável: indisponível"
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
