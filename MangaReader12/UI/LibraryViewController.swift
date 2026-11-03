import UIKit

final class LibraryViewController: UITableViewController, UISearchResultsUpdating {
    private var records: [LibraryMangaRecord] = []
    private var allRecords: [LibraryMangaRecord] = []
    private var metrics: [Int64: LibraryMangaMetrics] = [:]
    private var searchText = ""
    private var sortKey = UserDefaults.standard.string(forKey: "library.sort") ?? "added"
    private var statusKey = UserDefaults.standard.string(forKey: "library.status") ?? "all"
    private var onlyUnread = UserDefaults.standard.bool(forKey: "library.onlyUnread")
    private var onlyDownloaded = UserDefaults.standard.bool(forKey: "library.onlyDownloaded")
    private lazy var librarySearchController: UISearchController = {
        let search = UISearchController(searchResultsController: nil)
        search.obscuresBackgroundDuringPresentation = false
        search.searchBar.placeholder = "Buscar na Biblioteca"
        search.searchResultsUpdater = self
        return search
    }()
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
        tableView.estimatedRowHeight = 100
        tableView.register(
            MangaCoverCell.self,
            forCellReuseIdentifier: MangaCoverCell.reuseIdentifier
        )
        navigationItem.searchController = librarySearchController
        navigationItem.hidesSearchBarWhenScrolling = false
        definesPresentationContext = true
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
            if let savedCategory = UserDefaults.standard.object(forKey: "library.categoryID") as? NSNumber {
                selectedCategoryID = savedCategory.int64Value
            }
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
            if let category = selectedCategoryID,
               categories.contains(where: { $0.internalID == category }) {
                allRecords = try repository.list(categoryID: category)
            } else {
                selectedCategoryID = nil
                UserDefaults.standard.removeObject(forKey: "library.categoryID")
                allRecords = try repository.list()
            }
            metrics = try repository.readingMetrics()
            startupError = nil
            applyLocalFilters()
        } catch {
            startupError = error
            records = []
            tableView.backgroundView = nil
            tableView.reloadData()
        }
    }

    private func applyLocalFilters() {
        records = allRecords.filter { record in
            if !searchText.isEmpty &&
                record.title.range(
                    of: searchText, options: [.caseInsensitive, .diacriticInsensitive]
                ) == nil {
                return false
            }
            if statusKey != "all" && record.status.rawValue != statusKey {
                return false
            }
            let entry = metrics[record.internalID]
            if onlyUnread && (entry?.unreadChapters ?? 0) == 0 {
                return false
            }
            if onlyDownloaded && !(entry?.hasCompletedDownload ?? false) {
                return false
            }
            return true
        }
        records.sort { left, right in
            let first = metrics[left.internalID]
            let second = metrics[right.internalID]
            switch sortKey {
            case "title-az":
                let order = left.title.localizedStandardCompare(right.title)
                if order != .orderedSame { return order == .orderedAscending }
            case "title-za":
                let order = left.title.localizedStandardCompare(right.title)
                if order != .orderedSame { return order == .orderedDescending }
            case "last-read":
                let l = first?.lastReadAt ?? 0
                let r = second?.lastReadAt ?? 0
                if l != r { return l > r }
            case "unread":
                let l = first?.unreadChapters ?? 0
                let r = second?.unreadChapters ?? 0
                if l != r { return l > r }
            default:
                break
            }
            if left.dateAdded != right.dateAdded {
                return left.dateAdded > right.dateAdded
            }
            return left.internalID > right.internalID
        }
        updateFilterPresentation()
    }

    private func updateFilterPresentation() {
        let filtering = selectedCategoryID != nil || statusKey != "all" ||
            onlyUnread || onlyDownloaded || !searchText.isEmpty
        let current = allRecords.count
        navigationItem.rightBarButtonItems?.last?.title = filtering ? "Filtrar •" : "Filtrar"
        tableView.backgroundView = startupError == nil && records.isEmpty
            ? emptyLabel(filtered: filtering || current > 0)
            : nil
        tableView.reloadData()
    }

    func updateSearchResults(for searchController: UISearchController) {
        let value = (searchController.searchBar.text ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard searchText != value else { return }
        searchText = value
        applyLocalFilters()
    }

    private func emptyLabel(filtered: Bool) -> UIView {
        let label = UILabel()
        label.text = filtered
            ? "Nenhuma obra corresponde aos filtros.\nToque em Filtrar para alterar ou limpar."
            : "Sua biblioteca está vazia.\nAdicione um mangá pela tela de detalhes."
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
        if let error = startupError {
            let cell = tableView.dequeueReusableCell(withIdentifier: "LibraryError")
                ?? UITableViewCell(style: .subtitle, reuseIdentifier: "LibraryError")
            ThemeManager.shared.style(cell: cell)
            cell.textLabel?.text = "Erro ao abrir Biblioteca"
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
        var details = [record.status.rawValue]
        if let count = metrics[record.internalID]?.unreadChapters, count > 0 {
            details.append(String(count) + " não lidos")
        }
        if metrics[record.internalID]?.hasCompletedDownload == true {
            details.append("Offline")
        }
        if let categoryRepository = categoryRepository,
           let names = try? categoryRepository.names(mangaID: record.internalID),
           !names.isEmpty {
            details.append(names.joined(separator: ", "))
        }

        cell.configure(
            title: record.title,
            subtitle: details.joined(separator: " • "),
            coverURL: record.cover,
            allowedDomains: []
        )
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
        let controller = LibraryFilterSheetViewController(
            categories: categories,
            selectedCategoryID: selectedCategoryID,
            sortKey: sortKey,
            statusKey: statusKey,
            onlyUnread: onlyUnread,
            onlyDownloaded: onlyDownloaded
        )
        controller.onApply = { [weak self] categoryID, sort, status, unread, downloaded in
            guard let self = self else { return }
            self.selectedCategoryID = categoryID
            self.sortKey = sort
            self.statusKey = status
            self.onlyUnread = unread
            self.onlyDownloaded = downloaded
            let defaults = UserDefaults.standard
            if let id = categoryID {
                defaults.set(NSNumber(value: id), forKey: "library.categoryID")
            } else {
                defaults.removeObject(forKey: "library.categoryID")
            }
            defaults.set(sort, forKey: "library.sort")
            defaults.set(status, forKey: "library.status")
            defaults.set(unread, forKey: "library.onlyUnread")
            defaults.set(downloaded, forKey: "library.onlyDownloaded")
            self.reloadLibrary()
        }
        controller.modalPresentationStyle = .overFullScreen
        controller.modalTransitionStyle = .crossDissolve
        present(controller, animated: true)
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
        ThemeManager.shared.style(searchBar: librarySearchController.searchBar)
        tableView.backgroundView?.backgroundColor = ThemeManager.shared.palette.background
        tableView.reloadData()
    }
}

// Independent local-library filter panel. Compatible with UIKit on iOS 12:
// no UISheetPresentationController or third-party UI framework is required.
private final class LibraryFilterSheetViewController: UIViewController {
    typealias ApplyHandler = (Int64?, String, String, Bool, Bool) -> Void
    var onApply: ApplyHandler?

    private let categories: [CategoryRecord]
    private var categoryID: Int64?
    private var sortKey: String
    private var statusKey: String
    private var onlyUnread: Bool
    private var onlyDownloaded: Bool

    private let background = UIControl()
    private let panel = UIView()
    private let scroll = UIScrollView()
    private let stack = UIStackView()
    private let footer = UIView()
    private let unreadSwitch = UISwitch()
    private let downloadedSwitch = UISwitch()
    private var categoryButtons: [String: UIButton] = [:]
    private var sortButtons: [String: UIButton] = [:]
    private var statusButtons: [String: UIButton] = [:]

    init(
        categories: [CategoryRecord],
        selectedCategoryID: Int64?,
        sortKey: String,
        statusKey: String,
        onlyUnread: Bool,
        onlyDownloaded: Bool
    ) {
        self.categories = categories
        self.categoryID = selectedCategoryID
        self.sortKey = sortKey
        self.statusKey = statusKey
        self.onlyUnread = onlyUnread
        self.onlyDownloaded = onlyDownloaded
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        let palette = ThemeManager.shared.palette
        view.backgroundColor = .clear

        background.translatesAutoresizingMaskIntoConstraints = false
        background.backgroundColor = UIColor.black.withAlphaComponent(0.6)
        background.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        view.addSubview(background)

        panel.translatesAutoresizingMaskIntoConstraints = false
        panel.backgroundColor = palette.background
        panel.layer.cornerRadius = 22
        panel.layer.masksToBounds = true
        view.addSubview(panel)

        let width = panel.widthAnchor.constraint(equalToConstant: 560)
        width.priority = UILayoutPriority(750)
        NSLayoutConstraint.activate([
            background.topAnchor.constraint(equalTo: view.topAnchor),
            background.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            background.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            background.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            panel.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            panel.widthAnchor.constraint(lessThanOrEqualTo: view.widthAnchor),
            panel.widthAnchor.constraint(lessThanOrEqualToConstant: 560),
            width,
            panel.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            panel.heightAnchor.constraint(equalTo: view.heightAnchor, multiplier: 0.88)
        ])

        let heading = UILabel()
        heading.translatesAutoresizingMaskIntoConstraints = false
        heading.text = "Organizar Biblioteca"
        heading.font = UIFont.systemFont(ofSize: 22, weight: .bold)
        heading.textColor = palette.primaryText
        panel.addSubview(heading)

        let close = UIButton(type: .system)
        close.translatesAutoresizingMaskIntoConstraints = false
        close.setTitle("✕", for: .normal)
        close.setTitleColor(palette.secondaryText, for: .normal)
        close.titleLabel?.font = UIFont.systemFont(ofSize: 18, weight: .medium)
        close.accessibilityLabel = "Fechar filtros"
        close.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        panel.addSubview(close)

        scroll.translatesAutoresizingMaskIntoConstraints = false
        scroll.alwaysBounceVertical = true
        panel.addSubview(scroll)

        stack.translatesAutoresizingMaskIntoConstraints = false
        stack.axis = .vertical
        stack.alignment = .fill
        stack.spacing = 12
        scroll.addSubview(stack)

        footer.translatesAutoresizingMaskIntoConstraints = false
        footer.backgroundColor = palette.barBackground
        panel.addSubview(footer)

        NSLayoutConstraint.activate([
            heading.topAnchor.constraint(equalTo: panel.topAnchor, constant: 18),
            heading.leadingAnchor.constraint(equalTo: panel.leadingAnchor, constant: 18),
            heading.trailingAnchor.constraint(lessThanOrEqualTo: close.leadingAnchor, constant: -8),
            close.topAnchor.constraint(equalTo: panel.topAnchor, constant: 10),
            close.trailingAnchor.constraint(equalTo: panel.trailingAnchor, constant: -15),
            close.widthAnchor.constraint(equalToConstant: 44),
            close.heightAnchor.constraint(equalToConstant: 44),
            scroll.topAnchor.constraint(equalTo: panel.topAnchor, constant: 64),
            scroll.leadingAnchor.constraint(equalTo: panel.leadingAnchor),
            scroll.trailingAnchor.constraint(equalTo: panel.trailingAnchor),
            scroll.bottomAnchor.constraint(equalTo: footer.topAnchor),
            stack.topAnchor.constraint(equalTo: scroll.topAnchor, constant: 12),
            stack.leadingAnchor.constraint(equalTo: scroll.leadingAnchor, constant: 18),
            stack.trailingAnchor.constraint(equalTo: scroll.trailingAnchor, constant: -18),
            stack.bottomAnchor.constraint(equalTo: scroll.bottomAnchor, constant: -20),
            stack.widthAnchor.constraint(equalTo: scroll.widthAnchor, constant: -36),
            footer.leadingAnchor.constraint(equalTo: panel.leadingAnchor),
            footer.trailingAnchor.constraint(equalTo: panel.trailingAnchor),
            footer.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
            footer.heightAnchor.constraint(equalToConstant: 74)
        ])

        addChips(
            title: "ORDENAR",
            options: [
                ("added", "Adicionados recentemente"),
                ("title-az", "Título A–Z"),
                ("title-za", "Título Z–A"),
                ("last-read", "Última leitura"),
                ("unread", "Mais não lidos")
            ],
            prefix: "sort",
            buttons: &sortButtons
        )
        addChips(
            title: "STATUS",
            options: [
                ("all", "Todos"),
                ("ongoing", "Em andamento"),
                ("completed", "Concluídos"),
                ("hiatus", "Pausados"),
                ("cancelled", "Cancelados"),
                ("unknown", "Desconhecido")
            ],
            prefix: "status",
            buttons: &statusButtons
        )

        var categoryOptions: [(String, String)] = [("all", "Todas as categorias")]
        for category in categories {
            categoryOptions.append((String(category.internalID), category.name))
        }
        addChips(
            title: "CATEGORIAS",
            options: categoryOptions,
            prefix: "category",
            buttons: &categoryButtons
        )

        addSwitch(
            label: "Somente obras com capítulos não lidos",
            target: unreadSwitch, enabled: onlyUnread,
            action: #selector(unreadChanged)
        )
        addSwitch(
            label: "Somente obras com downloads concluídos",
            target: downloadedSwitch, enabled: onlyDownloaded,
            action: #selector(downloadedChanged)
        )
        let explanation = UILabel()
        explanation.numberOfLines = 0
        explanation.font = UIFont.systemFont(ofSize: 12)
        explanation.textColor = palette.secondaryText
        explanation.text = "Os filtros são locais e funcionam offline. " +
            "Não lidos considera apenas capítulos que já foram registrados no aplicativo. " +
            "Downloaded significa capítulo com download concluído."
        stack.addArrangedSubview(explanation)
        createFooter()
        refreshButtons()
    }

    // Buttons are two per row for comfortable use on small iOS 12 screens.
    private func addChips(
        title: String, options: [(String, String)],
        prefix: String, buttons: inout [String: UIButton]
    ) {
        let caption = UILabel()
        caption.font = UIFont.systemFont(ofSize: 11, weight: .bold)
        caption.textColor = ThemeManager.shared.palette.secondaryText
        caption.text = title
        stack.addArrangedSubview(caption)

        for start in stride(from: 0, to: options.count, by: 2) {
            let row = UIStackView()
            row.axis = .horizontal
            row.spacing = 8
            row.distribution = .fillEqually
            for index in start..<min(start + 2, options.count) {
                let choice = options[index]
                let button = UIButton(type: .system)
                button.setTitle(choice.1, for: .normal)
                button.titleLabel?.font = UIFont.systemFont(ofSize: 13, weight: .medium)
                button.titleLabel?.numberOfLines = 2
                button.titleLabel?.textAlignment = .center
                button.layer.cornerRadius = 12
                button.layer.borderWidth = 1
                button.contentEdgeInsets = UIEdgeInsets(
                    top: 8, left: 6, bottom: 8, right: 6
                )
                button.heightAnchor.constraint(greaterThanOrEqualToConstant: 42).isActive = true
                button.accessibilityIdentifier = prefix + "." + choice.0
                button.addTarget(self, action: #selector(chipTapped(_:)), for: .touchUpInside)
                buttons[choice.0] = button
                row.addArrangedSubview(button)
            }
            if options.count - start == 1 {
                row.addArrangedSubview(UIView())
            }
            stack.addArrangedSubview(row)
        }
    }

    private func addSwitch(
        label: String, target: UISwitch, enabled: Bool, action: Selector
    ) {
        let row = UIStackView()
        row.axis = .horizontal
        row.alignment = .center
        row.spacing = 12
        let title = UILabel()
        title.text = label
        title.textColor = ThemeManager.shared.palette.primaryText
        title.font = UIFont.systemFont(ofSize: 14)
        title.numberOfLines = 2
        row.addArrangedSubview(title)
        target.isOn = enabled
        target.onTintColor = ThemeManager.shared.palette.accent
        target.addTarget(self, action: action, for: .valueChanged)
        row.addArrangedSubview(target)
        stack.addArrangedSubview(row)
    }

    private func createFooter() {
        let clear = UIButton(type: .system)
        clear.translatesAutoresizingMaskIntoConstraints = false
        clear.setTitle("Limpar", for: .normal)
        clear.setTitleColor(ThemeManager.shared.palette.primaryText, for: .normal)
        clear.backgroundColor = ThemeManager.shared.palette.secondaryBackground
        clear.layer.cornerRadius = 12
        clear.titleLabel?.font = UIFont.systemFont(ofSize: 14, weight: .semibold)
        clear.addTarget(self, action: #selector(clearTapped), for: .touchUpInside)

        let apply = UIButton(type: .system)
        apply.translatesAutoresizingMaskIntoConstraints = false
        apply.setTitle("Aplicar", for: .normal)
        apply.setTitleColor(.white, for: .normal)
        apply.backgroundColor = ThemeManager.shared.palette.accent
        apply.titleLabel?.font = UIFont.systemFont(ofSize: 15, weight: .semibold)
        apply.layer.cornerRadius = 12
        apply.addTarget(self, action: #selector(applyTapped), for: .touchUpInside)

        footer.addSubview(clear)
        footer.addSubview(apply)
        NSLayoutConstraint.activate([
            clear.leadingAnchor.constraint(equalTo: footer.leadingAnchor, constant: 18),
            clear.topAnchor.constraint(equalTo: footer.topAnchor, constant: 10),
            clear.bottomAnchor.constraint(equalTo: footer.bottomAnchor, constant: -10),
            clear.widthAnchor.constraint(equalToConstant: 92),
            apply.leadingAnchor.constraint(equalTo: clear.trailingAnchor, constant: 10),
            apply.trailingAnchor.constraint(equalTo: footer.trailingAnchor, constant: -18),
            apply.topAnchor.constraint(equalTo: clear.topAnchor),
            apply.bottomAnchor.constraint(equalTo: clear.bottomAnchor)
        ])
    }

    private func refreshButtons() {
        let palette = ThemeManager.shared.palette
        func tint(_ buttons: [String: UIButton], active: String) {
            for (id, button) in buttons {
                let selected = id == active
                button.backgroundColor = selected
                    ? palette.accent.withAlphaComponent(0.17)
                    : palette.secondaryBackground
                button.layer.borderColor = (selected ? palette.accent : palette.separator).cgColor
                button.setTitleColor(
                    selected ? palette.accent : palette.primaryText, for: .normal
                )
            }
        }
        tint(sortButtons, active: sortKey)
        tint(statusButtons, active: statusKey)
        tint(categoryButtons, active: categoryID.map(String.init) ?? "all")
    }

    @objc private func chipTapped(_ sender: UIButton) {
        guard let key = sender.accessibilityIdentifier else { return }
        if key.hasPrefix("sort.") {
            sortKey = String(key.dropFirst(5))
        } else if key.hasPrefix("status.") {
            statusKey = String(key.dropFirst(7))
        } else if key.hasPrefix("category.") {
            let id = String(key.dropFirst(9))
            categoryID = id == "all" ? nil : Int64(id)
        }
        refreshButtons()
    }

    @objc private func unreadChanged() {
        onlyUnread = unreadSwitch.isOn
    }

    @objc private func downloadedChanged() {
        onlyDownloaded = downloadedSwitch.isOn
    }

    @objc private func clearTapped() {
        categoryID = nil
        sortKey = "added"
        statusKey = "all"
        onlyUnread = false
        onlyDownloaded = false
        unreadSwitch.isOn = false
        downloadedSwitch.isOn = false
        refreshButtons()
        scroll.setContentOffset(.zero, animated: true)
    }

    @objc private func closeTapped() {
        dismiss(animated: true)
    }

    @objc private func applyTapped() {
        let apply = onApply
        dismiss(animated: true) {
            apply?(
                self.categoryID, self.sortKey, self.statusKey,
                self.onlyUnread, self.onlyDownloaded
            )
        }
    }
}

