import UIKit

// BEGIN BUILD51_DOWNLOAD_STORAGE_METER
// Read-only app-owned download inspection, bounded for older iOS devices.
enum DownloadStorageMeter {
    struct Snapshot {
        let bytes: Int64
        let files: Int
        let truncated: Bool

        var label: String {
            return "Armazenamento: " + (truncated ? "≥ " : "") +
                ByteCountFormatter.string(fromByteCount: bytes, countStyle: .file) +
                " (" + String(files) + " arquivos" +
                (truncated ? "+)" : ")")
        }
    }

    static func inspect(root: URL, fileManager: FileManager = .default,
                        maximumFiles: Int = 10_000) -> Snapshot {
        guard maximumFiles > 0 else {
            return Snapshot(bytes: 0, files: 0, truncated: true)
        }
        guard let enumerator = fileManager.enumerator(
            at: root,
            includingPropertiesForKeys: [
                .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
            ],
            options: [.skipsHiddenFiles, .skipsPackageDescendants]
        ) else { return Snapshot(bytes: 0, files: 0, truncated: false) }
        var bytes: Int64 = 0
        var files = 0
        var truncated = false
        for case let item as URL in enumerator {
            if files >= maximumFiles { truncated = true; break }
            guard let values = try? item.resourceValues(forKeys: [
                .isRegularFileKey, .isSymbolicLinkKey, .fileSizeKey
            ]), values.isSymbolicLink != true,
                values.isRegularFile == true else { continue }
            files += 1
            let size = Int64(max(0, values.fileSize ?? 0))
            bytes = size > Int64.max - bytes ? Int64.max : bytes + size
        }
        return Snapshot(bytes: bytes, files: files, truncated: truncated)
    }
}
// END BUILD51_DOWNLOAD_STORAGE_METER

final class DownloadsViewController: UITableViewController {
    private var records: [DownloadListRecord] = []
    private var repository: DownloadRepository?
    private var manager: ChapterDownloadManager?
    private var startupError: Error?
    private var refreshTimer: Timer?
    private var retryInFlight = Set<String>()
    private let queueSummaryLabel = UILabel()
    private var storageInfo = "Armazenamento: calcular…"
    private var lastStorageRefresh: TimeInterval = 0
    private var storageEpoch = 0

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Downloads"
        updateDemoTestButton()
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 100
        tableView.register(
            MangaCoverCell.self,
            forCellReuseIdentifier: MangaCoverCell.reuseIdentifier
        )
        configureQueueSummary()
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
        refreshStorageIfNeeded(force: true)
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

    private func updateDemoTestButton() {
        let enabled = UserDefaults.standard.bool(
            forKey: ChapterDownloadManager.demoSlowModeKey
        )
        let demo = UIBarButtonItem(
            title: enabled ? "Teste 8s: ON" : "Teste 8s: OFF",
            style: .plain, target: self, action: #selector(toggleDemoTestMode)
        )
        demo.accessibilityLabel = enabled
            ? "Desativar espera de teste da fonte Demo"
            : "Ativar espera de teste da fonte Demo"
        let queue = UIBarButtonItem(
            title: "Fila", style: .plain,
            target: self, action: #selector(queueTapped)
        )
        navigationItem.rightBarButtonItems = [queue, demo]
    }

    private func configureQueueSummary() {
        let header = UIView(frame: CGRect(
            x: 0, y: 0, width: max(1, tableView.bounds.width), height: 82
        ))
        header.autoresizingMask = [.flexibleWidth]
        header.backgroundColor = ThemeManager.shared.palette.secondaryBackground
        queueSummaryLabel.frame = header.bounds.insetBy(dx: 14, dy: 7)
        queueSummaryLabel.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        queueSummaryLabel.font = UIFont.systemFont(ofSize: 12, weight: .medium)
        queueSummaryLabel.textColor = ThemeManager.shared.palette.secondaryText
        queueSummaryLabel.numberOfLines = 3
        queueSummaryLabel.text = "Fila de downloads"
        header.addSubview(queueSummaryLabel)
        tableView.tableHeaderView = header
    }

    private func updateQueueSummary() {
        let downloading = records.filter { $0.state == "downloading" }.count
        let queued = records.filter { $0.state == "queued" }.count
        let paused = records.filter { $0.state == "paused" }.count
        let failed = records.filter { $0.state == "failed" }.count
        let complete = records.filter { $0.state == "completed" }.count
        queueSummaryLabel.text = "Baixando: \(downloading)  •  Na fila: \(queued)  •  Pausados: \(paused)\n" +
            "Concluídos: \(complete)  •  Com falha: \(failed)\n" + storageInfo
    }

    private func refreshStorageIfNeeded(force: Bool) {
        let now = Date().timeIntervalSince1970
        guard force || now - lastStorageRefresh >= 30 else { return }
        lastStorageRefresh = now
        storageEpoch += 1
        let request = storageEpoch
        let root = FileManager.default.urls(
            for: .applicationSupportDirectory, in: .userDomainMask
        ).first?
            .appendingPathComponent("MangaReader12", isDirectory: true)
            .appendingPathComponent("Downloads", isDirectory: true)

        guard let folder = root else {
            storageInfo = "Armazenamento: indisponível"
            updateQueueSummary()
            return
        }
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let snapshot = DownloadStorageMeter.inspect(root: folder)
            DispatchQueue.main.async {
                guard let self = self, request == self.storageEpoch else { return }
                self.storageInfo = snapshot.label
                self.updateQueueSummary()
            }
        }
    }

    @objc private func queueTapped() {
        let active = records.filter {
            $0.state == "downloading" || $0.state == "queued"
        }
        let paused = records.filter { $0.state == "paused" }
        let alert = UIAlertController(
            title: "Controle da fila",
            message: (queueSummaryLabel.text ?? "") + "\n" +
                "As ações em lote não removem capítulos nem downloads concluídos.",
            preferredStyle: .alert
        )
        if !active.isEmpty {
            alert.addAction(UIAlertAction(
                title: "Pausar \(active.count) ativos", style: .default
            ) { [weak self] _ in self?.pauseActiveBatch(active) })
        }
        if !paused.isEmpty {
            alert.addAction(UIAlertAction(
                title: "Retomar pausados (até 12)", style: .default
            ) { [weak self] _ in self?.resumePausedBatch(Array(paused.prefix(12))) })
        }
        alert.addAction(UIAlertAction(title: "Fechar", style: .cancel))
        present(alert, animated: true)
    }

    private func pauseActiveBatch(_ snapshot: [DownloadListRecord]) {
        guard let manager = manager else { return }
        var changed = 0
        for record in snapshot {
            if (try? manager.pause(
                sourceID: record.sourceID,
                mangaID: record.sourceMangaID,
                chapterID: record.sourceChapterID
            )) == true {
                changed += 1
            }
        }
        reloadDownloads()
        showMessage(
            title: "Fila pausada",
            message: "\(changed) tarefas pausadas. As demais podem ter concluído ou mudado de estado."
        )
    }

    private func resumePausedBatch(_ snapshot: [DownloadListRecord]) {
        guard let manager = manager else { return }
        var changed = 0
        var needsManualRetry = 0
        for record in snapshot {
            if (try? manager.resume(
                sourceID: record.sourceID,
                mangaID: record.sourceMangaID,
                chapterID: record.sourceChapterID
            )) == true {
                changed += 1
            } else {
                // Never automatically refetch source URLs after app restart.
                needsManualRetry += 1
            }
        }
        reloadDownloads()
        showMessage(
            title: "Fila retomada",
            message: "\(changed) retomados com páginas já resolvidas. " +
                "\(needsManualRetry) exigem ação individual para reobter URLs. " +
                "No máximo 12 tarefas são consideradas por vez."
        )
    }

    @objc private func toggleDemoTestMode() {
        let key = ChapterDownloadManager.demoSlowModeKey
        let enabled = !UserDefaults.standard.bool(forKey: key)
        UserDefaults.standard.set(enabled, forKey: key)
        updateDemoTestButton()
        showMessage(
            title: enabled ? "Modo de teste ativado" : "Modo de teste desativado",
            message: enabled
                ? "Somente na fonte Demo, cada página aguardará 8 segundos antes de baixar. Abra a Demo, inicie um download e volte aqui para testar Pausar, Retomar e Priorizar. As fontes reais não são afetadas."
                : "As fontes Demo voltaram à velocidade normal. Downloads reais nunca foram afetados."
        )
    }

    @objc private func refreshPulled() {
        reloadDownloads()
        refreshStorageIfNeeded(force: true)
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
            refreshControl?.endRefreshing()
            return
        }

        let previousRecords = records
        let previousError = startupError?.localizedDescription

        do {
            records = try repository.listDownloads()
            startupError = nil
        } catch {
            startupError = error
        }

        let isEmpty = records.isEmpty && startupError == nil
        if isEmpty {
            if tableView.backgroundView == nil {
                let label = UILabel()
                label.text = "Nenhum capítulo offline."
                label.textAlignment = .center
                label.textColor = ThemeManager.shared.palette.secondaryText
                tableView.backgroundView = label
            }
        } else {
            tableView.backgroundView = nil
        }

        refreshControl?.endRefreshing()
        updateQueueSummary()
        if records != previousRecords {
            refreshStorageIfNeeded(force: false)
        }
        // Do not close swipe-action menus every 1.5 seconds when the list did
        // not actually change (needed for Pause/Resume/Prioritize to be usable).
        if records != previousRecords ||
           startupError?.localizedDescription != previousError {
            tableView.reloadData()
        }
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
              manager != nil,
              indexPath.row < records.count,
              records[indexPath.row].state != "downloading" else {
            return
        }
        // The system swipe-to-delete must pass through the SAME consent
        // as the custom Remover action. Offline pages are not in .mr12backup.
        confirmRemoveDownload(records[indexPath.row])
    }

    override func tableView(
        _ tableView: UITableView,
        editActionsForRowAt indexPath: IndexPath
    ) -> [UITableViewRowAction]? {
        guard startupError == nil else { return nil }
        let record = records[indexPath.row]

        if record.state == "downloading" || record.state == "queued" {
            let pause = UITableViewRowAction(
                style: .normal, title: "Pausar"
            ) { [weak self] _, _ in self?.pauseDownload(record) }
            pause.backgroundColor = UIColor(red: 0.76, green: 0.52, blue: 0.12, alpha: 1)
            if record.state == "queued" {
                let prioritize = UITableViewRowAction(
                    style: .normal, title: "Priorizar"
                ) { [weak self] _, _ in self?.prioritizeDownload(record) }
                prioritize.backgroundColor = UIColor(red: 0.15, green: 0.48, blue: 0.74, alpha: 1)
                return [prioritize, pause]
            }
            return [pause]
        }

        let remove = UITableViewRowAction(
            style: .destructive, title: "Remover"
        ) { [weak self] _, _ in self?.confirmRemoveDownload(record) }

        if record.state == "paused" {
            let resume = UITableViewRowAction(
                style: .normal, title: "Retomar"
            ) { [weak self] _, _ in self?.resumeDownload(record) }
            resume.backgroundColor = UIColor(red: 0.12, green: 0.50, blue: 0.30, alpha: 1)
            return [remove, resume]
        }

        if record.state == "failed" {
            let retry = UITableViewRowAction(
                style: .normal, title: "Tentar novamente"
            ) { [weak self] _, _ in self?.retryDownload(record) }
            retry.backgroundColor = UIColor(red: 0.14, green: 0.50, blue: 0.78, alpha: 1)
            return [remove, retry]
        }

        return [remove]
    }

    private func pauseDownload(_ record: DownloadListRecord) {
        guard let manager = manager else { return }
        do {
            if try !manager.pause(
                sourceID: record.sourceID,
                mangaID: record.sourceMangaID,
                chapterID: record.sourceChapterID
            ) {
                reloadDownloads()
                showMessage(
                    title: "Download não está ativo",
                    message: "Atualize a lista ou reinicie a transferência interrompida."
                )
                return
            }
            reloadDownloads()
        } catch { showError(error) }
    }

    private func resumeDownload(_ record: DownloadListRecord) {
        guard let manager = manager else { return }
        do {
            if try manager.resume(
                sourceID: record.sourceID,
                mangaID: record.sourceMangaID,
                chapterID: record.sourceChapterID
            ) {
                reloadDownloads()
            } else {
                // After app termination the request context is gone. Fetch
                // fresh page URLs using the installed source and start over.
                retryDownload(record)
            }
        } catch { showError(error) }
    }

    private func prioritizeDownload(_ record: DownloadListRecord) {
        guard let manager = manager else { return }
        if manager.prioritize(
            sourceID: record.sourceID,
            mangaID: record.sourceMangaID,
            chapterID: record.sourceChapterID
        ) {
            reloadDownloads()
        } else {
            showMessage(
                title: "Fila",
                message: "Esse download já é o próximo ou começou a baixar."
            )
        }
    }

    private func confirmRemoveDownload(_ record: DownloadListRecord) {
        guard presentedViewController == nil else { return }
        let alert = UIAlertController(
            title: "Apagar páginas offline?",
            message: "Esta ação remove as imagens baixadas deste capítulo. " +
                "O arquivo .mr12backup não contém essas imagens. " +
                "A exclusão não pode ser desfeita por restauração de backup.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Apagar download", style: .destructive) {
            [weak self] _ in self?.removeDownload(record)
        })
        present(alert, animated: true)
    }

    private func removeDownload(_ record: DownloadListRecord) {
        guard let manager = manager else { return }
        let key = [record.sourceID, record.sourceMangaID, record.sourceChapterID]
            .joined(separator: "\u{1F}")
        guard !retryInFlight.contains(key) else {
            showMessage(
                title: "Nova tentativa em andamento",
                message: "Espere a nova tentativa terminar antes de remover o capítulo."
            )
            return
        }
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
        guard presentedViewController == nil else { return }
        let alert = UIAlertController(
            title: "Reiniciar este download?",
            message: "Uma tentativa anterior pode ter páginas parciais. " +
                "Reiniciar substitui os arquivos locais dessa tentativa. " +
                "As imagens não estão incluídas no .mr12backup.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Reiniciar download", style: .destructive) {
            [weak self] _ in self?.beginRetryDownload(record)
        })
        present(alert, animated: true)
    }

    private func beginRetryDownload(_ record: DownloadListRecord) {
        let key = [record.sourceID, record.sourceMangaID, record.sourceChapterID]
            .joined(separator: "\u{1F}")
        guard !retryInFlight.contains(key) else { return }

        do {
            guard try repository?.record(
                sourceID: record.sourceID,
                sourceMangaID: record.sourceMangaID,
                sourceChapterID: record.sourceChapterID
            ).map({ $0.state == "failed" || $0.state == "paused" }) == true else {
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
                        existingDataPolicy: .replaceAfterExplicitUserConfirmation,
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

        // A completed download is an independent local reading entry point.
        // Do not load the JavaScript source or refresh remote details/chapters:
        // those requests fail with -1009 in airplane mode even though the
        // downloaded pages are present on disk.
        guard let manager = manager else {
            showMessage(
                title: "Leitura offline",
                message: "Não foi possível abrir o gerenciador de downloads."
            )
            return
        }

        do {
            let lifecycle = try SourceLifecycleManager.defaultManager()
            guard let source = try lifecycle.installedSources().first(where: {
                $0.manifest.id == record.sourceID
            }) else {
                showMessage(
                    title: "Fonte não instalada",
                    message: "Reinstale a fonte para abrir este download. Os arquivos locais não foram apagados."
                )
                return
            }

            guard let pages = try manager.localPages(
                sourceID: record.sourceID,
                mangaID: record.sourceMangaID,
                chapterID: record.sourceChapterID
            ), !pages.isEmpty else {
                showMessage(
                    title: "Arquivos indisponíveis",
                    message: "Este capítulo está marcado como baixado, mas suas páginas não foram encontradas. Os outros downloads foram preservados."
                )
                return
            }

            // Read the exact persisted manga/chapter metadata. Synthetic
            // placeholder objects can erase valid chapter numbers and cover
            // metadata when the reader records progress in SQLite.
            guard let snapshot = try DownloadRepository.defaultRepository()
                .completedOfflineSnapshot(
                    sourceID: record.sourceID,
                    sourceMangaID: record.sourceMangaID
                ),
                let chapter = snapshot.chapters.first(where: {
                    $0.id == record.sourceChapterID
                }) else {
                showMessage(
                    title: "Metadados offline indisponíveis",
                    message: "Não foi possível localizar os metadados locais deste capítulo. Os arquivos não foram alterados."
                )
                return
            }

            let reader = ReaderViewController(
                sourceID: source.manifest.id,
                manga: snapshot.manga,
                chapter: chapter,
                pages: pages,
                manifest: source.manifest,
                chapters: snapshot.chapters,
                resolvePages: { target, completion in
                    do {
                        guard let local = try manager.localPages(
                            sourceID: record.sourceID,
                            mangaID: record.sourceMangaID,
                            chapterID: target.id
                        ), !local.isEmpty else {
                            completion(.failure(ReaderError.noPages))
                            return
                        }
                        completion(.success(local))
                    } catch {
                        completion(.failure(error))
                    }
                }
            )
            reader.hidesBottomBarWhenPushed = true
            navigationController?.pushViewController(reader, animated: true)
        } catch ChapterDownloadError.missingCompletedFiles {
            showMessage(
                title: "Capítulo offline incompleto",
                message: "Este download possui páginas ausentes, vazias ou " +
                    "inválidas. Nenhum arquivo foi apagado. " +
                    "Não restaure o backup para corrigir este capítulo."
            )
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
        case "queued":
            return "Na fila"
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
        tableView.tableHeaderView?.backgroundColor =
            ThemeManager.shared.palette.secondaryBackground
        queueSummaryLabel.textColor = ThemeManager.shared.palette.secondaryText
        tableView.reloadData()
    }
}
