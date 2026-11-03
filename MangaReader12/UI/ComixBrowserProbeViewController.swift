import UIKit
import WebKit

// C2 is a user-operated browser compatibility test, NOT a Comix source.
// No JavaScript is injected, no WebView bridge is exposed, and no site content,
// credentials, cookies, headers or signed URLs are read into app storage.
final class ComixBrowserProbeViewController: UIViewController, WKNavigationDelegate {
    private static let startURL = URL(string: "https://comix.to/")!

    private let introduction = UILabel()
    private let statusLabel = UILabel()
    private let openButton = UIButton(type: .system)
    private let browserContainer = UIView()
    private let placeholder = UILabel()

    private var browser: WKWebView?
    private var hasOpened = false
    private var observedHTTPStatus: Int?
    private var outcome = "Aguardando a abertura manual da página."

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Comix • navegador"
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            title: "Copiar resultado", style: .plain,
            target: self, action: #selector(copyResultTapped)
        )

        let colors = ThemeManager.shared.palette
        view.backgroundColor = colors.background

        introduction.translatesAutoresizingMaskIntoConstraints = false
        introduction.numberOfLines = 0
        introduction.font = UIFont.systemFont(ofSize: 13)
        introduction.textColor = colors.secondaryText
        introduction.text =
            "Teste manual de compatibilidade com iOS 12.5.8. " +
            "A página só será aberta ao tocar no botão. " +
            "Não instala a fonte Comix, não extrai capítulos, " +
            "não altera certificados e não tenta contornar bloqueios."

        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        statusLabel.numberOfLines = 0
        statusLabel.font = UIFont.systemFont(ofSize: 13, weight: .medium)
        statusLabel.textColor = colors.primaryText
        statusLabel.text = outcome
        statusLabel.accessibilityIdentifier = "comixProbeStatus"

        openButton.translatesAutoresizingMaskIntoConstraints = false
        openButton.setTitle("Abrir comix.to no WKWebView", for: .normal)
        openButton.setTitleColor(.white, for: .normal)
        openButton.backgroundColor = colors.accent
        openButton.layer.cornerRadius = 9
        openButton.titleLabel?.font = UIFont.systemFont(ofSize: 15, weight: .semibold)
        openButton.addTarget(self, action: #selector(openTapped), for: .touchUpInside)
        openButton.accessibilityIdentifier = "comixProbeOpen"

        let header = UIStackView(arrangedSubviews: [
            introduction, statusLabel, openButton
        ])
        header.axis = .vertical
        header.spacing = 12
        header.translatesAutoresizingMaskIntoConstraints = false
        view.addSubview(header)

        browserContainer.translatesAutoresizingMaskIntoConstraints = false
        browserContainer.backgroundColor = colors.secondaryBackground
        browserContainer.layer.cornerRadius = 9
        browserContainer.clipsToBounds = true
        view.addSubview(browserContainer)

        placeholder.translatesAutoresizingMaskIntoConstraints = false
        placeholder.numberOfLines = 0
        placeholder.textAlignment = .center
        placeholder.textColor = colors.secondaryText
        placeholder.font = UIFont.systemFont(ofSize: 14)
        placeholder.text =
            "Nenhuma conexão foi iniciada.\n" +
            "Este painel exibirá o site após sua ação."
        browserContainer.addSubview(placeholder)

        NSLayoutConstraint.activate([
            header.topAnchor.constraint(
                equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 16
            ),
            header.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 16),
            header.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -16),
            openButton.heightAnchor.constraint(equalToConstant: 44),
            browserContainer.topAnchor.constraint(equalTo: header.bottomAnchor, constant: 14),
            browserContainer.leadingAnchor.constraint(equalTo: view.leadingAnchor, constant: 8),
            browserContainer.trailingAnchor.constraint(equalTo: view.trailingAnchor, constant: -8),
            browserContainer.bottomAnchor.constraint(
                equalTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -8
            ),
            placeholder.centerXAnchor.constraint(equalTo: browserContainer.centerXAnchor),
            placeholder.centerYAnchor.constraint(equalTo: browserContainer.centerYAnchor),
            placeholder.leadingAnchor.constraint(
                greaterThanOrEqualTo: browserContainer.leadingAnchor, constant: 20
            ),
            placeholder.trailingAnchor.constraint(
                lessThanOrEqualTo: browserContainer.trailingAnchor, constant: -20
            )
        ])
    }

    @objc private func openTapped() {
        guard !hasOpened else { return }
        hasOpened = true
        openButton.isEnabled = false
        openButton.alpha = 0.6
        updateOutcome("Solicitação iniciada por você. Aguardando a navegação principal…")

        // Create the browser only after an explicit tap. Default WebKit JS and
        // system TLS/ATS policies are left intact. The cookie store is ephemeral.
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.navigationDelegate = self
        webView.translatesAutoresizingMaskIntoConstraints = false
        browserContainer.addSubview(webView)
        NSLayoutConstraint.activate([
            webView.topAnchor.constraint(equalTo: browserContainer.topAnchor),
            webView.leadingAnchor.constraint(equalTo: browserContainer.leadingAnchor),
            webView.trailingAnchor.constraint(equalTo: browserContainer.trailingAnchor),
            webView.bottomAnchor.constraint(equalTo: browserContainer.bottomAnchor)
        ])
        placeholder.isHidden = true
        browser = webView
        webView.load(URLRequest(url: Self.startURL))
    }

    @objc private func copyResultTapped() {
        let status = observedHTTPStatus.map(String.init) ?? "não observado"
        UIPasteboard.general.string = [
            "MangaReader12 / Comix C2 / WKWebView",
            "Alvo inicial: https://comix.to/",
            "HTTP principal: " + status,
            "Resultado: " + outcome,
            "Inspeção visual do conteúdo: a confirmar pelo usuário",
            "Sem automação, extração de conteúdo ou armazenamento de sessão."
        ].joined(separator: "\n")
    }

    private func updateOutcome(_ value: String) {
        outcome = value
        statusLabel.text = value
    }

    private static func isAllowedMainFrameHost(_ host: String) -> Bool {
        let normalized = host.lowercased()
        return normalized == "comix.to" || normalized.hasSuffix(".comix.to") ||
            normalized == "comix.ws" || normalized.hasSuffix(".comix.ws")
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        // Do not inspect or rewrite subresource requests. Limit only top-frame
        // browsing to the official hosts listed in Keiyoushi's source metadata.
        if let frame = navigationAction.targetFrame, !frame.isMainFrame {
            decisionHandler(.allow)
            return
        }
        guard let url = navigationAction.request.url,
              url.scheme?.lowercased() == "https",
              let host = url.host,
              Self.isAllowedMainFrameHost(host) else {
            updateOutcome("Navegação principal externa ou não HTTPS bloqueada. Sem redirecionamento automático.")
            decisionHandler(.cancel)
            return
        }
        decisionHandler(.allow)
    }

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationResponse: WKNavigationResponse,
        decisionHandler: @escaping (WKNavigationResponsePolicy) -> Void
    ) {
        if navigationResponse.isForMainFrame,
           let response = navigationResponse.response as? HTTPURLResponse {
            observedHTTPStatus = response.statusCode
            switch response.statusCode {
            case 403, 429, 500, 503:
                updateOutcome(
                    "Servidor respondeu HTTP \(response.statusCode). " +
                    "Não haverá nova tentativa ou tratamento automático de bloqueio."
                )
            default:
                updateOutcome(
                    "Resposta principal HTTP \(response.statusCode). " +
                    "Aguardando renderização pelo WebKit."
                )
            }
        }
        decisionHandler(.allow)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        if let status = observedHTTPStatus, [403, 429, 500, 503].contains(status) {
            return // Preserve the stop indication; no retry or background request.
        }
        updateOutcome(
            "A navegação WebKit terminou. Verifique visualmente se o site " +
            "renderiza e se permite o acesso. Isso não comprova suporte à fonte."
        )
    }

    func webView(
        _ webView: WKWebView,
        didFailProvisionalNavigation navigation: WKNavigation!,
        withError error: Error
    ) {
        showWebKitError(error)
    }

    func webView(
        _ webView: WKWebView,
        didFail navigation: WKNavigation!,
        withError error: Error
    ) {
        showWebKitError(error)
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        updateOutcome("Processo WebContent encerrado pelo sistema. Não será reiniciado automaticamente.")
    }

    private func showWebKitError(_ error: Error) {
        let nsError = error as NSError
        // Error domain/code only: do not copy URL, headers or userInfo.
        updateOutcome("Falha WebKit: \(nsError.domain) / \(nsError.code).")
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        if isMovingFromParent {
            browser?.stopLoading()
            browser?.navigationDelegate = nil
        }
    }
}
