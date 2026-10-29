import UIKit

final class HistoryViewController: UITableViewController {
    private var records: [HistoryRecord] = []
    private var repository: ReadingProgressRepository?
    private var startupError: Error?
    private let dateFormatter: DateFormatter = {
        let formatter = DateFormatter()
        formatter.dateStyle = .short
        formatter.timeStyle = .short
        return formatter
    }()

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Histórico"
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 64
        applyTheme()

        do {
            repository = try ReadingProgressRepository.defaultRepository()
        } catch {
            startupError = error
        }

        reloadHistory()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadHistory()
    }

    private func reloadHistory() {
        guard let repository = repository else {
            tableView.reloadData()
            return
        }

        do {
            records = try repository.history()
            startupError = nil
        } catch {
            startupError = error
        }

        if records.isEmpty && startupError == nil {
            let label = UILabel()
            label.text = "Seu histórico de leitura aparecerá aqui."
            label.textAlignment = .center
            label.numberOfLines = 0
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
        let identifier = "HistoryCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)

        if let error = startupError {
            cell.textLabel?.text = "Erro ao abrir Histórico"
            cell.detailTextLabel?.text = error.localizedDescription
            cell.detailTextLabel?.numberOfLines = 0
            cell.accessoryType = .none
            return cell
        }

        let record = records[indexPath.row]
        cell.textLabel?.text = record.mangaTitle

        var details: [String] = []
        if let chapterName = record.chapterName {
            details.append(chapterName)
        }
        details.append(dateFormatter.string(
            from: Date(timeIntervalSince1970: record.lastReadAt)
        ))

        cell.detailTextLabel?.text = details.joined(separator: " • ")
        cell.detailTextLabel?.numberOfLines = 2
        cell.accessoryType = .disclosureIndicator
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
              let repository = repository,
              startupError == nil else {
            return
        }

        let record = records[indexPath.row]

        do {
            try repository.removeHistory(
                sourceID: record.sourceID,
                sourceMangaID: record.sourceMangaID
            )
            reloadHistory()
        } catch {
            showError(error)
        }
    }

    private func open(_ record: HistoryRecord) {
        do {
            let manager = try SourceLifecycleManager.defaultManager()
            guard let sourceRecord = try manager.installedSources().first(where: {
                $0.manifest.id == record.sourceID
            }) else {
                showMessage(
                    title: "Source ausente",
                    message: "A source usada neste histórico não está instalada."
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

            loader.load(sourceID: record.sourceID) { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.navigationItem.prompt = nil

                    switch result {
                    case .success(let runtime):
                        let summary = SourceMangaSummary(
                            id: record.sourceMangaID,
                            title: record.mangaTitle,
                            cover: record.cover,
                            url: record.mangaURL
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

extension HistoryViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
