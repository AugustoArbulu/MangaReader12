import UIKit

final class LibraryViewController: UITableViewController {
    private var records: [LibraryMangaRecord] = []
    private var repository: LibraryRepository?
    private var startupError: Error?

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Biblioteca"
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 64

        do {
            repository = try LibraryRepository.defaultRepository()
        } catch {
            startupError = error
        }

        reloadLibrary()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadLibrary()
    }

    private func reloadLibrary() {
        guard let repository = repository else {
            tableView.reloadData()
            return
        }

        do {
            records = try repository.list()
            startupError = nil
        } catch {
            startupError = error
        }

        tableView.backgroundView = records.isEmpty && startupError == nil
            ? emptyLabel()
            : nil
        tableView.reloadData()
    }

    private func emptyLabel() -> UIView {
        let label = UILabel()
        label.text = "Sua biblioteca está vazia.\nAdicione um mangá pela tela de detalhes."
        label.textColor = .darkGray
        label.textAlignment = .center
        label.numberOfLines = 0
        return label
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
        let identifier = "LibraryCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)

        if let error = startupError {
            cell.textLabel?.text = "Erro ao abrir Biblioteca"
            cell.detailTextLabel?.text = error.localizedDescription
            cell.detailTextLabel?.numberOfLines = 0
            cell.accessoryType = .none
            return cell
        }

        let record = records[indexPath.row]
        cell.textLabel?.text = record.title
        cell.detailTextLabel?.text = record.status.rawValue
        cell.accessoryType = .disclosureIndicator
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        guard startupError == nil else { return }
        open(record: records[indexPath.row])
    }

    override func tableView(
        _ tableView: UITableView,
        commit editingStyle: UITableViewCell.EditingStyle,
        forRowAt indexPath: IndexPath
    ) {
        guard editingStyle == .delete,
              let repository = repository else {
            return
        }

        let record = records[indexPath.row]

        do {
            try repository.remove(
                sourceID: record.sourceID,
                sourceMangaID: record.sourceMangaID
            )
            reloadLibrary()
        } catch {
            showError(error)
        }
    }

    private func open(record: LibraryMangaRecord) {
        do {
            let manager = try SourceLifecycleManager.defaultManager()
            guard let sourceRecord = try manager.installedSources().first(where: {
                $0.manifest.id == record.sourceID
            }) else {
                showMessage(
                    title: "Source ausente",
                    message: "A source usada por este mangá não está instalada."
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

            let loader = try InstalledSourceRuntimeLoader.defaultLoader()
            navigationItem.prompt = "Carregando source…"

            loader.load(sourceID: record.sourceID) { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.navigationItem.prompt = nil

                    switch result {
                    case .success(let runtime):
                        let summary = SourceMangaSummary(
                            id: record.sourceMangaID,
                            title: record.title,
                            cover: record.cover,
                            url: record.url
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
