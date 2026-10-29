import UIKit

final class LibraryViewController: UITableViewController {
    private var records: [LibraryMangaRecord] = []
    private var repository: LibraryRepository?
    private var categoryRepository: CategoryRepository?
    private var categories: [CategoryRecord] = []
    private var selectedCategoryID: Int64?
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
        applyTheme()

        navigationItem.rightBarButtonItems = [
            UIBarButtonItem(
                title: "Categorias",
                style: .plain,
                target: self,
                action: #selector(categoriesTapped)
            ),
            UIBarButtonItem(
                title: "Filtrar",
                style: .plain,
                target: self,
                action: #selector(filterTapped)
            )
        ]

        do {
            repository = try LibraryRepository.defaultRepository()
            categoryRepository = try CategoryRepository.defaultRepository()
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
            categories = try categoryRepository?.list() ?? []

            if let selectedCategoryID = selectedCategoryID,
               categories.contains(where: { $0.internalID == selectedCategoryID }) {
                records = try repository.list(categoryID: selectedCategoryID)
            } else {
                self.selectedCategoryID = nil
                records = try repository.list()
            }

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
        label.textColor = ThemeManager.shared.palette.secondaryText
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
        ThemeManager.shared.style(cell: cell)

        if let error = startupError {
            cell.textLabel?.text = "Erro ao abrir Biblioteca"
            cell.detailTextLabel?.text = error.localizedDescription
            cell.detailTextLabel?.numberOfLines = 0
            cell.accessoryType = .none
            return cell
        }

        let record = records[indexPath.row]
        cell.textLabel?.text = record.title

        var details = [record.status.rawValue]
        if let categoryRepository = categoryRepository,
           let names = try? categoryRepository.names(mangaID: record.internalID),
           !names.isEmpty {
            details.append(names.joined(separator: ", "))
        }

        cell.detailTextLabel?.text = details.joined(separator: " • ")
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
        editActionsForRowAt indexPath: IndexPath
    ) -> [UITableViewRowAction]? {
        let record = records[indexPath.row]

        let remove = UITableViewRowAction(
            style: .destructive,
            title: "Remover"
        ) { [weak self] _, _ in
            guard let self = self,
                  let repository = self.repository else {
                return
            }

            do {
                try repository.remove(
                    sourceID: record.sourceID,
                    sourceMangaID: record.sourceMangaID
                )
                self.reloadLibrary()
            } catch {
                self.showError(error)
            }
        }

        let categories = UITableViewRowAction(
            style: .normal,
            title: "Categorias"
        ) { [weak self] _, _ in
            guard let self = self else { return }
            self.navigationController?.pushViewController(
                CategoryAssignmentViewController(
                    mangaID: record.internalID,
                    mangaTitle: record.title
                ),
                animated: true
            )
        }

        return [remove, categories]
    }

    @objc private func categoriesTapped() {
        navigationController?.pushViewController(
            CategoryManagerViewController(),
            animated: true
        )
    }

    @objc private func filterTapped() {
        let sheet = UIAlertController(
            title: "Filtrar Biblioteca",
            message: nil,
            preferredStyle: .actionSheet
        )

        sheet.addAction(UIAlertAction(
            title: selectedCategoryID == nil ? "✓ Todos" : "Todos",
            style: .default
        ) { [weak self] _ in
            self?.selectedCategoryID = nil
            self?.reloadLibrary()
        })

        for category in categories {
            let selected = selectedCategoryID == category.internalID
            sheet.addAction(UIAlertAction(
                title: selected ? "✓ \(category.name)" : category.name,
                style: .default
            ) { [weak self] _ in
                self?.selectedCategoryID = category.internalID
                self?.reloadLibrary()
            })
        }

        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))

        if let popover = sheet.popoverPresentationController {
            popover.barButtonItem = navigationItem.rightBarButtonItems?.last
        }

        present(sheet, animated: true)
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


extension LibraryViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.backgroundView?.backgroundColor = ThemeManager.shared.palette.background
        tableView.reloadData()
    }
}
