import UIKit

final class DownloadsViewController: UITableViewController {
    private var records: [DownloadListRecord] = []
    private var repository: DownloadRepository?
    private var manager: ChapterDownloadManager?
    private var startupError: Error?
    private var refreshTimer: Timer?
    private var retryInFlight = Set<String>()

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Downloads"
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 100
        tableView.register(
            MangaCoverCell.self,
            forCellReuseIdentifier: MangaCoverCell.reuseIdentifier
        )
        refreshControl = UIRefreshControl()
        refreshControl?.addTarget(self, action: #selector(refreshPulled), for: .valueChanged)
        applyTheme()

        do {
            repository = try DownloadRepository.defaultRepository()
            manager = try ChapterDownloadManager.defaultManager()
        } catch {
            startupError = error
        }

        reloadDownloads()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadDownloads()
        startRefreshTimer()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        refreshTimer?.invalidate()
        refreshTimer = nil
    }

    deinit {
        refreshTimer?.invalidate()
    }

    @objc private func refreshPulled() {
        reloadDownloads()
    }

    private func startRefreshTimer() {
        guard refreshTimer == nil else { return }
        // The network downloads can be running on a different screen.
        // Poll only while Downloads is visible, keeping iOS 12 compatible.
        refreshTimer = Timer.scheduledTimer(
            timeInterval: 1.5,
            target: self,
            selector: #selector(refreshTick),
            userInfo: nil,
            repeats: true
        )
    }

    @objc private func refreshTick() {
        reloadDownloads()
    }

    private func reloadDownloads() {
        guard let repository = repository else {
            tableView.reloadData()
            return
        }

        do {
            let nextRecords = try repository.listDownloads()
            if records != nextRecords || startupError != nil {
                records = nextRecords
                tableView.reloadData()
            }
            startupError = nil
        } catch {
            startupError = error
        }

        if records.isEmpty && startupError == nil {
            let label = UILabel()
            label.text = "Nenhum capítulo offline."
            label.textAlignment = .center
            label.textColor = ThemeManager.shared.palette.secondaryText
            tableView.backgroundView = label
        } else {
            tableView.backgroundView = nil
        }

        refreshControl?.endRefreshing()
        tableView.reloadData()
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return startupError == nil ? records.count : 1
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        if let error = startupError {
            let cell = tableView.dequeueReusableCell(withIdentifier: "DownloadError")
                ?? UITableViewCell(style: .subtitle, reuseIdentifier: "DownloadError")
            ThemeManager.shared.style(cell: cell)
            cell.textLabel?.text = "Erro ao abrir Downloads"
            cell.detailTextLabel?.text = error.localizedDescription
            cell.detailTextLabel?.numberOfLines = 0
            cell.accessoryType = .none
            return cell
        }

        guard let cell = tableView.dequeueReusableCell(
            withIdentifier: MangaCoverCell.reuseIdentifier,
            for: indexPath
        ) as? MangaCoverCell else {
            return UITableViewCell()
        }

        let record = records[indexPath.row]
        let percent = Int(round(record.progress * 100))
        cell.configure(
            title: record.mangaTitle,
            subtitle: "\(record.chapterName) • \(stateText(record.state)) • \(percent)%",
            coverURL: record.cover,
            allowedDomains: [],
            badge: record.state == "completed" ? "Offline" : nil
        )
        cell.accessoryType = record.state == "completed"
            ? .disclosureIndicator
            : .none
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        guard startupError == nil else { return }
        open(records[indexPath.row])
    }

    override func tableView(
        _ tableView: UITableView,
        commit editingStyle: UITableViewCell.EditingStyle,
        forRowAt indexPath: IndexPath
    ) {
        guard editingStyle == .delete,
              startupError == nil,
              let manager = manager,
              records[indexPath.row].state != "downloading" else {
            return
        }

        let record = records[indexPath.row]

        do {
            try manager.remove(
                sourceID: record.sourceID,
                mangaID: record.sourceMangaID,
                chapterID: record.sourceChapterID
            )
            reloadDownloads()
        } catch {
            showError(error)
        }
    }

    override func tableView(
        _ tableView: UITableView,
        editActionsForRowAt indexPath: IndexPath
    ) -> [UITableViewRowAction]? {
        guard startupError == nil else { return nil }
        let record = records[indexPath.row]
        // The original page downloader is not cancellable; do not remove
        // files while they are still being written.
        if record.state == "downloading" { return nil }

        let remove = UITableViewRowAction(
            style: .destructive,
            title: "Remover"
        ) { [weak self] _, _ in
            self?.removeDownload(record)
        }
        if record.state != "failed" { return [remove] }

        let retry = UITableViewRowAction(
            style: .normal,
            title: "Tentar novamente"
        ) { [weak self] _, _ in
            self?.retryDownload(record)
        }
        retry.backgroundColor = UIColor(red: 0.14, green: 0.50, blue: 0.78, alpha: 1)
        return [remove, retry]
    }

    private func removeDownload(_ record: DownloadListRecord) {
        guard let manager = manager else { return }
        do {
            // Re-read current state because a download might have started
            // after the table was rendered.
            let current = try repository?.record(
                sourceID: record.sourceID,
                sourceMangaID: record.sourceMangaID,
                sourceChapterID: record.sourceChapterID
            )
            guard current?.state != "downloading" else {
                showMessage(
                    title: "Download em andamento",
                    message: "Espere o download terminar antes de removê-lo."
                )
                return
            }
            try manager.remove(
                sourceID: record.sourceID,
                mangaID: record.sourceMangaID,
                chapterID: record.sourceChapterID
            )
            reloadDownloads()
        } catch {
            showError(error)
        }
    }

    private func retryDownload(_ record: DownloadListRecord) {
        let key = [record.sourceID, record.sourceMangaID, record.sourceChapterID]
            .joined(separator: "\u{1F}")
        guard !retryInFlight.contains(key) else { return }

        do {
            guard try repository?.record(
                sourceID: record.sourceID,
                sourceMangaID: record.sourceMangaID,
                sourceChapterID: record.sourceChapterID
            )?.state == "failed" else {
                reloadDownloads()
                return
            }

            let lifecycle = try SourceLifecycleManager.defaultManager()
            guard let source = try lifecycle.installedSources().first(where: {
                $0.manifest.id == record.sourceID && $0.enabled
            }) else {
                showMessage(
                    title: "Source indisponível",
                    message: "Instale ou habilite a source do capítulo para tentar novamente."
                )
                return
            }

            retryInFlight.insert(key)
            navigationItem.prompt = "Preparando nova tentativa…"
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()
            loader.load(sourceID: record.sourceID) { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    switch result {
                    case .failure(let error):
                        self.finishRetry(key: key, error: error)
                    case .success(let runtime):
                        self.resolveRetryDetails(
                            record, source: source, runtime: runtime, key: key
                        )
                    }
                }
            }
        } catch {
            retryInFlight.remove(key)
            showError(error)
        }
    }

    private func resolveRetryDetails(
        _ record: DownloadListRecord,
        source: InstalledSourceRecord,
        runtime: JavaScriptSourceRuntime,
        key: String
    ) {
        runtime.callDecoded(
            "details",
            arguments: [record.sourceMangaID],
            as: Manga.self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                switch result {
                case .failure(let error):
                    self.finishRetry(key: key, error: error)
                case .success(let manga):
                    self.resolveRetryChapters(
                        record, manga: manga, source: source, runtime: runtime, key: key
                    )
                }
            }
        }
    }

    private func resolveRetryChapters(
        _ record: DownloadListRecord,
        manga: Manga,
        source: InstalledSourceRecord,
        runtime: JavaScriptSourceRuntime,
        key: String
    ) {
        runtime.callDecoded(
            "chapters",
            arguments: [record.sourceMangaID],
            as: [Chapter].self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                switch result {
                case .failure(let error):
                    self.finishRetry(key: key, error: error)
                case .success(let chapters):
                    guard let chapter = chapters.first(where: {
                        $0.id == record.sourceChapterID
                    }) else {
                        self.finishRetry(
                            key: key,
                            error: ChapterDownloadError.emptyPages
                        )
                        return
                    }
                    self.resolveRetryPages(
                        record, manga: manga, chapter: chapter,
                        source: source, runtime: runtime, key: key
                    )
                }
            }
        }
    }

    private func resolveRetryPages(
        _ record: DownloadListRecord,
        manga: Manga,
        chapter: Chapter,
        source: InstalledSourceRecord,
        runtime: JavaScriptSourceRuntime,
        key: String
    ) {
        runtime.callDecoded(
            "pages",
            arguments: [chapter.id],
            as: [Page].self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                switch result {
                case .failure(let error):
                    self.finishRetry(key: key, error: error)
                case .success(let pages):
                    guard let manager = self.manager, !pages.isEmpty else {
                        self.finishRetry(
                            key: key, error: ChapterDownloadError.emptyPages
                        )
                        return
                    }
                    self.navigationItem.prompt = "Baixando novamente…"
                    manager.download(
                        sourceID: source.manifest.id,
                        manga: manga,
                        chapter: chapter,
                        pages: pages,
                        manifest: source.manifest,
                        progress: { [weak self] _ in self?.reloadDownloads() },
                        completion: { [weak self] result in
                            DispatchQueue.main.async {
                                guard let self = self else { return }
                                switch result {
                                case .success:
                                    self.finishRetry(key: key, error: nil)
                                case .failure(let error):
                                    self.finishRetry(key: key, error: error)
                                }
                            }
                        }
                    )
                }
                self.reloadDownloads()
            }
        }
    }

    private func finishRetry(key: String, error: Error?) {
        retryInFlight.remove(key)
        navigationItem.prompt = nil
        reloadDownloads()
        if let error = error { showError(error) }
    }

    private func open(_ record: DownloadListRecord) {
        guard record.state == "completed" else { return }

        do {
            let lifecycle = try SourceLifecycleManager.defaultManager()
            guard let sourceRecord = try lifecycle.installedSources().first(where: {
                $0.manifest.id == record.sourceID
            }) else {
                showMessage(
                    title: "Source ausente",
                    message: "A source usada por este download não está instalada."
                )
                return
            }

            guard sourceRecord.enabled else {
                showMessage(
                    title: "Source desativada",
                    message: "Ative \(sourceRecord.manifest.name) em Explorar para abrir os detalhes."
                )
                return
            }

            navigationItem.prompt = "Carregando source…"
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()

            loader.load(sourceID: record.sourceID) { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.navigationItem.prompt = nil

                    switch result {
                    case .success(let runtime):
                        let summary = SourceMangaSummary(
                            id: record.sourceMangaID,
                            title: record.mangaTitle,
                            cover: nil,
                            url: nil
                        )

                        self.navigationController?.pushViewController(
                            MangaDetailsViewController(
                                sourceRecord: sourceRecord,
                                runtime: runtime,
                                summary: summary
                            ),
                            animated: true
                        )

                    case .failure(let error):
                        self.showError(error)
                    }
                }
            }
        } catch {
            showError(error)
        }
    }

    private func stateText(_ state: String) -> String {
        switch state {
        case "completed":
            return "Offline"
        case "downloading":
            return "Baixando"
        case "failed":
            return "Falhou"
        case "paused":
            return "Pausado"
        default:
            return state
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

extension DownloadsViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.backgroundView?.backgroundColor = ThemeManager.shared.palette.background
        tableView.reloadData()
    }
}
