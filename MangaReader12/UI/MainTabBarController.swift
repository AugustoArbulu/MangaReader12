import UIKit
import WebKit
import Network

final class MainTabBarController: UITabBarController {
    override func viewDidLoad() {
        super.viewDidLoad()

        NotificationCenter.default.addObserver(
            self,
            selector: #selector(themeDidChange),
            name: .appThemeDidChange,
            object: nil
        )

        viewControllers = [
            makeNavigation(
                title: "Biblioteca",
                root: LibraryViewController()
            ),
            makeNavigation(
                title: "Atualizações",
                root: UpdatesViewController()
            ),
            makeNavigation(
                title: "Histórico",
                root: HistoryViewController()
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

        ThemeManager.shared.apply(to: self)
    }

    deinit {
        NotificationCenter.default.removeObserver(self)
    }

    @objc private func themeDidChange() {
        ThemeManager.shared.apply(to: self)
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
    private let messageLabel = UILabel()

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

        messageLabel.translatesAutoresizingMaskIntoConstraints = false
        messageLabel.text = message
        messageLabel.textAlignment = .center
        messageLabel.numberOfLines = 0
        messageLabel.font = UIFont.systemFont(ofSize: 16)
        view.addSubview(messageLabel)

        NSLayoutConstraint.activate([
            messageLabel.centerYAnchor.constraint(equalTo: view.centerYAnchor),
            messageLabel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 28),
            messageLabel.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -28)
        ])

        applyTheme()
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
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 66
        tableView.register(
            SourceIconCell.self,
            forCellReuseIdentifier: SourceIconCell.reuseIdentifier
        )
        let addButton = UIBarButtonItem(
            barButtonSystemItem: .add,
            target: self,
            action: #selector(addRepositoryTapped)
        )
        let globalSearchButton = UIBarButtonItem(
            barButtonSystemItem: .search,
            target: self,
            action: #selector(globalSearchTapped)
        )
        globalSearchButton.accessibilityLabel = "Buscar em todas as fontes"
        navigationItem.rightBarButtonItems = [addButton, globalSearchButton]

        do {
            manager = try SourceLifecycleManager.defaultManager()
        } catch {
            startupError = error
        }

        reloadStoredState()
        applyTheme()
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

    @objc private func globalSearchTapped() {
        navigationController?.pushViewController(
            GlobalSourceSearchViewController(),
            animated: true
        )
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
        if let error = startupError {
            let cell = tableView.dequeueReusableCell(withIdentifier: "ExploreError")
                ?? UITableViewCell(style: .subtitle, reuseIdentifier: "ExploreError")
            ThemeManager.shared.style(cell: cell)
            cell.textLabel?.text = "Não foi possível abrir o gerenciador"
            cell.detailTextLabel?.text = error.localizedDescription
            cell.detailTextLabel?.numberOfLines = 0
            cell.accessoryType = .none
            return cell
        }

        if indexPath.section == 0 {
            let cell = tableView.dequeueReusableCell(withIdentifier: "RepositoryCell")
                ?? UITableViewCell(style: .subtitle, reuseIdentifier: "RepositoryCell")
            ThemeManager.shared.style(cell: cell)

            let repository = repositories[indexPath.row]
            cell.textLabel?.text = repository.name
            cell.detailTextLabel?.text = repository.url
            cell.detailTextLabel?.numberOfLines = 2
            cell.accessoryType = .disclosureIndicator
            return cell
        }

        guard let cell = tableView.dequeueReusableCell(
            withIdentifier: SourceIconCell.reuseIdentifier,
            for: indexPath
        ) as? SourceIconCell else {
            return UITableViewCell()
        }

        let source = sources[indexPath.row]
        cell.configure(
            title: source.manifest.name,
            subtitle: "v\(source.manifest.version) • \(source.manifest.lang) • \(source.enabled ? "ativada" : "desativada")",
            iconURL: source.manifest.icon
        )
        cell.accessoryType = source.enabled ? .disclosureIndicator : .none
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
            title: "Abrir source",
            style: .default
        ) { [weak self] _ in
            guard record.enabled else {
                self?.showMessage(
                    title: "Source desativada",
                    message: "Ative essa source antes de abri-la."
                )
                return
            }

            self?.navigationController?.pushViewController(
                SourceBrowserViewController(sourceRecord: record),
                animated: true
            )
        })

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
            title: "Informações e dados da fonte",
            style: .default
        ) { [weak self] _ in
            self?.navigationController?.pushViewController(
                SourceInformationViewController(record: record),
                animated: true
            )
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

// Global search uses the installed JavaScriptSourceRuntime contract and
// the same source-domain policy as per-source search. It does not install or
// execute Android APKs, and it intentionally only requests page one.
// A single iOS 12-compatible search surface across enabled JS sources.
// Search batches run sequentially to limit memory and request concurrency.
final class GlobalSourceSearchViewController: UITableViewController, UISearchBarDelegate {
    private struct SearchMatch {
        let source: InstalledSourceRecord
        let manga: SourceMangaSummary
    }

    private struct PageState {
        let nextPage: Int
        let hasMore: Bool
    }

    private let maxPagesPerSource = 5
    private var matches: [SearchMatch] = []
    private var seenIDs = Set<String>()
    private var sourcePages: [String: PageState] = [:]
    private var sourceOptions: [InstalledSourceRecord] = []
    private var selectedSourceIDs: Set<String>? // nil means all enabled sources
    private var searchSources: [InstalledSourceRecord] = []
    private var activeQuery: String?
    private var generation = 0
    private var failedSources = 0
    private var loading = false

    private lazy var globalSearchController: UISearchController = {
        let controller = UISearchController(searchResultsController: nil)
        controller.obscuresBackgroundDuringPresentation = false
        controller.searchBar.placeholder = "Título em todas as fontes"
        controller.searchBar.delegate = self
        return controller
    }()

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Busca global"
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 98
        tableView.register(
            MangaCoverCell.self, forCellReuseIdentifier: MangaCoverCell.reuseIdentifier
        )
        navigationItem.searchController = globalSearchController
        navigationItem.hidesSearchBarWhenScrolling = false
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            title: "Fontes", style: .plain,
            target: self, action: #selector(filterTapped)
        )
        definesPresentationContext = true
        applyTheme()
        showEmptyState("Digite um título e toque em Buscar.")
    }

    private func showEmptyState(_ message: String?) {
        guard let message = message else {
            tableView.backgroundView = nil
            return
        }
        let label = UILabel()
        label.text = message
        label.textAlignment = .center
        label.numberOfLines = 0
        label.textColor = ThemeManager.shared.palette.secondaryText
        tableView.backgroundView = label
    }

    @objc private func filterTapped() {
        do {
            let manager = try SourceLifecycleManager.defaultManager()
            let sources = try manager.installedSources().filter { $0.enabled }
            let picker = GlobalSearchSourcePickerViewController(
                sources: sources,
                selected: selectedSourceIDs ?? Set(sources.map { $0.manifest.id })
            ) { [weak self] newSelection in
                guard let self = self else { return }
                self.selectedSourceIDs = newSelection
                let query = (self.globalSearchController.searchBar.text ?? "")
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                if query.isEmpty {
                    self.resetSearch(message: "Digite um título e toque em Buscar.")
                } else {
                    self.startSearch(query)
                }
            }
            navigationController?.pushViewController(picker, animated: true)
        } catch {
            showMessage(title: "Fontes indisponíveis", message: error.localizedDescription)
        }
    }

    func searchBarSearchButtonClicked(_ searchBar: UISearchBar) {
        let query = (searchBar.text ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        searchBar.resignFirstResponder()
        guard !query.isEmpty else {
            resetSearch(message: "Digite um título para pesquisar.")
            return
        }
        startSearch(query)
    }

    func searchBarCancelButtonClicked(_ searchBar: UISearchBar) {
        resetSearch(message: "Digite um título e toque em Buscar.")
    }

    private func resetSearch(message: String) {
        // Invalidates all late async completions from an older query/batch.
        generation += 1
        loading = false
        activeQuery = nil
        failedSources = 0
        matches = []
        seenIDs = []
        sourcePages = [:]
        searchSources = []
        navigationItem.prompt = nil
        tableView.tableFooterView = UIView(frame: .zero)
        tableView.reloadData()
        showEmptyState(message)
    }

    private func startSearch(_ query: String) {
        resetSearch(message: "Buscando em fontes instaladas…")
        activeQuery = query
        do {
            let lifecycle = try SourceLifecycleManager.defaultManager()
            sourceOptions = try lifecycle.installedSources().filter { $0.enabled }
            searchSources = sourceOptions.filter {
                selectedSourceIDs?.contains($0.manifest.id) ?? true
            }
            guard !searchSources.isEmpty else {
                showEmptyState(
                    sourceOptions.isEmpty
                        ? "Nenhuma fonte ativa. Instale ou ative uma fonte em Explorar."
                        : "Nenhuma fonte selecionada. Toque em Fontes para escolher."
                )
                return
            }
            loadBatch(searchSources)
        } catch {
            activeQuery = nil
            showEmptyState("Erro ao pesquisar: \(error.localizedDescription)")
        }
    }

    private func loadBatch(_ sources: [InstalledSourceRecord]) {
        guard !loading, !sources.isEmpty,
              let query = activeQuery else { return }
        loading = true
        let token = generation
        updateLoadMoreFooter()
        do {
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()
            fetchNext(
                index: 0, sources: sources, loader: loader,
                query: query, token: token
            )
        } catch {
            loading = false
            navigationItem.prompt = nil
            showMessage(title: "Erro da pesquisa", message: error.localizedDescription)
            updateLoadMoreFooter()
        }
    }

    private func fetchNext(
        index: Int,
        sources: [InstalledSourceRecord],
        loader: InstalledSourceRuntimeLoader,
        query: String,
        token: Int
    ) {
        guard token == generation else { return }
        guard index < sources.count else {
            loading = false
            navigationItem.prompt = "\(matches.count) resultados • \(searchSources.count) fontes" +
                (failedSources > 0 ? " • \(failedSources) falhas" : "")
            if matches.isEmpty {
                showEmptyState("Nenhum resultado encontrado.")
            }
            updateLoadMoreFooter()
            return
        }

        let source = sources[index]
        let id = source.manifest.id
        let pageNumber = sourcePages[id]?.nextPage ?? 1
        navigationItem.prompt = "Buscando \(index + 1)/\(sources.count): \(source.manifest.name)…"
        loader.load(sourceID: id) { [weak self] loaded in
            DispatchQueue.main.async {
                guard let self = self, token == self.generation else { return }
                switch loaded {
                case .failure:
                    self.failedSources += 1
                    self.sourcePages[id] = PageState(nextPage: pageNumber, hasMore: false)
                    self.fetchNext(
                        index: index + 1, sources: sources, loader: loader,
                        query: query, token: token
                    )

                case .success(let runtime):
                    runtime.callDecoded(
                        "search",
                        arguments: [query, pageNumber, [] as [Any]],
                        as: SourcePagedMangaResult.self
                    ) { [weak self] response in
                        DispatchQueue.main.async {
                            guard let self = self, token == self.generation else { return }
                            switch response {
                            case .failure:
                                self.failedSources += 1
                                self.sourcePages[id] = PageState(
                                    nextPage: pageNumber, hasMore: false
                                )
                            case .success(let page):
                                for item in page.items.prefix(40) {
                                    let key = id + "\u{1F}" + item.id
                                    if self.seenIDs.insert(key).inserted {
                                        self.matches.append(
                                            SearchMatch(source: source, manga: item)
                                        )
                                    }
                                }
                                self.sourcePages[id] = PageState(
                                    nextPage: pageNumber + 1,
                                    hasMore: page.hasNextPage &&
                                        pageNumber < self.maxPagesPerSource
                                )
                                if !self.matches.isEmpty {
                                    self.showEmptyState(nil)
                                }
                                self.tableView.reloadData()
                            }
                            self.fetchNext(
                                index: index + 1, sources: sources,
                                loader: loader, query: query, token: token
                            )
                        }
                    }
                }
            }
        }
    }

    private func updateLoadMoreFooter() {
        let available = searchSources.contains {
            sourcePages[$0.manifest.id]?.hasMore == true
        }
        guard available else {
            tableView.tableFooterView = UIView(frame: .zero)
            return
        }
        let footer = UIView(frame: CGRect(x: 0, y: 0, width: tableView.bounds.width, height: 58))
        let button = UIButton(type: .system)
        button.setTitle(loading ? "Carregando…" : "Carregar mais resultados", for: .normal)
        button.isEnabled = !loading
        button.addTarget(self, action: #selector(loadMoreTapped), for: .touchUpInside)
        button.frame = footer.bounds
        footer.addSubview(button)
        tableView.tableFooterView = footer
    }

    @objc private func loadMoreTapped() {
        guard !loading else { return }
        let pending = searchSources.filter {
            sourcePages[$0.manifest.id]?.hasMore == true
        }
        loadBatch(pending)
    }

    override func tableView(
        _ tableView: UITableView, numberOfRowsInSection section: Int
    ) -> Int {
        return matches.count
    }

    override func tableView(
        _ tableView: UITableView, cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        guard let cell = tableView.dequeueReusableCell(
            withIdentifier: MangaCoverCell.reuseIdentifier, for: indexPath
        ) as? MangaCoverCell else { return UITableViewCell() }

        let match = matches[indexPath.row]
        cell.configure(
            title: match.manga.title,
            subtitle: "\(match.source.manifest.name) • \(match.source.manifest.lang)",
            coverURL: match.manga.cover,
            allowedDomains: match.source.manifest.domains
        )
        cell.accessoryType = .disclosureIndicator
        return cell
    }

    override func tableView(
        _ tableView: UITableView, didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        let match = matches[indexPath.row]
        navigationItem.prompt = "Abrindo \(match.source.manifest.name)…"
        do {
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()
            loader.load(sourceID: match.source.manifest.id) { [weak self] loaded in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.navigationItem.prompt = nil
                    switch loaded {
                    case .success(let runtime):
                        self.navigationController?.pushViewController(
                            MangaDetailsViewController(
                                sourceRecord: match.source,
                                runtime: runtime, summary: match.manga
                            ),
                            animated: true
                        )
                    case .failure(let error):
                        self.showMessage(
                            title: "Não foi possível abrir",
                            message: error.localizedDescription
                        )
                    }
                }
            }
        } catch {
            navigationItem.prompt = nil
            showMessage(title: "Erro da fonte", message: error.localizedDescription)
        }
    }

    private func showMessage(title: String, message: String) {
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

// Isolated source diagnostics and settings maintenance. This screen never
// exposes persisted values or removes user Library/download data.
final class SourceInformationViewController: UITableViewController {
    private let record: InstalledSourceRecord
    private let storage: SourceStorage
    private var isTesting = false
    private var networkDiagnostics: MangaDexHTTPSDiagnostics?

    init(record: InstalledSourceRecord) {
        self.record = record
        self.storage = SourceStorage(sourceID: record.manifest.id)
        super.init(style: .grouped)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = record.manifest.name
        tableView.tableFooterView = UIView()
        applyTheme()
    }

    override func numberOfSections(in tableView: UITableView) -> Int {
        return 2
    }

    override func tableView(
        _ tableView: UITableView, numberOfRowsInSection section: Int
    ) -> Int {
        return section == 0 ? 5 :
            (record.manifest.id == "org.mangareader12.mangadex" ? 3 : 2)
    }

    override func tableView(
        _ tableView: UITableView, titleForHeaderInSection section: Int
    ) -> String? {
        return section == 0 ? "Informações da fonte" : "Manutenção"
    }

    override func tableView(
        _ tableView: UITableView, cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "SourceInfoCell")
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: "SourceInfoCell")
        ThemeManager.shared.style(cell: cell)
        cell.accessoryType = .none
        cell.selectionStyle = .none
        cell.detailTextLabel?.numberOfLines = 0

        if indexPath.section == 0 {
            switch indexPath.row {
            case 0:
                cell.textLabel?.text = "Identificador"
                cell.detailTextLabel?.text = record.manifest.id
            case 1:
                cell.textLabel?.text = "Versão e idioma"
                cell.detailTextLabel?.text = "v\(record.manifest.version) • \(record.manifest.lang)"
            case 2:
                cell.textLabel?.text = "Estado"
                cell.detailTextLabel?.text = record.enabled ? "Ativada" : "Desativada"
            case 3:
                cell.textLabel?.text = "Domínios permitidos"
                cell.detailTextLabel?.text = record.manifest.domains.joined(separator: ", ")
            default:
                cell.textLabel?.text = "Preferências da fonte"
                cell.detailTextLabel?.text = "\(storage.entryCount()) entradas locais"
            }
        } else {
            cell.selectionStyle = .default
            cell.accessoryType = .disclosureIndicator
            if indexPath.row == 0 {
                cell.textLabel?.text = "Verificar runtime"
                cell.detailTextLabel?.text = "Testa carregamento e metadata da fonte"
            } else if indexPath.row == 1 {
                cell.textLabel?.text = "Limpar preferências desta fonte"
                cell.detailTextLabel?.text =
                    "Remove apenas o armazenamento JS desta fonte; pode exigir reconfiguração"
            } else {
                cell.textLabel?.text = "Diagnosticar HTTPS do MangaDex"
                cell.detailTextLabel?.text =
                    "Compara API, URLSession do iOS e HTTPS de controle; não altera certificados"
            }
        }
        return cell
    }

    override func tableView(
        _ tableView: UITableView, didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        guard indexPath.section == 1 else { return }
        switch indexPath.row {
        case 0: testRuntime()
        case 1: confirmReset()
        default: diagnoseMangaDexHTTPS()
        }
    }

    private func diagnoseMangaDexHTTPS() {
        guard record.manifest.id == "org.mangareader12.mangadex",
              networkDiagnostics == nil else { return }

        navigationItem.prompt = "Testando conexões HTTPS…"
        let diagnostic = MangaDexHTTPSDiagnostics()
        networkDiagnostics = diagnostic
        diagnostic.run { [weak self] report in
            guard let self = self else { return }
            self.networkDiagnostics = nil
            self.navigationItem.prompt = nil

            let alert = UIAlertController(
                title: "Diagnóstico HTTPS",
                message: report,
                preferredStyle: .alert
            )
            alert.addAction(UIAlertAction(
                title: "Copiar relatório", style: .default
            ) { _ in
                UIPasteboard.general.string = report
            })
            alert.addAction(UIAlertAction(title: "Fechar", style: .cancel))
            self.present(alert, animated: true)
        }
    }

    private func testRuntime() {
        guard !isTesting else { return }
        isTesting = true
        navigationItem.prompt = "Verificando runtime…"
        do {
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()
            loader.load(sourceID: record.manifest.id) { [weak self] outcome in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    switch outcome {
                    case .failure(let error):
                        self.finishTest(.failure(error))
                    case .success(let runtime):
                        runtime.callDecoded("metadata", as: SourceMetadata.self) {
                            [weak self] metadata in
                            DispatchQueue.main.async {
                                self?.finishTest(metadata)
                            }
                        }
                    }
                }
            }
        } catch {
            finishTest(.failure(error))
        }
    }

    private func finishTest(_ result: Result<SourceMetadata, Error>) {
        isTesting = false
        navigationItem.prompt = nil
        switch result {
        case .failure(let error):
            showMessage(title: "Falha no runtime", message: error.localizedDescription)
        case .success(let meta):
            showMessage(
                title: "Runtime OK",
                message: "\(meta.name) • versão \(meta.version) • \(meta.lang)"
            )
        }
    }

    private func confirmReset() {
        let count = storage.entryCount()
        let alert = UIAlertController(
            title: "Limpar dados desta fonte?",
            message: "Serão apagadas \(count) entradas do armazenamento JS de \(record.manifest.name). Isso pode redefinir opções e sessões da fonte. Biblioteca, downloads, histórico e preferências do leitor não serão alterados.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(
            title: "Limpar dados", style: .destructive
        ) { [weak self] _ in
            guard let self = self else { return }
            let removed = self.storage.clearAll()
            self.tableView.reloadData()
            self.showMessage(
                title: "Dados da fonte limpos",
                message: "\(removed) entradas locais removidas."
            )
        })
        present(alert, animated: true)
    }

    private func showMessage(title: String, message: String) {
        let alert = UIAlertController(title: title, message: message, preferredStyle: .alert)
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

// Read-only, opt-in diagnostic. No trust-challenge override, TLS downgrade,
// insecure HTTP, global ATS exemption or source-domain policy changes.
private final class MangaDexHTTPSDiagnostics {
    private let sourceClient = HTTPClient(
        policy: HTTPPolicy(
            allowedDomains: ["mangadex.org"],
            timeout: 12,
            maxResponseBytes: 64 * 1024
        )
    )
    private var results: [String] = []
    private weak var presentationView: UIView?
    private var alternateProbe: MangaDexAlternateTLSProbe?

    func run(completion: @escaping (String) -> Void) {
        results = [
            "iOS " + UIDevice.current.systemVersion,
            "Certificados: validação padrão do iOS (sem exceções)",
            "Teste somente leitura; sem dados de conta."
        ]
        presentationView = UIApplication.shared.keyWindow?.rootViewController?.view
        testSourceClient(completion: completion)
    }

    private func testSourceClient(completion: @escaping (String) -> Void) {
        sourceClient.send(
            HTTPRequest(url: "https://api.mangadex.org/ping")
        ) { [self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let response):
                    self.results.append("API via HTTPClient: HTTP \(response.statusCode)")
                case .failure(let error):
                    self.results.append(
                        "API via HTTPClient: " + error.localizedDescription
                    )
                }
                self.testSystemSession(index: 0, completion: completion)
            }
        }
    }

    private func testSystemSession(
        index: Int,
        completion: @escaping (String) -> Void
    ) {
        // The system session differs from our delegate-backed HTTPClient,
        // helping distinguish TLS/device trust from a client implementation bug.
        let destinations: [(String, String)] = [
            ("API via URLSession", "https://api.mangadex.org/ping"),
            ("Site MangaDex", "https://mangadex.org/"),
            ("GitHub de controle", "https://raw.githubusercontent.com/AugustoArbulu/MangaReader12/main/fixtures/repository-mangadex.json"),
            ("HTTPS de controle", "https://example.com/")
        ]
        guard index < destinations.count else {
            let alternate = MangaDexAlternateTLSProbe()
            alternateProbe = alternate
            alternate.run(on: presentationView) { [self] findings in
                self.results.append(contentsOf: findings)
                self.alternateProbe = nil
                completion(self.results.joined(separator: "\n"))
            }
            return
        }
        let entry = destinations[index]
        guard let url = URL(string: entry.1), url.scheme == "https" else {
            results.append(entry.0 + ": URL inválida")
            testSystemSession(index: index + 1, completion: completion)
            return
        }
        var request = URLRequest(url: url)
        request.timeoutInterval = 12
        request.httpMethod = "GET"
        // All probes use system trust and require HTTPS.
        URLSession.shared.dataTask(with: request) { [self] _, response, error in
            DispatchQueue.main.async {
                if let error = error {
                    self.results.append(entry.0 + ": " + self.describe(error))
                } else if let http = response as? HTTPURLResponse {
                    self.results.append(entry.0 + ": HTTP \(http.statusCode)")
                } else {
                    self.results.append(entry.0 + ": resposta inválida")
                }
                self.testSystemSession(index: index + 1, completion: completion)
            }
        }.resume()
    }

    private func describe(_ error: Error) -> String {
        let ns = error as NSError
        var detail = "\(ns.domain) \(ns.code)"
        if let underlying = ns.userInfo[NSUnderlyingErrorKey] as? NSError {
            detail += " (suberro \(underlying.domain):\(underlying.code))"
            if let ssl = underlying.userInfo["_kCFStreamErrorCodeKey"] {
                detail += " [TLS \(ssl)]"
            }
        } else if let ssl = ns.userInfo["_kCFStreamErrorCodeKey"] {
            detail += " [TLS \(ssl)]"
        }
        return detail
    }
}

// Alternate TLS stacks tested only after normal URLSession fails. WebKit
// uses an ephemeral WKWebView and iOS' default certificate verification.
// Network.framework uses NWParameters(tls:) with system trust and no custom
// verify block. Neither approach overrides ATS or bypasses server checks.
private final class MangaDexAlternateTLSProbe: NSObject, WKNavigationDelegate {
    private var results: [String] = []
    private var webView: WKWebView?
    private var networkConnection: NWConnection?
    private var callback: (([String]) -> Void)?
    private var webFinished = false
    private var networkFinished = false

    func run(on hostView: UIView?, completion: @escaping ([String]) -> Void) {
        callback = completion
        guard let hostView = hostView else {
            results.append("WebKit: sem tela disponível")
            startNetwork()
            return
        }
        let config = WKWebViewConfiguration()
        config.websiteDataStore = .nonPersistent()
        let browser = WKWebView(
            frame: CGRect(x: 0, y: 0, width: 1, height: 1),
            configuration: config
        )
        // Keep the ephemeral WebView attached to a real view to ensure that
        // the iOS 12 WebContent process can start loading.
        browser.alpha = 0.01
        browser.isUserInteractionEnabled = false
        browser.navigationDelegate = self
        hostView.addSubview(browser)
        webView = browser
        if let url = URL(string: "https://api.mangadex.org/ping") {
            var request = URLRequest(url: url)
            request.timeoutInterval = 12
            browser.load(request)
        } else {
            finishWebKit("URL inválida")
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 14) { [weak self] in
            self?.finishWebKit("tempo esgotado")
        }
    }

    func webView(
        _ webView: WKWebView,
        didFinish navigation: WKNavigation!
    ) {
        webView.evaluateJavaScript("document.body ? document.body.innerText : ''") {
            [weak self] content, error in
            if let error = error {
                self?.finishWebKit("HTTPS OK, leitura do corpo falhou: \((error as NSError).code)")
            } else {
                let value = (content as? String ?? "")
                    .trimmingCharacters(in: .whitespacesAndNewlines)
                self?.finishWebKit(
                    "HTTPS OK" + (value.isEmpty ? "" : " • " + String(value.prefix(50)))
                )
            }
        }
    }

    func webView(
        _ webView: WKWebView,
        didFailProvisionalNavigation navigation: WKNavigation!,
        withError error: Error
    ) {
        finishWebKit("falhou " + describe(error))
    }

    func webView(
        _ webView: WKWebView,
        didFail navigation: WKNavigation!,
        withError error: Error
    ) {
        finishWebKit("falhou " + describe(error))
    }

    private func finishWebKit(_ result: String) {
        guard !webFinished else { return }
        webFinished = true
        results.append("API via WKWebView: " + result)
        webView?.navigationDelegate = nil
        webView?.stopLoading()
        webView?.removeFromSuperview()
        webView = nil
        startNetwork()
    }

    private func startNetwork() {
        let options = NWProtocolTLS.Options()
        // No verify override: Network.framework performs standard
        // hostname + certificate trust validation for this TLS hostname.
        let parameters = NWParameters(
            tls: options,
            tcp: NWProtocolTCP.Options()
        )
        let endpoint = NWEndpoint.Port(rawValue: 443)!
        let connection = NWConnection(
            host: NWEndpoint.Host("api.mangadex.org"),
            port: endpoint,
            using: parameters
        )
        networkConnection = connection
        let queue = DispatchQueue(label: "mangareader12.mangadex.tls-probe")
        connection.stateUpdateHandler = { [weak self] state in
            DispatchQueue.main.async {
                guard let self = self else { return }
                switch state {
                case .ready:
                    self.finishNetwork("TLS conectado, confiança padrão OK")
                case .failed(let error):
                    self.finishNetwork("falhou: " + String(describing: error))
                default:
                    break
                }
            }
        }
        connection.start(queue: queue)
        DispatchQueue.main.asyncAfter(deadline: .now() + 14) { [weak self] in
            self?.finishNetwork("tempo esgotado")
        }
    }

    private func finishNetwork(_ result: String) {
        guard !networkFinished else { return }
        networkFinished = true
        results.append("API via Network.framework: " + result)
        networkConnection?.stateUpdateHandler = nil
        networkConnection?.cancel()
        networkConnection = nil
        let onComplete = callback
        callback = nil
        onComplete?(results)
    }

    private func describe(_ error: Error) -> String {
        let ns = error as NSError
        let underlying = ns.userInfo[NSUnderlyingErrorKey] as? NSError
        let code = underlying?.userInfo["_kCFStreamErrorCodeKey"]
            ?? ns.userInfo["_kCFStreamErrorCodeKey"]
        return "\(ns.domain) \(ns.code)" +
            (code.map { " [TLS \($0)]" } ?? "")
    }
}

extension SourceInformationViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}

final class GlobalSearchSourcePickerViewController: UITableViewController {
    private let sources: [InstalledSourceRecord]
    private var selectedIDs: Set<String>
    private let onApply: (Set<String>) -> Void

    init(
        sources: [InstalledSourceRecord],
        selected: Set<String>,
        onApply: @escaping (Set<String>) -> Void
    ) {
        self.sources = sources
        self.selectedIDs = selected
        self.onApply = onApply
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Filtrar fontes"
        tableView.tableFooterView = UIView()
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            title: "Aplicar", style: .done,
            target: self, action: #selector(applyTapped)
        )
        navigationItem.leftBarButtonItem = UIBarButtonItem(
            title: "Todas", style: .plain,
            target: self, action: #selector(selectAllTapped)
        )
        applyTheme()
    }

    @objc private func selectAllTapped() {
        selectedIDs = Set(sources.map { $0.manifest.id })
        tableView.reloadData()
    }

    @objc private func applyTapped() {
        onApply(selectedIDs)
        navigationController?.popViewController(animated: true)
    }

    override func tableView(
        _ tableView: UITableView, numberOfRowsInSection section: Int
    ) -> Int {
        return sources.count
    }

    override func tableView(
        _ tableView: UITableView, cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "GlobalSourceFilter")
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: "GlobalSourceFilter")
        ThemeManager.shared.style(cell: cell)
        let source = sources[indexPath.row]
        cell.textLabel?.text = source.manifest.name
        cell.detailTextLabel?.text = "\(source.manifest.lang) • v\(source.manifest.version)"
        cell.accessoryType = selectedIDs.contains(source.manifest.id) ? .checkmark : .none
        return cell
    }

    override func tableView(
        _ tableView: UITableView, didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        let id = sources[indexPath.row].manifest.id
        if selectedIDs.contains(id) {
            selectedIDs.remove(id)
        } else {
            selectedIDs.insert(id)
        }
        tableView.reloadRows(at: [indexPath], with: .none)
    }
}

extension GlobalSearchSourcePickerViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}

extension GlobalSourceSearchViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        if matches.isEmpty && !loading {
            showEmptyState("Digite um título e toque em Buscar.")
        }
        tableView.reloadData()
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
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 66
        tableView.register(
            SourceIconCell.self,
            forCellReuseIdentifier: SourceIconCell.reuseIdentifier
        )
        applyTheme()
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
        guard let cell = tableView.dequeueReusableCell(
            withIdentifier: SourceIconCell.reuseIdentifier,
            for: indexPath
        ) as? SourceIconCell else {
            return UITableViewCell()
        }

        guard let refreshResult = refreshResult else { return cell }
        let manifest = refreshResult.catalog.sources[indexPath.row]
        let plan = refreshResult.plans.first { $0.sourceID == manifest.id }

        cell.configure(
            title: manifest.name,
            subtitle: "v\(manifest.version) • \(manifest.lang) • \(actionText(plan?.action))",
            iconURL: manifest.icon
        )

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
        applyTheme()
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return 6
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "SettingsCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)

        switch indexPath.row {
        case 0:
            cell.textLabel?.text = "Modo escuro"
            cell.detailTextLabel?.text = "Tema manual compatível com iOS 12"
            cell.accessoryType = .none

            let toggle = UISwitch()
            toggle.isOn = ThemeManager.shared.isDark
            toggle.addTarget(
                self,
                action: #selector(darkModeChanged(_:)),
                for: .valueChanged
            )
            cell.accessoryView = toggle
            cell.selectionStyle = .none

        case 1:
            cell.textLabel?.text = "Leitor"
            cell.detailTextLabel?.text = "Modo, direção, fundo, tap zones e outros controles"
            cell.accessoryType = .disclosureIndicator
            cell.accessoryView = nil
            cell.selectionStyle = .default

        case 2:
            cell.textLabel?.text = "Dados e armazenamento"
            cell.detailTextLabel?.text = "Backup, Downloads, caches e uso de espaço"
            cell.accessoryType = .disclosureIndicator
            cell.accessoryView = nil
            cell.selectionStyle = .default

        case 3:
            cell.textLabel?.text = "Atualização automática"
            cell.detailTextLabel?.text = "Oportunista: o iOS 12 decide quando executar em segundo plano"
            cell.accessoryType = .none

            let toggle = UISwitch()
            toggle.isOn = BackgroundLibraryUpdateManager.shared.isEnabled
            toggle.addTarget(
                self,
                action: #selector(backgroundUpdatesChanged(_:)),
                for: .valueChanged
            )
            cell.accessoryView = toggle
            cell.selectionStyle = .none

        case 4:
            cell.textLabel?.text = "Diagnósticos"
            cell.detailTextLabel?.text = "Compatibilidade iOS 12 e subsistemas internos"
            cell.accessoryType = .disclosureIndicator
            cell.accessoryView = nil
            cell.selectionStyle = .default

        default:
            cell.textLabel?.text = "MangaReader12"
            cell.detailTextLabel?.text = "Batch M7C–M9A hardening • iOS 12.0"
            cell.accessoryType = .none
            cell.accessoryView = nil
            cell.selectionStyle = .none
        }
        return cell
    }

    @objc private func darkModeChanged(_ sender: UISwitch) {
        ThemeManager.shared.setTheme(sender.isOn ? .dark : .light)
    }

    @objc private func backgroundUpdatesChanged(_ sender: UISwitch) {
        BackgroundLibraryUpdateManager.shared.isEnabled = sender.isOn
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        switch indexPath.row {
        case 1:
            navigationController?.pushViewController(
                ReaderSettingsViewController(),
                animated: true
            )

        case 2:
            navigationController?.pushViewController(
                DataStorageViewController(),
                animated: true
            )

        case 4:
            navigationController?.pushViewController(
                RootViewController(),
                animated: true
            )

        default:
            break
        }
    }
}

extension MainTabBarController: ThemeApplicable {
    func applyTheme() {
        let colors = ThemeManager.shared.palette
        view.backgroundColor = colors.background
        tabBar.barTintColor = colors.barBackground
        tabBar.tintColor = colors.accent
    }
}

extension PlaceholderViewController: ThemeApplicable {
    func applyTheme() {
        let colors = ThemeManager.shared.palette
        view.backgroundColor = colors.background
        messageLabel.textColor = colors.secondaryText
    }
}

extension ExploreViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}

extension RepositoryCatalogViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}

extension SettingsViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
