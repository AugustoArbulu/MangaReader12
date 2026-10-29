import UIKit

final class CategoryManagerViewController: UITableViewController {
    private var repository: CategoryRepository?
    private var categories: [CategoryRecord] = []
    private var startupError: Error?

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Categorias"
        tableView.tableFooterView = UIView()
        applyTheme()

        navigationItem.rightBarButtonItem = UIBarButtonItem(
            barButtonSystemItem: .add,
            target: self,
            action: #selector(addTapped)
        )

        do {
            repository = try CategoryRepository.defaultRepository()
        } catch {
            startupError = error
        }

        reloadCategories()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadCategories()
    }

    @objc private func addTapped() {
        let alert = UIAlertController(
            title: "Nova categoria",
            message: nil,
            preferredStyle: .alert
        )

        alert.addTextField { field in
            field.placeholder = "Nome"
            field.autocapitalizationType = .sentences
        }

        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Criar", style: .default) { [weak self, weak alert] _ in
            guard let self = self,
                  let name = alert?.textFields?.first?.text,
                  let repository = self.repository else {
                return
            }

            do {
                _ = try repository.create(name: name)
                self.reloadCategories()
            } catch {
                self.showError(error)
            }
        })

        present(alert, animated: true)
    }

    private func reloadCategories() {
        guard let repository = repository else {
            tableView.reloadData()
            return
        }

        do {
            categories = try repository.list()
            startupError = nil
        } catch {
            startupError = error
        }

        if categories.isEmpty && startupError == nil {
            let label = UILabel()
            label.text = "Nenhuma categoria criada."
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
        return startupError == nil ? categories.count : 1
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "CategoryCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)

        if let error = startupError {
            cell.textLabel?.text = "Erro ao abrir Categorias"
            cell.detailTextLabel?.text = error.localizedDescription
            cell.accessoryType = .none
            return cell
        }

        let category = categories[indexPath.row]
        cell.textLabel?.text = category.name
        cell.detailTextLabel?.text = "Ordem \(category.sortOrder + 1)"
        cell.accessoryType = .none
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        commit editingStyle: UITableViewCell.EditingStyle,
        forRowAt indexPath: IndexPath
    ) {
        guard editingStyle == .delete,
              startupError == nil,
              let repository = repository else {
            return
        }

        do {
            try repository.remove(categoryID: categories[indexPath.row].internalID)
            reloadCategories()
        } catch {
            showError(error)
        }
    }

    private func showError(_ error: Error) {
        let alert = UIAlertController(
            title: "Erro",
            message: error.localizedDescription,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

final class CategoryAssignmentViewController: UITableViewController {
    private let mangaID: Int64
    private let mangaTitle: String
    private var repository: CategoryRepository?
    private var categories: [CategoryRecord] = []
    private var selectedIDs = Set<Int64>()

    init(mangaID: Int64, mangaTitle: String) {
        self.mangaID = mangaID
        self.mangaTitle = mangaTitle
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Categorias"
        navigationItem.prompt = mangaTitle
        tableView.tableFooterView = UIView()
        applyTheme()

        navigationItem.rightBarButtonItem = UIBarButtonItem(
            title: "Salvar",
            style: .done,
            target: self,
            action: #selector(saveTapped)
        )

        do {
            repository = try CategoryRepository.defaultRepository()
            reload()
        } catch {
            showError(error)
        }
    }

    private func reload() {
        guard let repository = repository else { return }

        do {
            categories = try repository.list()
            selectedIDs = try repository.categoryIDs(mangaID: mangaID)
            tableView.reloadData()
        } catch {
            showError(error)
        }
    }

    @objc private func saveTapped() {
        guard let repository = repository else { return }

        do {
            try repository.setCategories(
                mangaID: mangaID,
                categoryIDs: selectedIDs
            )
            navigationController?.popViewController(animated: true)
        } catch {
            showError(error)
        }
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return categories.count
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "CategoryAssignmentCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .default, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)

        let category = categories[indexPath.row]
        cell.textLabel?.text = category.name
        cell.accessoryType = selectedIDs.contains(category.internalID)
            ? .checkmark
            : .none
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        let id = categories[indexPath.row].internalID

        if selectedIDs.contains(id) {
            selectedIDs.remove(id)
        } else {
            selectedIDs.insert(id)
        }

        tableView.reloadRows(at: [indexPath], with: .none)
    }

    private func showError(_ error: Error) {
        let alert = UIAlertController(
            title: "Erro",
            message: error.localizedDescription,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

extension CategoryManagerViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.backgroundView?.backgroundColor = ThemeManager.shared.palette.background
        tableView.reloadData()
    }
}

extension CategoryAssignmentViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
