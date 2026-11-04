import UIKit

final class UpdatesViewController: UITableViewController {
    private let feedStore = UpdateFeedStore()
    private var events: [LibraryUpdateEvent] = []
    private var updateManager: LibraryUpdateManager?
    private var checking = false
    private var showAll = UserDefaults.standard.bool(forKey: "updates.showAll.v1")
    private var refreshItem: UIBarButtonItem?
    private var markAllItem: UIBarButtonItem?

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Atualizações"
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 100
        tableView.register(
            MangaCoverCell.self,
            forCellReuseIdentifier: MangaCoverCell.reuseIdentifier
        )
        applyTheme()

        let scope = UISegmentedControl(items: ["Novas", "Todas"])
        scope.selectedSegmentIndex = showAll ? 1 : 0
        scope.addTarget(self, action: #selector(scopeChanged(_:)), for: .valueChanged)
        navigationItem.titleView = scope

        refreshItem = UIBarButtonItem(
            barButtonSystemItem: .refresh,
            target: self,
            action: #selector(refreshTapped)
        )
        markAllItem = UIBarButtonItem(
            title: "Marcar vistas", style: .plain,
            target: self, action: #selector(markAllTapped)
        )
        if let refreshItem = refreshItem, let markAllItem = markAllItem {
            navigationItem.rightBarButtonItems = [refreshItem, markAllItem]
        }

        do {
            updateManager = try LibraryUpdateManager.defaultManager()
        } catch {
            showError(error)
        }

        reloadFeed()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadFeed()
    }

    @objc private func scopeChanged(_ control: UISegmentedControl) {
        showAll = control.selectedSegmentIndex == 1
        UserDefaults.standard.set(showAll, forKey: "updates.showAll.v1")
        reloadFeed()
    }

    @objc private func markAllTapped() {
        guard !feedStore.pendingEvents().isEmpty else { return }
        let alert = UIAlertController(
            title: "Marcar novidades como vistas?",
            message: "As atualizações continuarão disponíveis em Todas. " +
                "Isso não marca os capítulos como lidos.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Marcar vistas", style: .default) {
            [weak self] _ in
            self?.feedStore.acknowledgeAll()
            self?.reloadFeed()
        })
        present(alert, animated: true)
    }

    @objc private func refreshTapped() {
        guard !checking,
              let updateManager = updateManager else {
            return
        }

        checking = true
        refreshItem?.isEnabled = false
        markAllItem?.isEnabled = false
        navigationItem.prompt = "Verificando Biblioteca…"

        updateManager.checkAll(
            progress: { [weak self] completed, total in
                self?.navigationItem.prompt = "Verificando \(completed)/\(total)…"
            },
            completion: { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.checking = false
                    self.refreshItem?.isEnabled = true
                    self.navigationItem.prompt = nil

                    switch result {
                    case .success(let value):
                        self.reloadFeed()

                        var message = "\(value.checkedManga) mangá(s) verificado(s)."
                        if value.newChapters.isEmpty {
                            message += "\nNenhum capítulo novo encontrado."
                        } else {
                            message += "\n\(value.newChapters.count) capítulo(s) novo(s) encontrado(s)."
                        }

                        if !value.failures.isEmpty {
                            message += "\n\(value.failures.count) item(ns) não puderam ser verificados."
                        }

                        self.showMessage(
                            title: "Atualização concluída",
                            message: message
                        )

                    case .failure(let error):
                        self.showError(error)
                    }
                }
            }
        )
    }

    private func reloadFeed() {
        events = showAll ? feedStore.events() : feedStore.pendingEvents()
        markAllItem?.isEnabled = !checking && !feedStore.pendingEvents().isEmpty
        if events.isEmpty {
            let label = UILabel()
            label.text = showAll
                ? "Nenhum capítulo novo registrado.\nUse Atualizar para verificar sua Biblioteca."
                : "Nenhuma novidade pendente.\nToque em Todas para ver o histórico."
            label.numberOfLines = 0
            label.textAlignment = .center
            label.textColor = ThemeManager.shared.palette.secondaryText
            tableView.backgroundView = label
        } else {
            tableView.backgroundView = nil
        }

        tableView.reloadData()
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return events.count
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

        let event = events[indexPath.row]
        cell.configure(
            title: event.mangaTitle,
            subtitle: event.chapterName,
            coverURL: event.mangaCover,
            allowedDomains: [],
            badge: feedStore.isAcknowledged(event) ? "Vista" : "Novo",
            sourceID: event.sourceID
        )
        cell.accessoryType = .disclosureIndicator
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        let event = events[indexPath.row]
        // Opening a newly discovered event never changes chapter read state.
        feedStore.acknowledge(event)
        reloadFeed()
        open(event)
    }

    override func tableView(
        _ tableView: UITableView,
        editActionsForRowAt indexPath: IndexPath
    ) -> [UITableViewRowAction]? {
        let event = events[indexPath.row]
        guard !feedStore.isAcknowledged(event) else { return nil }
        let mark = UITableViewRowAction(
            style: .normal, title: "Vista"
        ) { [weak self] _, _ in
            self?.feedStore.acknowledge(event)
            self?.reloadFeed()
        }
        mark.backgroundColor = ThemeManager.shared.palette.accent
        return [mark]
    }

    private func open(_ event: LibraryUpdateEvent) {
        do {
            let lifecycle = try SourceLifecycleManager.defaultManager()

            guard let sourceRecord = try lifecycle.installedSources().first(where: {
                $0.manifest.id == event.sourceID
            }) else {
                showMessage(
                    title: "Source ausente",
                    message: "A source desta atualização não está instalada."
                )
                return
            }

            guard sourceRecord.enabled else {
                showMessage(
                    title: "Source desativada",
                    message: "Ative \(sourceRecord.manifest.name) em Explorar."
                )
                return
            }

            navigationItem.prompt = "Carregando source…"
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()

            loader.load(sourceID: event.sourceID) { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.navigationItem.prompt = nil

                    switch result {
                    case .success(let runtime):
                        let summary = SourceMangaSummary(
                            id: event.sourceMangaID,
                            title: event.mangaTitle,
                            cover: event.mangaCover,
                            url: event.mangaURL
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

extension UpdatesViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.backgroundView?.backgroundColor = ThemeManager.shared.palette.background
        tableView.reloadData()
    }
}
