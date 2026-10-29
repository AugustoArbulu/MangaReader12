import UIKit

final class DownloadsViewController: UITableViewController {
    private var records: [DownloadListRecord] = []
    private var repository: DownloadRepository?
    private var manager: ChapterDownloadManager?
    private var startupError: Error?

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
    }

    private func reloadDownloads() {
        guard let repository = repository else {
            tableView.reloadData()
            return
        }

        do {
            records = try repository.listDownloads()
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
            coverURL: nil,
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
              let manager = manager else {
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
