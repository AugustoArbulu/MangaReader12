import UIKit

final class SourceBrowserViewController: UITableViewController, UISearchBarDelegate {
    private let sourceRecord: InstalledSourceRecord
    private var runtime: JavaScriptSourceRuntime?
    private var items: [SourceMangaSummary] = []
    private var currentPage = 1
    private var hasNextPage = false
    private var loading = false
    private var currentQuery: String?

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
        tableView.estimatedRowHeight = 58
        navigationItem.searchController = sourceSearchController
        navigationItem.hidesSearchBarWhenScrolling = false
        definesPresentationContext = true

        refreshControl = UIRefreshControl()
        refreshControl?.addTarget(
            self,
            action: #selector(refreshPulled),
            for: .valueChanged
        )

        loadRuntime()
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
        let identifier = "SourceMangaCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)

        let item = items[indexPath.row]
        cell.textLabel?.text = item.title
        cell.textLabel?.numberOfLines = 2
        cell.detailTextLabel?.text = item.url ?? item.id
        cell.detailTextLabel?.numberOfLines = 2
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

final class MangaDetailsViewController: UITableViewController {
    private let runtime: JavaScriptSourceRuntime
    private let summary: SourceMangaSummary

    private var manga: Manga?
    private var chapters: [Chapter] = []
    private var pendingRequests = 0

    init(
        runtime: JavaScriptSourceRuntime,
        summary: SourceMangaSummary
    ) {
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
        tableView.estimatedRowHeight = 74

        navigationItem.rightBarButtonItem = UIBarButtonItem(
            barButtonSystemItem: .refresh,
            target: self,
            action: #selector(refreshTapped)
        )

        loadDetailsAndChapters()
    }

    @objc private func refreshTapped() {
        loadDetailsAndChapters()
    }

    private func loadDetailsAndChapters() {
        guard pendingRequests == 0 else { return }

        pendingRequests = 2
        navigationItem.prompt = "Carregando detalhes e capítulos…"
        navigationItem.rightBarButtonItem?.isEnabled = false

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
            navigationItem.rightBarButtonItem?.isEnabled = true
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
            let identifier = "MangaInfoCell"
            let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
                ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)

            cell.textLabel?.numberOfLines = 0
            cell.detailTextLabel?.numberOfLines = 0
            cell.selectionStyle = .none
            cell.accessoryType = .none

            if let manga = manga {
                cell.textLabel?.text = manga.title

                var detailParts: [String] = []

                if let author = manga.author, !author.isEmpty {
                    detailParts.append("Autor: \(author)")
                }

                detailParts.append("Status: \(manga.status.rawValue)")

                if !manga.genres.isEmpty {
                    detailParts.append("Gêneros: \(manga.genres.joined(separator: ", "))")
                }

                if let description = manga.description, !description.isEmpty {
                    detailParts.append(description)
                }

                cell.detailTextLabel?.text = detailParts.joined(separator: "\n")
            } else {
                cell.textLabel?.text = summary.title
                cell.detailTextLabel?.text = "Carregando…"
            }

            return cell
        }

        let identifier = "ChapterCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)

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

        cell.detailTextLabel?.text = detailParts.joined(separator: " • ")
        cell.accessoryType = .disclosureIndicator
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
                    let firstURL = pages.first?.imageUrl ?? "nenhuma"
                    self.showMessage(
                        title: "\(pages.count) página(s)",
                        message: "Primeira imagem: \(firstURL)"
                    )

                case .failure(let error):
                    self.showError(error)
                }
            }
        }
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
