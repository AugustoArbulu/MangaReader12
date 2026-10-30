import UIKit

final class SourceBrowserViewController: UITableViewController, UISearchBarDelegate {
    private let sourceRecord: InstalledSourceRecord
    private var runtime: JavaScriptSourceRuntime?
    private var items: [SourceMangaSummary] = []
    private var currentPage = 1
    private var hasNextPage = false
    private var loading = false
    private var currentQuery: String?
    private var coverDiagnostic: WebtoonsCoverDiagnostic?

    private lazy var sourceSearchController: UISearchController = {
        let controller = UISearchController(searchResultsController: nil)
        controller.obscuresBackgroundDuringPresentation = false
        controller.searchBar.placeholder = "Buscar nesta source"
        controller.searchBar.delegate = self
        return controller
    }()

    init(sourceRecord: InstalledSourceRecord) {
        self.sourceRecord = sourceRecord
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = sourceRecord.manifest.name
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 100
        tableView.register(
            MangaCoverCell.self,
            forCellReuseIdentifier: MangaCoverCell.reuseIdentifier
        )
        navigationItem.searchController = sourceSearchController
        navigationItem.hidesSearchBarWhenScrolling = false
        definesPresentationContext = true
        applyTheme()

        if sourceRecord.manifest.id == "kei.webtoons.en" {
            navigationItem.rightBarButtonItem = UIBarButtonItem(
                title: "Testar capas",
                style: .plain,
                target: self,
                action: #selector(diagnoseCoverTapped)
            )
        }

        refreshControl = UIRefreshControl()
        refreshControl?.addTarget(
            self,
            action: #selector(refreshPulled),
            for: .valueChanged
        )

        loadRuntime()
    }

    @objc private func diagnoseCoverTapped() {
        guard sourceRecord.manifest.id == "kei.webtoons.en",
              coverDiagnostic == nil else { return }
        guard let runtime = runtime, let first = items.first else {
            showMessage(
                title: "Diagnóstico de capas",
                message: "Abra Populares e carregue pelo menos uma obra antes do teste."
            )
            return
        }

        navigationItem.rightBarButtonItem?.isEnabled = false
        navigationItem.prompt = "Testando uma capa da lista e dos detalhes…"

        let diagnostic = WebtoonsCoverDiagnostic(
            summary: first,
            runtime: runtime,
            allowedDomains: sourceRecord.manifest.domains
        )
        coverDiagnostic = diagnostic
        diagnostic.run { [weak self] report in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.coverDiagnostic = nil
                self.navigationItem.rightBarButtonItem?.isEnabled = true
                self.navigationItem.prompt = nil

                let alert = UIAlertController(
                    title: "Diagnóstico de capas",
                    message: report,
                    preferredStyle: .alert
                )
                alert.addAction(UIAlertAction(
                    title: "Copiar relatório",
                    style: .default
                ) { _ in
                    UIPasteboard.general.string = report
                })
                alert.addAction(UIAlertAction(title: "Fechar", style: .cancel))
                self.present(alert, animated: true)
            }
        }
    }

    @objc private func refreshPulled() {
        loadFirstPage()
    }

    private func loadRuntime() {
        guard sourceRecord.enabled else {
            showMessage(
                title: "Source desativada",
                message: "Ative essa source em Explorar antes de abri-la."
            )
            return
        }

        loading = true
        navigationItem.prompt = "Carregando source…"

        do {
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()
            loader.load(sourceID: sourceRecord.manifest.id) { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }

                    switch result {
                    case .success(let runtime):
                        self.runtime = runtime
                        self.loading = false
                        self.navigationItem.prompt = nil
                        self.loadFirstPage()

                    case .failure(let error):
                        self.loading = false
                        self.navigationItem.prompt = nil
                        self.refreshControl?.endRefreshing()
                        self.showError(error)
                    }
                }
            }
        } catch {
            loading = false
            navigationItem.prompt = nil
            refreshControl?.endRefreshing()
            showError(error)
        }
    }

    private func loadFirstPage() {
        guard runtime != nil else {
            refreshControl?.endRefreshing()
            return
        }

        currentPage = 1
        items = []
        hasNextPage = false
        tableView.reloadData()
        loadPage(1)
    }

    private func loadPage(_ page: Int) {
        guard let runtime = runtime, !loading else {
            refreshControl?.endRefreshing()
            return
        }

        loading = true
        navigationItem.prompt = currentQuery == nil
            ? "Carregando populares…"
            : "Buscando…"

        let completion: (Result<SourcePagedMangaResult, Error>) -> Void = { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }

                self.loading = false
                self.navigationItem.prompt = nil
                self.refreshControl?.endRefreshing()

                switch result {
                case .success(let pageResult):
                    if page == 1 {
                        self.items = pageResult.items
                    } else {
                        self.items.append(contentsOf: pageResult.items)
                    }

                    self.currentPage = page
                    self.hasNextPage = pageResult.hasNextPage
                    self.tableView.reloadData()

                case .failure(let error):
                    self.showError(error)
                }
            }
        }

        if let query = currentQuery, !query.isEmpty {
            runtime.callDecoded(
                "search",
                arguments: [query, page, [] as [Any]],
                as: SourcePagedMangaResult.self,
                completion: completion
            )
        } else {
            runtime.callDecoded(
                "popular",
                arguments: [page],
                as: SourcePagedMangaResult.self,
                completion: completion
            )
        }
    }

    func searchBarSearchButtonClicked(_ searchBar: UISearchBar) {
        let query = (searchBar.text ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)

        currentQuery = query.isEmpty ? nil : query
        searchBar.resignFirstResponder()
        loadFirstPage()
    }

    func searchBarCancelButtonClicked(_ searchBar: UISearchBar) {
        currentQuery = nil
        loadFirstPage()
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return items.count
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        guard let cell = tableView.dequeueReusableCell(
            withIdentifier: MangaCoverCell.reuseIdentifier,
            for: indexPath
        ) as? MangaCoverCell else {
            return UITableViewCell()
        }

        let item = items[indexPath.row]
        cell.configure(
            title: item.title,
            subtitle: item.url ?? item.id,
            coverURL: item.cover,
            allowedDomains: sourceRecord.manifest.domains
        )
        cell.accessoryType = .disclosureIndicator
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        willDisplay cell: UITableViewCell,
        forRowAt indexPath: IndexPath
    ) {
        guard indexPath.row == items.count - 1,
              hasNextPage,
              !loading else {
            return
        }

        loadPage(currentPage + 1)
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        guard let runtime = runtime else { return }

        navigationController?.pushViewController(
            MangaDetailsViewController(
                sourceRecord: sourceRecord,
                runtime: runtime,
                summary: items[indexPath.row]
            ),
            animated: true
        )
    }

    private func showError(_ error: Error) {
        showMessage(title: "Erro da source", message: error.localizedDescription)
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

// An explicitly initiated, bounded cover probe. It performs at most one
// normal GET for a popular-list thumbnail, one regular source details call,
// and one normal GET for that work's details cover. No automated retries,
// cross-host exceptions, certificate overrides or background monitoring.
//
// URLs may contain tokens or reveal the manga title. The copied report
// includes only the host and safe format metadata, never URL path/query,
// authentication headers, HTML, cookies or response body.
private final class WebtoonsCoverDiagnostic {
    private let summary: SourceMangaSummary
    private let runtime: JavaScriptSourceRuntime
    private let domains: [String]
    private var client: HTTPClient?
    private var lines: [String] = []
    private var finishCallback: ((String) -> Void)?

    init(
        summary: SourceMangaSummary,
        runtime: JavaScriptSourceRuntime,
        allowedDomains: [String]
    ) {
        self.summary = summary
        self.runtime = runtime
        self.domains = allowedDomains
    }

    func run(_ completion: @escaping (String) -> Void) {
        finishCallback = completion
        lines = [
            "iOS: " + UIDevice.current.systemVersion,
            "App: " + (Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"),
            "Fonte: Webtoons.com EN",
            "Amostra: primeira obra da lista (sem título no relatório)",
            "HTTPS padrão; sem login, bypass ou exceções de certificado",
            "Domínios permitidos: " + domains.joined(separator: ", ")
        ]
        probe("Capa da lista", url: summary.cover) { [weak self] rateLimited in
            guard let self = self else { return }
            if rateLimited {
                self.lines.append("Detalhes: não testados após HTTP 429")
                self.finish()
                return
            }
            self.runtime.callDecoded(
                "details",
                arguments: [self.summary.id],
                as: Manga.self
            ) { [weak self] result in
                guard let self = self else { return }
                switch result {
                case .success(let manga):
                    self.probe("Capa dos detalhes", url: manga.cover) { [weak self] _ in
                        self?.finish()
                    }
                case .failure(let error):
                    self.lines.append("Obtenção dos detalhes: " + error.localizedDescription)
                    self.finish()
                }
            }
        }
    }

    private func probe(
        _ label: String,
        url: String?,
        completion: @escaping (Bool) -> Void
    ) {
        guard let raw = url, !raw.isEmpty,
              let parsed = URL(string: raw), parsed.scheme?.lowercased() == "https",
              let host = parsed.host else {
            lines.append(label + ": URL HTTPS ausente ou inválida")
            completion(false)
            return
        }

        lines.append(label + " URL: host=" + host.lowercased() +
            ", extensão=" + (parsed.pathExtension.isEmpty ? "(nenhuma)" : parsed.pathExtension.lowercased()) +
            ", query=" + (parsed.query == nil ? "não" : "sim"))

        let policy = HTTPPolicy(
            allowedDomains: domains,
            timeout: 15,
            maxRedirects: 3,
            maxResponseBytes: 5 * 1024 * 1024
        )
        guard policy.isURLAllowed(parsed) else {
            lines.append(label + ": host fora dos domínios autorizados")
            completion(false)
            return
        }

        let currentClient = HTTPClient(policy: policy)
        client = currentClient // Retain URLSession until asynchronous completion.
        currentClient.send(HTTPRequest(url: raw)) { [weak self] outcome in
            guard let self = self else { return }
            self.client = nil
            switch outcome {
            case .failure(let error):
                self.lines.append(label + ": " + error.localizedDescription)
                completion(false)
            case .success(let response):
                let contentType = response.headers.first {
                    $0.key.lowercased() == "content-type"
                }?.value ?? "(ausente)"
                let mime = contentType.components(separatedBy: ";").first ?? contentType
                let decoded = UIImage(data: response.data) != nil
                let finalHost = URL(string: response.finalURL)?.host ?? "(desconhecido)"
                self.lines.append(
                    label + ": HTTP " + String(response.statusCode) +
                    ", tipo=" + String(mime.prefix(64)) +
                    ", bytes=" + String(response.data.count) +
                    ", UIImage=" + (decoded ? "SIM" : "NÃO") +
                    ", host final=" + finalHost
                )
                completion(response.statusCode == 429)
            }
        }
    }

    private func finish() {
        client = nil
        let text = lines.joined(separator: "\n")
        let callback = finishCallback
        finishCallback = nil
        callback?(text)
    }
}

final class MangaDetailsViewController: UITableViewController {
    private let sourceRecord: InstalledSourceRecord
    private let runtime: JavaScriptSourceRuntime
    private let summary: SourceMangaSummary

    private var manga: Manga?
    private var chapters: [Chapter] = []
    private var pendingRequests = 0
    private var libraryRepository: LibraryRepository?
    private var readingRepository: ReadingProgressRepository?
    private var downloadManager: ChapterDownloadManager?
    private var chapterStates: [String: ChapterReadingState] = [:]
    private var isInLibrary = false

    init(
        sourceRecord: InstalledSourceRecord,
        runtime: JavaScriptSourceRuntime,
        summary: SourceMangaSummary
    ) {
        self.sourceRecord = sourceRecord
        self.runtime = runtime
        self.summary = summary
        super.init(style: .grouped)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = summary.title
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 92
        tableView.register(
            MangaDetailsHeaderCell.self,
            forCellReuseIdentifier: MangaDetailsHeaderCell.reuseIdentifier
        )
        applyTheme()

        let refreshButton = UIBarButtonItem(
            barButtonSystemItem: .refresh,
            target: self,
            action: #selector(refreshTapped)
        )
        let libraryButton = UIBarButtonItem(
            title: "Biblioteca",
            style: .plain,
            target: self,
            action: #selector(libraryTapped)
        )
        let migrateButton = UIBarButtonItem(
            title: "Migrar",
            style: .plain,
            target: self,
            action: #selector(migrationTapped)
        )
        navigationItem.rightBarButtonItems = [
            refreshButton,
            libraryButton,
            migrateButton
        ]

        do {
            libraryRepository = try LibraryRepository.defaultRepository()
            isInLibrary = try libraryRepository?.isInLibrary(
                sourceID: sourceRecord.manifest.id,
                sourceMangaID: summary.id
            ) ?? false
            updateLibraryButton()
        } catch {
            libraryRepository = nil
        }

        readingRepository = try? ReadingProgressRepository.defaultRepository()
        downloadManager = try? ChapterDownloadManager.defaultManager()

        loadDetailsAndChapters()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadReadingStates()
    }

    @objc private func refreshTapped() {
        loadDetailsAndChapters()
    }


    @objc private func migrationTapped() {
        guard isInLibrary,
              let manga = manga else {
            showMessage(
                title: "Migração",
                message: "Adicione esta obra à Biblioteca antes de migrar."
            )
            return
        }

        navigationController?.pushViewController(
            MigrationViewController(
                originalSource: sourceRecord,
                originalManga: manga,
                originalChapters: chapters
            ),
            animated: true
        )
    }

    @objc private func libraryTapped() {
        guard let manga = manga,
              let repository = libraryRepository else {
            showMessage(
                title: "Biblioteca",
                message: "Aguarde os detalhes do mangá terminarem de carregar."
            )
            return
        }

        do {
            if isInLibrary {
                try repository.remove(
                    sourceID: sourceRecord.manifest.id,
                    sourceMangaID: manga.id
                )
                isInLibrary = false
                showMessage(
                    title: "Biblioteca",
                    message: "Mangá removido da Biblioteca."
                )
            } else {
                try repository.add(
                    sourceID: sourceRecord.manifest.id,
                    manga: manga,
                    chapters: chapters
                )
                isInLibrary = true
                showMessage(
                    title: "Biblioteca",
                    message: "Mangá adicionado à Biblioteca."
                )
            }

            updateLibraryButton()
        } catch {
            showError(error)
        }
    }

    private func updateLibraryButton() {
        guard let items = navigationItem.rightBarButtonItems,
              items.count > 2 else {
            return
        }

        items[1].title = isInLibrary ? "Remover" : "Biblioteca"
        items[2].isEnabled = isInLibrary
    }

    private func loadDetailsAndChapters() {
        guard pendingRequests == 0 else { return }

        pendingRequests = 2
        navigationItem.prompt = "Carregando detalhes e capítulos…"
        navigationItem.rightBarButtonItems?.first?.isEnabled = false

        runtime.callDecoded(
            "details",
            arguments: [summary.id],
            as: Manga.self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }

                switch result {
                case .success(let manga):
                    self.manga = manga
                    self.title = manga.title
                    self.tableView.reloadSections(
                        IndexSet(integer: 0),
                        with: .automatic
                    )

                case .failure(let error):
                    self.showError(error)
                }

                self.finishRequest()
            }
        }

        runtime.callDecoded(
            "chapters",
            arguments: [summary.id],
            as: [Chapter].self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }

                switch result {
                case .success(let chapters):
                    self.chapters = chapters
                    self.reloadReadingStates()
                    self.tableView.reloadSections(
                        IndexSet(integer: 1),
                        with: .automatic
                    )

                case .failure(let error):
                    self.showError(error)
                }

                self.finishRequest()
            }
        }
    }

    private func finishRequest() {
        pendingRequests = max(0, pendingRequests - 1)

        if pendingRequests == 0 {
            navigationItem.prompt = nil
            navigationItem.rightBarButtonItems?.first?.isEnabled = true

            if isInLibrary,
               let manga = manga,
               let repository = libraryRepository {
                do {
                    try repository.add(
                        sourceID: sourceRecord.manifest.id,
                        manga: manga,
                        chapters: chapters
                    )
                } catch {
                    // Details remain usable even if refreshing cached Library
                    // metadata fails; the explicit Library action still reports
                    // persistence errors to the user.
                }
            }
        }
    }

    override func numberOfSections(in tableView: UITableView) -> Int {
        return 2
    }

    override func tableView(
        _ tableView: UITableView,
        titleForHeaderInSection section: Int
    ) -> String? {
        return section == 0 ? "Detalhes" : "Capítulos"
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        if section == 0 {
            return 1
        }

        return chapters.count
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        if indexPath.section == 0 {
            guard let cell = tableView.dequeueReusableCell(
                withIdentifier: MangaDetailsHeaderCell.reuseIdentifier,
                for: indexPath
            ) as? MangaDetailsHeaderCell else {
                return UITableViewCell()
            }

            cell.configure(
                manga: manga,
                fallback: summary,
                allowedDomains: sourceRecord.manifest.domains
            )
            return cell
        }

        let identifier = "ChapterCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)

        let chapter = chapters[indexPath.row]
        cell.textLabel?.text = chapter.name

        var detailParts: [String] = []

        if let number = chapter.number {
            detailParts.append("Cap. \(format(number))")
        }

        if let volume = chapter.volume {
            detailParts.append("Vol. \(format(volume))")
        }

        if let date = chapter.date, !date.isEmpty {
            detailParts.append(date)
        }

        if let scanlator = chapter.scanlator, !scanlator.isEmpty {
            detailParts.append(scanlator)
        }

        if let state = chapterStates[chapter.id] {
            if state.isRead {
                detailParts.append("Lido")
            } else if state.lastPageRead > 0 {
                detailParts.append("Página \(state.lastPageRead + 1)")
            }

            if state.downloaded {
                detailParts.append("Offline")
            }

            cell.accessoryType = state.isRead ? .checkmark : .disclosureIndicator
        } else {
            cell.accessoryType = .disclosureIndicator
        }

        cell.detailTextLabel?.text = detailParts.joined(separator: " • ")
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        guard indexPath.section == 1 else { return }
        loadPages(for: chapters[indexPath.row])
    }

    private func loadPages(for chapter: Chapter) {
        guard let manga = manga else {
            showMessage(
                title: "Leitor",
                message: "Aguarde os detalhes do mangá terminarem de carregar."
            )
            return
        }

        if let manager = downloadManager,
           let localPages = try? manager.localPages(
                sourceID: sourceRecord.manifest.id,
                mangaID: manga.id,
                chapterID: chapter.id
           ),
           !localPages.isEmpty {
            openReader(
                manga: manga,
                chapter: chapter,
                pages: localPages
            )
            return
        }

        navigationItem.prompt = "Resolvendo páginas…"

        runtime.callDecoded(
            "pages",
            arguments: [chapter.id],
            as: [Page].self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.navigationItem.prompt = nil

                switch result {
                case .success(let pages):
                    guard !pages.isEmpty else {
                        self.showError(ReaderError.noPages)
                        return
                    }

                    self.openReader(
                        manga: manga,
                        chapter: chapter,
                        pages: pages
                    )

                case .failure(let error):
                    self.showError(error)
                }
            }
        }
    }

    private func openReader(
        manga: Manga,
        chapter: Chapter,
        pages: [Page]
    ) {
        let reader = ReaderViewController(
            sourceID: sourceRecord.manifest.id,
            manga: manga,
            chapter: chapter,
            pages: pages,
            manifest: sourceRecord.manifest,
            chapters: chapters,
            resolvePages: { [weak self] target, completion in
                guard let self = self else {
                    completion(.failure(ReaderError.noPages))
                    return
                }
                if let manager = self.downloadManager,
                   let local = try? manager.localPages(
                        sourceID: self.sourceRecord.manifest.id,
                        mangaID: manga.id,
                        chapterID: target.id
                   ),
                   !local.isEmpty {
                    completion(.success(local))
                    return
                }
                self.runtime.callDecoded(
                    "pages",
                    arguments: [target.id],
                    as: [Page].self,
                    completion: completion
                )
            }
        )

        reader.hidesBottomBarWhenPushed = true

        navigationController?.pushViewController(
            reader,
            animated: true
        )
    }

    private func reloadReadingStates() {
        guard let repository = readingRepository else { return }

        do {
            chapterStates = try repository.chapterStates(
                sourceID: sourceRecord.manifest.id,
                sourceMangaID: summary.id
            )
            if isViewLoaded {
                tableView.reloadData()
            }
        } catch {
            chapterStates = [:]
        }
    }

    private func downloadChapter(_ chapter: Chapter) {
        guard let manga = manga,
              let manager = downloadManager else {
            showMessage(
                title: "Download",
                message: "O gerenciador de downloads ainda não está disponível."
            )
            return
        }

        navigationItem.prompt = "Preparando download…"

        runtime.callDecoded(
            "pages",
            arguments: [chapter.id],
            as: [Page].self
        ) { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let pages):
                guard !pages.isEmpty else {
                    DispatchQueue.main.async {
                        self.navigationItem.prompt = nil
                        self.showError(ReaderError.noPages)
                    }
                    return
                }

                manager.download(
                    sourceID: self.sourceRecord.manifest.id,
                    manga: manga,
                    chapter: chapter,
                    pages: pages,
                    manifest: self.sourceRecord.manifest,
                    progress: { [weak self] value in
                        self?.navigationItem.prompt = String(
                            format: "Baixando… %.0f%%",
                            value * 100
                        )
                    },
                    completion: { [weak self] downloadResult in
                        DispatchQueue.main.async {
                            guard let self = self else { return }
                            self.navigationItem.prompt = nil

                            switch downloadResult {
                            case .success:
                                self.reloadReadingStates()
                                self.showMessage(
                                    title: "Download concluído",
                                    message: "\(chapter.name) está disponível offline."
                                )

                            case .failure(let error):
                                self.showError(error)
                            }
                        }
                    }
                )

            case .failure(let error):
                DispatchQueue.main.async {
                    self.navigationItem.prompt = nil
                    self.showError(error)
                }
            }
        }
    }

    private func removeDownload(_ chapter: Chapter) {
        guard let manga = manga,
              let manager = downloadManager else {
            return
        }

        do {
            try manager.remove(
                sourceID: sourceRecord.manifest.id,
                mangaID: manga.id,
                chapterID: chapter.id
            )
            reloadReadingStates()
            showMessage(
                title: "Download removido",
                message: "\(chapter.name) foi removido do armazenamento offline."
            )
        } catch {
            showError(error)
        }
    }

    override func tableView(
        _ tableView: UITableView,
        editActionsForRowAt indexPath: IndexPath
    ) -> [UITableViewRowAction]? {
        guard indexPath.section == 1,
              let manga = manga else {
            return nil
        }

        let chapter = chapters[indexPath.row]
        let state = chapterStates[chapter.id]
        let read = state?.isRead ?? false

        let readAction = UITableViewRowAction(
            style: .normal,
            title: read ? "Não lido" : "Lido"
        ) { [weak self] _, _ in
            guard let self = self,
                  let repository = self.readingRepository else {
                return
            }

            do {
                try repository.markRead(
                    sourceID: self.sourceRecord.manifest.id,
                    manga: manga,
                    chapter: chapter,
                    isRead: !read
                )
                self.reloadReadingStates()
            } catch {
                self.showError(error)
            }
        }

        let downloaded = state?.downloaded ?? false
        let downloadAction = UITableViewRowAction(
            style: downloaded ? .destructive : .normal,
            title: downloaded ? "Remover offline" : "Download"
        ) { [weak self] _, _ in
            if downloaded {
                self?.removeDownload(chapter)
            } else {
                self?.downloadChapter(chapter)
            }
        }

        return [downloadAction, readAction]
    }

    private func format(_ number: Double) -> String {
        if floor(number) == number {
            return String(Int(number))
        }
        return String(number)
    }

    private func showError(_ error: Error) {
        showMessage(title: "Erro da source", message: error.localizedDescription)
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


extension SourceBrowserViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        ThemeManager.shared.style(searchBar: sourceSearchController.searchBar)
        refreshControl?.tintColor = ThemeManager.shared.palette.secondaryText
        tableView.reloadData()
    }
}

extension MangaDetailsViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.visibleCells.compactMap { $0 as? MangaDetailsHeaderCell }.forEach {
            $0.applyPalette()
        }
        tableView.reloadData()
    }
}
