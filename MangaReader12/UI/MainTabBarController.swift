import UIKit

final class MainTabBarController: UITabBarController {
    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .white

        viewControllers = [
            makeNavigation(
                title: "Biblioteca",
                root: PlaceholderViewController(
                    titleText: "Biblioteca",
                    message: "Seus mangás adicionados à biblioteca aparecerão aqui."
                )
            ),
            makeNavigation(
                title: "Atualizações",
                root: PlaceholderViewController(
                    titleText: "Atualizações",
                    message: "Novos capítulos e atualizações da biblioteca aparecerão aqui."
                )
            ),
            makeNavigation(
                title: "Histórico",
                root: PlaceholderViewController(
                    titleText: "Histórico",
                    message: "Seu histórico de leitura aparecerá aqui."
                )
            ),
            makeNavigation(
                title: "Explorar",
                root: ExploreViewController()
            ),
            makeNavigation(
                title: "Ajustes",
                root: SettingsViewController()
            )
        ]
    }

    private func makeNavigation(
        title: String,
        root: UIViewController
    ) -> UINavigationController {
        let navigation = UINavigationController(rootViewController: root)
        navigation.tabBarItem = UITabBarItem(
            title: title,
            image: nil,
            selectedImage: nil
        )
        return navigation
    }
}

final class PlaceholderViewController: UIViewController {
    private let titleText: String
    private let message: String

    init(titleText: String, message: String) {
        self.titleText = titleText
        self.message = message
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = titleText
        view.backgroundColor = .white

        let label = UILabel()
        label.translatesAutoresizingMaskIntoConstraints = false
        label.text = message
        label.textColor = .darkGray
        label.textAlignment = .center
        label.numberOfLines = 0
        label.font = UIFont.systemFont(ofSize: 16)
        view.addSubview(label)

        NSLayoutConstraint.activate([
            label.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            label.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 28),
            label.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -28)
        ])
    }
}

final class ExploreViewController: UITableViewController {
    private var manager: SourceLifecycleManager?
    private var repositories: [RepositoryRecord] = []
    private var sources: [InstalledSourceRecord] = []
    private var startupError: Error?

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Explorar"
        tableView.tableFooterView = UIView()
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            barButtonSystemItem: .add,
            target: self,
            action: #selector(addRepositoryTapped)
        )

        do {
            manager = try SourceLifecycleManager.defaultManager()
        } catch {
            startupError = error
        }

        reloadStoredState()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadStoredState()
    }

    private func reloadStoredState() {
        guard let manager = manager else {
            tableView.reloadData()
            return
        }

        do {
            repositories = try manager.repositories()
            sources = try manager.installedSources()
            startupError = nil
        } catch {
            startupError = error
        }

        tableView.reloadData()
    }

    @objc private func addRepositoryTapped() {
        guard manager != nil else {
            if let error = startupError {
                showError(error)
            }
            return
        }

        let sheet = UIAlertController(
            title: "Adicionar repositório",
            message: nil,
            preferredStyle: .actionSheet
        )

        sheet.addAction(UIAlertAction(
            title: "Repositório demo do MangaReader12",
            style: .default
        ) { [weak self] _ in
            self?.addRepository(url: SourceLifecycleManager.demoRepositoryURL)
        })

        sheet.addAction(UIAlertAction(
            title: "Inserir URL HTTPS",
            style: .default
        ) { [weak self] _ in
            self?.showRepositoryURLPrompt()
        })

        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))

        if let popover = sheet.popoverPresentationController {
            popover.barButtonItem = navigationItem.rightBarButtonItem
        }

        present(sheet, animated: true)
    }

    private func showRepositoryURLPrompt() {
        let alert = UIAlertController(
            title: "URL do repositório",
            message: "Informe a URL HTTPS do catálogo JSON.",
            preferredStyle: .alert
        )

        alert.addTextField { textField in
            textField.placeholder = "https://example.com/repository.json"
            textField.keyboardType = .URL
            textField.autocapitalizationType = .none
            textField.autocorrectionType = .no
        }

        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Adicionar", style: .default) { [weak self, weak alert] _ in
            guard let url = alert?.textFields?.first?.text,
                  !url.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
                return
            }
            self?.addRepository(url: url)
        })

        present(alert, animated: true)
    }

    private func addRepository(url: String) {
        guard let manager = manager else { return }

        navigationItem.rightBarButtonItem?.isEnabled = false
        navigationItem.prompt = "Atualizando repositório…"

        manager.refreshRepository(url: url) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.navigationItem.rightBarButtonItem?.isEnabled = true
                self.navigationItem.prompt = nil

                switch result {
                case .success:
                    self.reloadStoredState()
                    self.navigationController?.pushViewController(
                        RepositoryCatalogViewController(
                            manager: manager,
                            repositoryURL: url
                        ),
                        animated: true
                    )

                case .failure(let error):
                    self.showError(error)
                }
            }
        }
    }

    override func numberOfSections(in tableView: UITableView) -> Int {
        return startupError == nil ? 2 : 1
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        if startupError != nil {
            return 1
        }

        return section == 0 ? repositories.count : sources.count
    }

    override func tableView(
        _ tableView: UITableView,
        titleForHeaderInSection section: Int
    ) -> String? {
        if startupError != nil {
            return "Erro"
        }
        return section == 0 ? "Repositórios" : "Sources instaladas"
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "ExploreCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)

        if let error = startupError {
            cell.textLabel?.text = "Não foi possível abrir o gerenciador"
            cell.detailTextLabel?.text = error.localizedDescription
            cell.detailTextLabel?.numberOfLines = 0
            cell.accessoryType = .none
            return cell
        }

        if indexPath.section == 0 {
            let repository = repositories[indexPath.row]
            cell.textLabel?.text = repository.name
            cell.detailTextLabel?.text = repository.url
            cell.detailTextLabel?.numberOfLines = 2
            cell.accessoryType = .disclosureIndicator
        } else {
            let source = sources[indexPath.row]
            cell.textLabel?.text = source.manifest.name
            cell.detailTextLabel?.text = "v\(source.manifest.version) • \(source.manifest.lang) • \(source.enabled ? "ativada" : "desativada")"
            cell.accessoryType = .none
        }

        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        guard startupError == nil, let manager = manager else { return }

        if indexPath.section == 0 {
            let repository = repositories[indexPath.row]
            navigationController?.pushViewController(
                RepositoryCatalogViewController(
                    manager: manager,
                    repositoryURL: repository.url
                ),
                animated: true
            )
        } else {
            showSourceActions(sources[indexPath.row])
        }
    }

    private func showSourceActions(_ record: InstalledSourceRecord) {
        guard let manager = manager else { return }

        let sheet = UIAlertController(
            title: record.manifest.name,
            message: "Versão \(record.manifest.version)",
            preferredStyle: .actionSheet
        )

        sheet.addAction(UIAlertAction(
            title: record.enabled ? "Desativar" : "Ativar",
            style: .default
        ) { [weak self] _ in
            do {
                try manager.setSourceEnabled(
                    !record.enabled,
                    sourceID: record.manifest.id
                )
                self?.reloadStoredState()
            } catch {
                self?.showError(error)
            }
        })

        sheet.addAction(UIAlertAction(
            title: "Testar runtime instalado",
            style: .default
        ) { [weak self] _ in
            self?.testInstalledRuntime(sourceID: record.manifest.id)
        })

        sheet.addAction(UIAlertAction(
            title: "Rollback para versão anterior",
            style: .default
        ) { [weak self] _ in
            do {
                _ = try manager.rollback(sourceID: record.manifest.id)
                self?.reloadStoredState()
            } catch {
                self?.showError(error)
            }
        })

        sheet.addAction(UIAlertAction(
            title: "Remover source",
            style: .destructive
        ) { [weak self] _ in
            do {
                try manager.removeSource(sourceID: record.manifest.id)
                self?.reloadStoredState()
            } catch {
                self?.showError(error)
            }
        })

        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))

        if let popover = sheet.popoverPresentationController {
            popover.sourceView = view
            popover.sourceRect = CGRect(
                x: view.bounds.midX,
                y: view.bounds.midY,
                width: 1,
                height: 1
            )
        }

        present(sheet, animated: true)
    }

    private func testInstalledRuntime(sourceID: String) {
        do {
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()
            navigationItem.prompt = "Carregando runtime…"

            loader.load(sourceID: sourceID) { [weak self] result in
                switch result {
                case .success(let runtime):
                    runtime.callDecoded(
                        "metadata",
                        as: SourceMetadata.self
                    ) { metadataResult in
                        DispatchQueue.main.async {
                            self?.navigationItem.prompt = nil
                            switch metadataResult {
                            case .success(let metadata):
                                self?.showMessage(
                                    title: "Runtime OK",
                                    message: "\(metadata.name) v\(metadata.version) carregou pelo JavaScriptCore."
                                )
                            case .failure(let error):
                                self?.showError(error)
                            }
                        }
                    }

                case .failure(let error):
                    DispatchQueue.main.async {
                        self?.navigationItem.prompt = nil
                        self?.showError(error)
                    }
                }
            }
        } catch {
            showError(error)
        }
    }

    fileprivate func showError(_ error: Error) {
        showMessage(title: "Erro", message: error.localizedDescription)
    }

    fileprivate func showMessage(title: String, message: String) {
        let alert = UIAlertController(
            title: title,
            message: message,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

final class RepositoryCatalogViewController: UITableViewController {
    private let manager: SourceLifecycleManager
    private let repositoryURL: String
    private var refreshResult: RepositoryRefreshResult?
    private var loading = false

    init(manager: SourceLifecycleManager, repositoryURL: String) {
        self.manager = manager
        self.repositoryURL = repositoryURL
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Sources"
        tableView.tableFooterView = UIView()
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            barButtonSystemItem: .refresh,
            target: self,
            action: #selector(refreshTapped)
        )
        refreshCatalog()
    }

    @objc private func refreshTapped() {
        refreshCatalog()
    }

    private func refreshCatalog() {
        guard !loading else { return }
        loading = true
        navigationItem.prompt = "Atualizando catálogo…"
        navigationItem.rightBarButtonItem?.isEnabled = false

        manager.refreshRepository(url: repositoryURL) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.loading = false
                self.navigationItem.prompt = nil
                self.navigationItem.rightBarButtonItem?.isEnabled = true

                switch result {
                case .success(let value):
                    self.refreshResult = value
                    self.title = value.catalog.name
                    self.tableView.reloadData()

                case .failure(let error):
                    self.showError(error)
                }
            }
        }
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return refreshResult?.catalog.sources.count ?? 0
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "RepositorySourceCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)

        guard let refreshResult = refreshResult else { return cell }
        let manifest = refreshResult.catalog.sources[indexPath.row]
        let plan = refreshResult.plans.first { $0.sourceID == manifest.id }

        cell.textLabel?.text = manifest.name
        cell.detailTextLabel?.text = "v\(manifest.version) • \(manifest.lang) • \(actionText(plan?.action))"

        if let action = plan?.action, action == .install || action == .update {
            cell.accessoryType = .disclosureIndicator
        } else {
            cell.accessoryType = .none
        }

        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        guard let refreshResult = refreshResult else { return }
        let manifest = refreshResult.catalog.sources[indexPath.row]
        guard let action = refreshResult.plans.first(where: {
            $0.sourceID == manifest.id
        })?.action else {
            return
        }

        switch action {
        case .install, .update:
            install(manifest: manifest)
        case .incompatible:
            showMessage(
                title: "Incompatível",
                message: "Essa source exige uma versão mais nova do app."
            )
        case .unchanged:
            showMessage(
                title: "Já instalada",
                message: "A versão \(manifest.version) já está instalada."
            )
        }
    }

    private func install(manifest: SourceManifest) {
        guard !loading else { return }
        loading = true
        navigationItem.prompt = "Instalando \(manifest.name)…"

        manager.installOrUpdate(
            manifest: manifest,
            repositoryURL: repositoryURL
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.loading = false
                self.navigationItem.prompt = nil

                switch result {
                case .success(let record):
                    self.showMessage(
                        title: "Source instalada",
                        message: "\(record.manifest.name) v\(record.manifest.version) está pronta para uso."
                    )
                    self.refreshCatalog()

                case .failure(let error):
                    self.showError(error)
                }
            }
        }
    }

    private func actionText(_ action: RepositorySourceAction?) -> String {
        guard let action = action else { return "desconhecido" }

        switch action {
        case .install: return "instalar"
        case .update: return "atualizar"
        case .unchanged: return "instalada"
        case .incompatible: return "incompatível"
        }
    }

    private func showError(_ error: Error) {
        showMessage(title: "Erro", message: error.localizedDescription)
    }

    private func showMessage(title: String, message: String) {
        let alert = UIAlertController(
            title: title,
            message: message,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

final class SettingsViewController: UITableViewController {
    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Ajustes"
        tableView.tableFooterView = UIView()
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return 2
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "SettingsCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)

        if indexPath.row == 0 {
            cell.textLabel?.text = "Diagnósticos"
            cell.detailTextLabel?.text = "Compatibilidade iOS 12 e subsistemas internos"
            cell.accessoryType = .disclosureIndicator
        } else {
            cell.textLabel?.text = "MangaReader12"
            cell.detailTextLabel?.text = "Batch M2D–M3A • iOS 12.0"
            cell.accessoryType = .none
        }

        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        if indexPath.row == 0 {
            navigationController?.pushViewController(
                RootViewController(),
                animated: true
            )
        }
    }
}
