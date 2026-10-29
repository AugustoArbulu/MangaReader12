import UIKit

final class MigrationViewController: UITableViewController {
    private let originalSource: InstalledSourceRecord
    private let originalManga: Manga
    private let originalChapters: [Chapter]
    private var manager: MigrationManager?
    private var candidates: [MigrationCandidate] = []
    private var searching = false

    init(
        originalSource: InstalledSourceRecord,
        originalManga: Manga,
        originalChapters: [Chapter]
    ) {
        self.originalSource = originalSource
        self.originalManga = originalManga
        self.originalChapters = originalChapters
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Migrar"
        navigationItem.prompt = originalManga.title
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 100
        tableView.register(
            MangaCoverCell.self,
            forCellReuseIdentifier: MangaCoverCell.reuseIdentifier
        )
        applyTheme()

        do {
            manager = try MigrationManager.defaultManager()
            beginSearch()
        } catch {
            showError(error)
        }
    }

    private func beginSearch() {
        guard let manager = manager, !searching else { return }

        searching = true
        candidates = []
        tableView.reloadData()
        navigationItem.prompt = "Buscando \(originalManga.title)…"

        manager.search(
            title: originalManga.title,
            excludingSourceID: originalSource.manifest.id,
            progress: { [weak self] completed, total in
                self?.navigationItem.prompt = "Buscando sources \(completed)/\(total)…"
            },
            completion: { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }
                    self.searching = false
                    self.navigationItem.prompt = self.originalManga.title

                    switch result {
                    case .success(let values):
                        self.candidates = values
                        self.updateEmptyState()
                        self.tableView.reloadData()

                    case .failure(let error):
                        self.showError(error)
                        self.updateEmptyState()
                    }
                }
            }
        )
    }

    private func updateEmptyState() {
        if candidates.isEmpty && !searching {
            let label = UILabel()
            label.text = "Nenhum resultado encontrado nas outras sources instaladas e ativadas."
            label.textColor = ThemeManager.shared.palette.secondaryText
            label.textAlignment = .center
            label.numberOfLines = 0
            tableView.backgroundView = label
        } else {
            tableView.backgroundView = nil
        }
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return candidates.count
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

        let candidate = candidates[indexPath.row]
        cell.configure(
            title: candidate.summary.title,
            subtitle: "\(candidate.source.manifest.name) • v\(candidate.source.manifest.version)",
            coverURL: candidate.summary.cover,
            allowedDomains: candidate.source.manifest.domains
        )
        cell.accessoryType = .disclosureIndicator
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        confirmMigration(candidates[indexPath.row])
    }

    private func confirmMigration(_ candidate: MigrationCandidate) {
        let alert = UIAlertController(
            title: "Migrar para \(candidate.source.manifest.name)?",
            message: "Biblioteca, categorias, progresso e histórico compatíveis serão transferidos. Downloads offline não são transferidos.",
            preferredStyle: .alert
        )

        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(
            title: "Migrar",
            style: .default
        ) { [weak self] _ in
            self?.performMigration(candidate)
        })

        present(alert, animated: true)
    }

    private func performMigration(_ candidate: MigrationCandidate) {
        guard let manager = manager else { return }

        navigationItem.prompt = "Migrando…"
        view.isUserInteractionEnabled = false

        manager.migrate(
            originalSourceID: originalSource.manifest.id,
            originalManga: originalManga,
            originalChapters: originalChapters,
            candidate: candidate
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.view.isUserInteractionEnabled = true
                self.navigationItem.prompt = nil

                switch result {
                case .success(let report):
                    let alert = UIAlertController(
                        title: "Migração concluída",
                        message: "\(report.targetTitle)\n\n\(report.matchedChapterStates) estado(s) de capítulo e \(report.categoriesTransferred) categoria(s) transferidos.",
                        preferredStyle: .alert
                    )
                    alert.addAction(UIAlertAction(
                        title: "OK",
                        style: .default
                    ) { _ in
                        self.navigationController?.popToRootViewController(
                            animated: true
                        )
                    })
                    self.present(alert, animated: true)

                case .failure(let error):
                    self.showError(error)
                }
            }
        }
    }

    private func showError(_ error: Error) {
        let alert = UIAlertController(
            title: "Erro de migração",
            message: error.localizedDescription,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

extension MigrationViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.backgroundView?.backgroundColor = ThemeManager.shared.palette.background
        tableView.reloadData()
    }
}
