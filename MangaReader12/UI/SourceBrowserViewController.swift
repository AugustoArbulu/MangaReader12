import UIKit

final class SourceBrowserViewController: UITableViewController, UISearchBarDelegate {
    private let sourceRecord: InstalledSourceRecord
    private var runtime: JavaScriptSourceRuntime?
    private var items: [SourceMangaSummary] = []
    private var excludedTags: Set<String> = []
    private var hideUnclassified = false

    private var displayedItems: [SourceMangaSummary] {
        guard !excludedTags.isEmpty else { return items }
        return items.filter { item in
            guard let tags = item.tags, !tags.isEmpty else {
                return !hideUnclassified
            }
            return !tags.contains { label in
                excludedTags.contains { SourceTagMatcher.matches(label, exclusion: $0) }
            }
        }
    }
    private var currentPage = 1
    private var hasNextPage = false
    private var loading = false
    private var currentQuery: String?
    private var browseCategories: [SourceBrowseCategory] = []
    private var selectedCategory: SourceBrowseCategory?
    // A category can change while the previous asynchronous source request
    // is running. Ignore old responses and execute the newest request.
    private var requestEpoch = 0
    private var pendingReload = false
    private let browseHeader = UIView()
    private let browseHeaderButton = UIButton(type: .system)
    private let browseHeaderHint = UILabel()
    private var coverDiagnostic: WebtoonsCoverDiagnostic?

    private lazy var sourceSearchController: UISearchController = {
        let controller = UISearchController(searchResultsController: nil)
        controller.obscuresBackgroundDuringPresentation = false
        controller.searchBar.placeholder = "Buscar nesta source"
        controller.searchBar.delegate = self
        return controller
    }()

    init(sourceRecord: InstalledSourceRecord) {
        self.sourceRecord = sourceRecord
        let key = "explore.filters." + sourceRecord.manifest.id
        self.excludedTags = Set(UserDefaults.standard.stringArray(forKey: key) ?? [])
        self.hideUnclassified = UserDefaults.standard.bool(forKey: key + ".hideUnknown")
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = sourceRecord.manifest.name
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 100
        tableView.register(
            MangaCoverCell.self,
            forCellReuseIdentifier: MangaCoverCell.reuseIdentifier
        )
        navigationItem.searchController = sourceSearchController
        navigationItem.hidesSearchBarWhenScrolling = false
        definesPresentationContext = true
        configureBrowseHeader()
        applyTheme()

        if sourceRecord.manifest.id == "kei.webtoons.en" {
            navigationItem.rightBarButtonItem = UIBarButtonItem(
                title: "Testar capas",
                style: .plain,
                target: self,
                action: #selector(diagnoseCoverTapped)
            )
        }

        refreshControl = UIRefreshControl()
        refreshControl?.addTarget(
            self,
            action: #selector(refreshPulled),
            for: .valueChanged
        )

        loadRuntime()
    }

    // A small, explicit source-backed discovery menu. Empty categories
    // mean a legacy API v1 adapter; Popular and search continue to work.
    private func configureBrowseHeader() {
        browseHeader.frame = CGRect(
            x: 0, y: 0, width: tableView.bounds.width, height: 68
        )
        browseHeader.autoresizingMask = [.flexibleWidth]

        browseHeaderButton.frame = CGRect(
            x: 16, y: 6, width: max(1, tableView.bounds.width - 32), height: 36
        )
        browseHeaderButton.autoresizingMask = [.flexibleWidth]
        browseHeaderButton.contentHorizontalAlignment = .left
        browseHeaderButton.titleLabel?.font = UIFont.systemFont(
            ofSize: 16, weight: .semibold
        )
        browseHeaderButton.addTarget(
            self, action: #selector(showBrowseMenu), for: .touchUpInside
        )
        browseHeader.addSubview(browseHeaderButton)

        browseHeaderHint.frame = CGRect(
            x: 16, y: 41, width: max(1, tableView.bounds.width - 32), height: 19
        )
        browseHeaderHint.autoresizingMask = [.flexibleWidth]
        browseHeaderHint.font = UIFont.systemFont(ofSize: 12)
        browseHeaderHint.textColor = .gray
        browseHeader.addSubview(browseHeaderHint)
        tableView.tableHeaderView = browseHeader
        updateBrowseHeader()
    }

    private func updateBrowseHeader() {
        let title = currentQuery != nil
            ? "Busca por título"
            : (selectedCategory?.title ?? "Populares")
        let active = excludedTags.count
        browseHeaderButton.setTitle(
            "Explorar: " + title + (active > 0 ? "   • " + String(active) + " exclusões" : "") + "  ▾",
            for: .normal
        )

        if let category = selectedCategory {
            browseHeaderHint.text = category.kind == "genre"
                ? "Gênero da fonte • resultados do site"
                : (category.kind == "latest"
                    ? "Atualizações recentes da fonte"
                    : "Ranking da fonte")
        } else {
            browseHeaderHint.text = currentQuery != nil
                ? "Resultados da busca nesta fonte"
                : "Toque para escolher seção, gênero e exclusões"
        }
    }

    private func loadBrowseCategories() {
        guard let runtime = runtime else { return }
        runtime.callDecoded(
            "browseCategories",
            as: [SourceBrowseCategory].self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                switch result {
                case .success(let candidates):
                    var seen = Set<String>()
                    self.browseCategories = Array(candidates.prefix(32))
                        .filter { category in
                            category.isValid &&
                            category.id != "popular" &&
                            seen.insert(category.id).inserted
                        }
                        .prefix(24)
                        .map { $0 }
                case .failure:
                    // Missing optional function on old source scripts is fine.
                    self.browseCategories = []
                }
                self.updateBrowseHeader()
            }
        }
    }

    @objc private func showBrowseMenu() {
        let controller = SourceDiscoverySheetViewController(
            categories: browseCategories,
            selectedID: selectedCategory?.id,
            exclusions: excludedTags,
            hideUnknown: hideUnclassified
        )
        controller.onApply = { [weak self] selectedID, exclusions, hideUnknown in
            guard let self = self else { return }
            let previousID = self.selectedCategory?.id
            let wasSearching = self.currentQuery != nil
            self.selectedCategory = self.browseCategories.first { $0.id == selectedID }
            self.excludedTags = exclusions
            self.hideUnclassified = hideUnknown

            let key = "explore.filters." + self.sourceRecord.manifest.id
            UserDefaults.standard.set(exclusions.sorted(), forKey: key)
            UserDefaults.standard.set(hideUnknown, forKey: key + ".hideUnknown")
            self.updateBrowseHeader()

            if previousID != self.selectedCategory?.id || (wasSearching && selectedID != nil) {
                self.currentQuery = nil
                self.sourceSearchController.searchBar.text = nil
                self.sourceSearchController.searchBar.resignFirstResponder()
                self.loadFirstPage()
            } else {
                self.tableView.reloadData()
                self.updateEmptyState()
            }
        }
        controller.modalPresentationStyle = .overFullScreen
        controller.modalTransitionStyle = .crossDissolve
        present(controller, animated: true)
    }

    private func updateEmptyState() {
        guard !loading, displayedItems.isEmpty else {
            tableView.backgroundView = nil
            return
        }
        let label = UILabel()
        label.numberOfLines = 0
        label.textAlignment = .center
        label.font = UIFont.systemFont(ofSize: 14)
        label.textColor = ThemeManager.shared.palette.secondaryText
        label.text = excludedTags.isEmpty
            ? "Nenhuma obra encontrada nesta seção."
            : "Nenhuma obra corresponde aos filtros nesta lista.\nSe a fonte não informar tags, experimente permitir obras sem classificação."
        label.frame = tableView.bounds.insetBy(dx: 28, dy: 20)
        tableView.backgroundView = label
    }

    @objc private func diagnoseCoverTapped() {
        guard sourceRecord.manifest.id == "kei.webtoons.en",
              coverDiagnostic == nil else { return }
        guard let runtime = runtime, !items.isEmpty else {
            showMessage(
                title: "Diagnóstico de capas",
                message: "Abra Populares e carregue pelo menos uma obra antes do teste."
            )
            return
        }

        navigationItem.rightBarButtonItem?.isEnabled = false
        navigationItem.prompt = "Testando capas visíveis e os detalhes…"

        // Sample at most three currently visible rows so the user can scroll
        // to a failed cover before explicitly running this bounded test.
        let shown = displayedItems
        let visible = (tableView.indexPathsForVisibleRows ?? [])
            .filter { $0.section == 0 && $0.row < shown.count }
            .sorted { $0.row < $1.row }
            .prefix(3)
            .map { shown[$0.row] }
        let samples = visible.isEmpty ? Array(shown.prefix(3)) : visible
        startCoverDiagnostic(samples: samples, chosenDirectly: false)
    }

    private func startCoverDiagnostic(
        samples: [SourceMangaSummary],
        chosenDirectly: Bool
    ) {
        guard sourceRecord.manifest.id == "kei.webtoons.en",
              let runtime = runtime, coverDiagnostic == nil,
              !samples.isEmpty else { return }

        navigationItem.rightBarButtonItem?.isEnabled = false
        navigationItem.prompt = chosenDirectly
            ? "Diagnosticando a capa selecionada…"
            : "Testando capas visíveis e os detalhes…"

        let diagnostic = WebtoonsCoverDiagnostic(
            summaries: samples,
            runtime: runtime,
            allowedDomains: sourceRecord.manifest.domains,
            inspectSource: chosenDirectly
        )
        coverDiagnostic = diagnostic
        diagnostic.run { [weak self] report in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.coverDiagnostic = nil
                self.navigationItem.rightBarButtonItem?.isEnabled = true
                self.navigationItem.prompt = nil

                let alert = UIAlertController(
                    title: "Diagnóstico de capas",
                    message: report,
                    preferredStyle: .alert
                )
                alert.addAction(UIAlertAction(
                    title: "Copiar relatório",
                    style: .default
                ) { _ in
                    UIPasteboard.general.string = report
                })
                alert.addAction(UIAlertAction(title: "Fechar", style: .cancel))
                self.present(alert, animated: true)
            }
        }
    }

    @objc private func refreshPulled() {
        loadFirstPage()
    }

    private func loadRuntime() {
        guard sourceRecord.enabled else {
            showMessage(
                title: "Source desativada",
                message: "Ative essa source em Explorar antes de abri-la."
            )
            return
        }

        loading = true
        navigationItem.prompt = "Carregando source…"

        do {
            let loader = try InstalledSourceRuntimeLoader.defaultLoader()
            loader.load(sourceID: sourceRecord.manifest.id) { [weak self] result in
                DispatchQueue.main.async {
                    guard let self = self else { return }

                    switch result {
                    case .success(let runtime):
                        self.runtime = runtime
                        self.loading = false
                        self.navigationItem.prompt = nil
                        self.loadBrowseCategories()
                        self.loadFirstPage()

                    case .failure(let error):
                        self.loading = false
                        self.navigationItem.prompt = nil
                        self.refreshControl?.endRefreshing()
                        self.showError(error)
                    }
                }
            }
        } catch {
            loading = false
            navigationItem.prompt = nil
            refreshControl?.endRefreshing()
            showError(error)
        }
    }

    private func loadFirstPage() {
        guard runtime != nil else {
            refreshControl?.endRefreshing()
            return
        }
        requestEpoch += 1
        currentPage = 1
        items = []
        hasNextPage = false
        tableView.reloadData()
        updateEmptyState()
        if loading {
            pendingReload = true
        } else {
            loadPage(1)
        }
    }

    private func loadPage(_ page: Int) {
        guard let runtime = runtime, !loading else {
            refreshControl?.endRefreshing()
            return
        }

        let epoch = requestEpoch
        let query = currentQuery
        let category = selectedCategory
        loading = true
        navigationItem.prompt = query != nil ? "Buscando…" :
            (category?.kind == "genre" ? "Filtrando gênero…" :
                (category?.kind == "latest" ? "Carregando recentes…" :
                    "Carregando listagem…"))

        let completion: (Result<SourcePagedMangaResult, Error>) -> Void = {
            [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.loading = false
                self.navigationItem.prompt = nil
                self.refreshControl?.endRefreshing()

                // Never allow an in-flight response for a previous category,
                // query or pagination sequence to overwrite the current UI.
                if epoch != self.requestEpoch || self.pendingReload {
                    self.pendingReload = false
                    self.loadPage(1)
                    return
                }

                switch result {
                case .success(let pageResult):
                    if page == 1 {
                        self.items = pageResult.items
                    } else {
                        let known = Set(self.items.map { $0.id })
                        var seen = known
                        self.items.append(contentsOf: pageResult.items.filter {
                            seen.insert($0.id).inserted
                        })
                    }

                    self.currentPage = page
                    self.hasNextPage = pageResult.hasNextPage
                    self.tableView.reloadData()
                    self.updateEmptyState()

                case .failure(let error):
                    self.showError(error)
                }
            }
        }

        if let query = query, !query.isEmpty {
            runtime.callDecoded(
                "search",
                arguments: [query, page, [] as [Any]],
                as: SourcePagedMangaResult.self,
                completion: completion
            )
        } else if let category = category {
            runtime.callDecoded(
                "browse",
                arguments: [category.id, page],
                as: SourcePagedMangaResult.self,
                completion: completion
            )
        } else {
            runtime.callDecoded(
                "popular",
                arguments: [page],
                as: SourcePagedMangaResult.self,
                completion: completion
            )
        }
    }

    func searchBarSearchButtonClicked(_ searchBar: UISearchBar) {
        let query = (searchBar.text ?? "")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        currentQuery = query.isEmpty ? nil : query
        searchBar.resignFirstResponder()
        updateBrowseHeader()
        loadFirstPage()
    }

    func searchBarCancelButtonClicked(_ searchBar: UISearchBar) {
        currentQuery = nil
        updateBrowseHeader()
        loadFirstPage()
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return displayedItems.count
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

        let item = displayedItems[indexPath.row]
        cell.configure(
            title: item.title,
            subtitle: item.url ?? item.id,
            coverURL: item.cover,
            allowedDomains: sourceRecord.manifest.domains
        )
        cell.accessoryType = .disclosureIndicator
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        willDisplay cell: UITableViewCell,
        forRowAt indexPath: IndexPath
    ) {
        guard indexPath.row == displayedItems.count - 1,
              hasNextPage,
              !loading else {
            return
        }

        loadPage(currentPage + 1)
    }

    override func tableView(
        _ tableView: UITableView,
        editActionsForRowAt indexPath: IndexPath
    ) -> [UITableViewRowAction]? {
        guard sourceRecord.manifest.id == "kei.webtoons.en",
              indexPath.section == 0, indexPath.row < displayedItems.count else {
            return nil
        }
        let action = UITableViewRowAction(style: .normal, title: "Testar capa") {
            [weak self] _, selected in
            guard let self = self, selected.row < self.displayedItems.count else {
                return
            }
            // Explicit swipe action selects the exact requested manga.
            self.startCoverDiagnostic(
                samples: [self.displayedItems[selected.row]],
                chosenDirectly: true
            )
        }
        return [action]
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        guard let runtime = runtime else { return }

        navigationController?.pushViewController(
            MangaDetailsViewController(
                sourceRecord: sourceRecord,
                runtime: runtime,
                summary: displayedItems[indexPath.row]
            ),
            animated: true
        )
    }

    private func showError(_ error: Error) {
        showMessage(title: "Erro da source", message: error.localizedDescription)
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

// Content exclusions use only a source-provided classification label. Titles,
// covers, URL slugs, character names, and images are never used to infer genre.
private enum SourceTagMatcher {
    static func matches(_ tag: String, exclusion: String) -> Bool {
        let normalized = tag.folding(
            options: [.diacriticInsensitive, .caseInsensitive],
            locale: Locale(identifier: "en_US_POSIX")
        )
        .lowercased()
        .replacingOccurrences(
            of: "[^a-z0-9]+", with: " ", options: .regularExpression
        )
        .trimmingCharacters(in: .whitespacesAndNewlines)

        switch exclusion {
        case "bl":
            return ["bl", "boys love", "boy s love", "yaoi", "shounen ai",
                    "shonen ai"].contains(normalized)
        case "gl":
            return ["gl", "girls love", "girl s love", "yuri", "shoujo ai",
                    "shojo ai"].contains(normalized)
        case "lgbtq":
            return ["lgbt", "lgbtq", "lgbtqia", "lgbtqia plus", "queer"]
                .contains(normalized)
        case "harem":
            return ["harem", "reverse harem", "harém"].contains(normalized)
        case "horror":
            return ["horror", "terror"].contains(normalized)
        default:
            return false
        }
    }
}

// A custom iOS 12 UIKit bottom sheet replaces UIAlertController actionSheet.
// It is full-screen dimmed even on iPad, and its content is vertically scrollable
// on older 4-inch devices. Categories come solely from optional source metadata.
private final class SourceDiscoverySheetViewController: UIViewController {
    typealias FilterCallback = (String?, Set<String>, Bool) -> Void
    var onApply: FilterCallback?

    private let categories: [SourceBrowseCategory]
    private var selectedID: String?
    private var exclusions: Set<String>
    private var hideUnknown: Bool

    private let backdrop = UIControl()
    private let sheet = UIView()
    private let scroller = UIScrollView()
    private let content = UIStackView()
    private let footer = UIView()
    private let infoLabel = UILabel()
    private let unknownToggle = UISwitch()
    private var categoryChips: [String: UIButton] = [:]
    private var exclusionChips: [String: UIButton] = [:]

    private let exclusionChoices: [(id: String, label: String)] = [
        ("bl", "BL (Boys' Love)"),
        ("gl", "GL (Girls' Love)"),
        ("lgbtq", "LGBTQ+"),
        ("harem", "Harém"),
        ("horror", "Terror")
    ]

    init(
        categories: [SourceBrowseCategory],
        selectedID: String?,
        exclusions: Set<String>,
        hideUnknown: Bool
    ) {
        self.categories = categories
        self.selectedID = selectedID
        self.exclusions = exclusions
        self.hideUnknown = hideUnknown
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        let palette = ThemeManager.shared.palette
        view.backgroundColor = .clear

        backdrop.translatesAutoresizingMaskIntoConstraints = false
        backdrop.backgroundColor = UIColor.black.withAlphaComponent(0.62)
        backdrop.addTarget(
            self, action: #selector(closeTapped), for: .touchUpInside
        )
        view.addSubview(backdrop)

        sheet.translatesAutoresizingMaskIntoConstraints = false
        sheet.backgroundColor = palette.background
        sheet.layer.cornerRadius = 22
        sheet.layer.masksToBounds = true
        view.addSubview(sheet)

        let preferredWidth = sheet.widthAnchor.constraint(equalToConstant: 560)
        preferredWidth.priority = UILayoutPriority(750)
        NSLayoutConstraint.activate([
            backdrop.topAnchor.constraint(equalTo: view.topAnchor),
            backdrop.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            backdrop.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            backdrop.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            sheet.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            sheet.widthAnchor.constraint(lessThanOrEqualTo: view.widthAnchor),
            sheet.widthAnchor.constraint(lessThanOrEqualToConstant: 560),
            preferredWidth,
            sheet.bottomAnchor.constraint(equalTo: view.bottomAnchor),
            sheet.heightAnchor.constraint(equalTo: view.heightAnchor, multiplier: 0.88)
        ])

        let heading = UILabel()
        heading.translatesAutoresizingMaskIntoConstraints = false
        heading.text = "Explorar"
        heading.font = UIFont.systemFont(ofSize: 23, weight: .bold)
        heading.textColor = palette.primaryText
        sheet.addSubview(heading)

        let close = UIButton(type: .system)
        close.translatesAutoresizingMaskIntoConstraints = false
        close.setTitle("✕", for: .normal)
        close.setTitleColor(palette.secondaryText, for: .normal)
        close.titleLabel?.font = UIFont.systemFont(ofSize: 19, weight: .medium)
        close.accessibilityLabel = "Fechar filtros"
        close.addTarget(self, action: #selector(closeTapped), for: .touchUpInside)
        sheet.addSubview(close)

        scroller.translatesAutoresizingMaskIntoConstraints = false
        scroller.alwaysBounceVertical = true
        scroller.showsVerticalScrollIndicator = true
        scroller.keyboardDismissMode = .onDrag
        sheet.addSubview(scroller)

        content.translatesAutoresizingMaskIntoConstraints = false
        content.axis = .vertical
        content.spacing = 14
        content.alignment = .fill
        scroller.addSubview(content)

        footer.translatesAutoresizingMaskIntoConstraints = false
        footer.backgroundColor = palette.barBackground
        sheet.addSubview(footer)

        NSLayoutConstraint.activate([
            heading.leadingAnchor.constraint(equalTo: sheet.leadingAnchor, constant: 22),
            heading.topAnchor.constraint(equalTo: sheet.topAnchor, constant: 19),
            heading.trailingAnchor.constraint(lessThanOrEqualTo: close.leadingAnchor, constant: -8),

            close.trailingAnchor.constraint(equalTo: sheet.trailingAnchor, constant: -17),
            close.topAnchor.constraint(equalTo: sheet.topAnchor, constant: 12),
            close.widthAnchor.constraint(equalToConstant: 44),
            close.heightAnchor.constraint(equalToConstant: 44),

            scroller.topAnchor.constraint(equalTo: sheet.topAnchor, constant: 65),
            scroller.leadingAnchor.constraint(equalTo: sheet.leadingAnchor),
            scroller.trailingAnchor.constraint(equalTo: sheet.trailingAnchor),
            scroller.bottomAnchor.constraint(equalTo: footer.topAnchor),

            content.topAnchor.constraint(equalTo: scroller.topAnchor, constant: 12),
            content.leadingAnchor.constraint(equalTo: scroller.leadingAnchor, constant: 18),
            content.trailingAnchor.constraint(equalTo: scroller.trailingAnchor, constant: -18),
            content.bottomAnchor.constraint(equalTo: scroller.bottomAnchor, constant: -22),
            content.widthAnchor.constraint(equalTo: scroller.widthAnchor, constant: -36),

            footer.leadingAnchor.constraint(equalTo: sheet.leadingAnchor),
            footer.trailingAnchor.constraint(equalTo: sheet.trailingAnchor),
            footer.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
            footer.heightAnchor.constraint(equalToConstant: 74)
        ])

        createSections()
        createFooter()
        refreshSelections()
    }

    private func createSections() {
        let rankings = categories.filter { $0.kind != "genre" }
        let genres = categories.filter { $0.kind == "genre" }
        let normal = SourceBrowseCategory(
            id: "popular", title: "Populares", kind: "ranking"
        )
        addSection(
            title: "DESCUBRA",
            subtitle: "Selecione uma lista da fonte.",
            choices: [(normal.id, normal.title)] +
                rankings.map { ($0.id, $0.id == "latest" ? "Recentes" : $0.title) },
            selection: .category
        )
        if !genres.isEmpty {
            addSection(
                title: "GÊNERO",
                subtitle: "Uma categoria remota por vez, conforme a fonte.",
                choices: genres.map { ($0.id, $0.title) },
                selection: .category
            )
        }

        addSection(
            title: "EXCLUIR TAGS",
            subtitle: "Oculta obras com tags explícitas correspondentes.",
            choices: exclusionChoices.map { ($0.id, $0.label) },
            selection: .exclusion
        )

        let unknownRow = UIStackView()
        unknownRow.axis = .horizontal
        unknownRow.alignment = .center
        unknownRow.spacing = 12
        let unknownLabel = UILabel()
        unknownLabel.text = "Ocultar obras sem tags"
        unknownLabel.font = UIFont.systemFont(ofSize: 14, weight: .medium)
        unknownLabel.textColor = ThemeManager.shared.palette.primaryText
        unknownLabel.numberOfLines = 2
        unknownRow.addArrangedSubview(unknownLabel)
        unknownToggle.onTintColor = ThemeManager.shared.palette.accent
        unknownToggle.addTarget(
            self, action: #selector(unknownChanged), for: .valueChanged
        )
        unknownRow.addArrangedSubview(unknownToggle)
        content.addArrangedSubview(unknownRow)

        infoLabel.numberOfLines = 0
        infoLabel.textColor = ThemeManager.shared.palette.secondaryText
        infoLabel.font = UIFont.systemFont(ofSize: 12)
        infoLabel.text = "Os filtros de exclusão usam apenas tags informadas na " +
            "listagem da fonte. A ausência de tags não comprova que a obra " +
            "não contém o tema excluído. Não analisamos títulos ou imagens."
        content.addArrangedSubview(infoLabel)
    }

    private enum ChoiceKind { case category, exclusion }

    private func addSection(
        title: String,
        subtitle: String,
        choices: [(String, String)],
        selection: ChoiceKind
    ) {
        let header = UILabel()
        header.text = title
        header.textColor = ThemeManager.shared.palette.secondaryText
        header.font = UIFont.systemFont(ofSize: 11, weight: .bold)
        content.addArrangedSubview(header)

        let detail = UILabel()
        detail.text = subtitle
        detail.numberOfLines = 0
        detail.textColor = ThemeManager.shared.palette.secondaryText
        detail.font = UIFont.systemFont(ofSize: 12)
        content.addArrangedSubview(detail)

        for start in stride(from: 0, to: choices.count, by: 2) {
            let row = UIStackView()
            row.axis = .horizontal
            row.spacing = 8
            row.distribution = .fillEqually
            let end = min(start + 2, choices.count)
            for index in start..<end {
                let choice = choices[index]
                let button = UIButton(type: .system)
                button.setTitle(choice.1, for: .normal)
                button.titleLabel?.font = UIFont.systemFont(ofSize: 13, weight: .medium)
                button.titleLabel?.numberOfLines = 2
                button.titleLabel?.textAlignment = .center
                button.layer.cornerRadius = 12
                button.layer.borderWidth = 1
                button.contentEdgeInsets = UIEdgeInsets(
                    top: 7, left: 7, bottom: 7, right: 7
                )
                button.heightAnchor.constraint(greaterThanOrEqualToConstant: 40).isActive = true
                button.accessibilityIdentifier =
                    (selection == .category ? "discover.category." : "discover.exclude.") + choice.0
                if selection == .category {
                    categoryChips[choice.0] = button
                    button.addTarget(
                        self, action: #selector(categoryTapped(_:)), for: .touchUpInside
                    )
                } else {
                    exclusionChips[choice.0] = button
                    button.addTarget(
                        self, action: #selector(exclusionTapped(_:)), for: .touchUpInside
                    )
                }
                row.addArrangedSubview(button)
            }
            if end == start + 1 {
                row.addArrangedSubview(UIView())
            }
            content.addArrangedSubview(row)
        }
    }

    private func createFooter() {
        let clear = UIButton(type: .system)
        clear.translatesAutoresizingMaskIntoConstraints = false
        clear.setTitle("Limpar", for: .normal)
        clear.setTitleColor(ThemeManager.shared.palette.primaryText, for: .normal)
        clear.titleLabel?.font = UIFont.systemFont(ofSize: 14, weight: .semibold)
        clear.backgroundColor = ThemeManager.shared.palette.secondaryBackground
        clear.layer.cornerRadius = 12
        clear.addTarget(self, action: #selector(clearTapped), for: .touchUpInside)

        let apply = UIButton(type: .system)
        apply.translatesAutoresizingMaskIntoConstraints = false
        apply.setTitle("Aplicar filtros", for: .normal)
        apply.setTitleColor(.white, for: .normal)
        apply.titleLabel?.font = UIFont.systemFont(ofSize: 15, weight: .semibold)
        apply.backgroundColor = ThemeManager.shared.palette.accent
        apply.layer.cornerRadius = 12
        apply.addTarget(self, action: #selector(applyTapped), for: .touchUpInside)

        footer.addSubview(clear)
        footer.addSubview(apply)
        NSLayoutConstraint.activate([
            clear.leadingAnchor.constraint(equalTo: footer.leadingAnchor, constant: 18),
            clear.topAnchor.constraint(equalTo: footer.topAnchor, constant: 10),
            clear.bottomAnchor.constraint(equalTo: footer.bottomAnchor, constant: -10),
            clear.widthAnchor.constraint(equalToConstant: 94),

            apply.leadingAnchor.constraint(equalTo: clear.trailingAnchor, constant: 10),
            apply.trailingAnchor.constraint(equalTo: footer.trailingAnchor, constant: -18),
            apply.topAnchor.constraint(equalTo: clear.topAnchor),
            apply.bottomAnchor.constraint(equalTo: clear.bottomAnchor)
        ])
    }

    private func refreshSelections() {
        let palette = ThemeManager.shared.palette
        for (key, button) in categoryChips {
            let selected = key == (selectedID ?? "popular")
            button.backgroundColor = selected
                ? palette.accent.withAlphaComponent(0.17)
                : palette.secondaryBackground
            button.layer.borderColor = (selected ? palette.accent : palette.separator).cgColor
            button.setTitleColor(
                selected ? palette.accent : palette.primaryText, for: .normal
            )
        }
        for (key, button) in exclusionChips {
            let selected = exclusions.contains(key)
            button.backgroundColor = selected
                ? palette.accent.withAlphaComponent(0.17)
                : palette.secondaryBackground
            button.layer.borderColor = (selected ? palette.accent : palette.separator).cgColor
            button.setTitleColor(
                selected ? palette.accent : palette.primaryText, for: .normal
            )
        }
        unknownToggle.isOn = hideUnknown
        unknownToggle.isEnabled = !exclusions.isEmpty
    }

    @objc private func categoryTapped(_ button: UIButton) {
        guard let key = button.accessibilityIdentifier?
            .replacingOccurrences(of: "discover.category.", with: "") else { return }
        selectedID = key == "popular" ? nil : key
        refreshSelections()
    }

    @objc private func exclusionTapped(_ button: UIButton) {
        guard let key = button.accessibilityIdentifier?
            .replacingOccurrences(of: "discover.exclude.", with: "") else { return }
        if exclusions.contains(key) {
            exclusions.remove(key)
        } else {
            exclusions.insert(key)
        }
        refreshSelections()
    }

    @objc private func unknownChanged() {
        hideUnknown = unknownToggle.isOn
    }

    @objc private func clearTapped() {
        selectedID = nil
        exclusions.removeAll()
        hideUnknown = false
        refreshSelections()
        scroller.setContentOffset(.zero, animated: true)
    }

    @objc private func closeTapped() {
        dismiss(animated: true)
    }

    @objc private func applyTapped() {
        let callback = onApply
        dismiss(animated: true) {
            callback?(self.selectedID, self.exclusions, self.hideUnknown)
        }
    }
}

// An explicitly initiated, bounded cover probe. It tests at most three
// visible thumbnails, one regular details() call, and one details cover GET,
// all sequentially; stop on HTTP 429. No automated retries,
// cross-host exceptions, certificate overrides or background monitoring.
//
// URLs may contain tokens or reveal the manga title. The copied report
// includes only the host and safe format metadata, never URL path/query,
// authentication headers, HTML, cookies or response body.
private struct WebtoonsDetailsCoverTrace: Decodable {
    let matched: Bool
    let metaPresent: Bool
    let contentPresent: Bool
    let contentClass: String
    let resolvedFound: Bool
    let resolvedClass: String
}

private final class WebtoonsCoverDiagnostic {
    private let summaries: [SourceMangaSummary]
    private let inspectSource: Bool
    private let runtime: JavaScriptSourceRuntime
    private let domains: [String]
    private var client: HTTPClient?
    private var lines: [String] = []
    private var finishCallback: ((String) -> Void)?

    init(
        summaries: [SourceMangaSummary],
        runtime: JavaScriptSourceRuntime,
        allowedDomains: [String],
        inspectSource: Bool = false
    ) {
        self.summaries = Array(summaries.prefix(3))
        self.inspectSource = inspectSource
        self.runtime = runtime
        self.domains = allowedDomains
    }

    func run(_ completion: @escaping (String) -> Void) {
        finishCallback = completion
        lines = [
            "iOS: " + UIDevice.current.systemVersion,
            "App: " + (Bundle.main.object(forInfoDictionaryKey: "CFBundleVersion") as? String ?? "?"),
            "Fonte: Webtoons.com EN",
            inspectSource
                ? "Amostra: 1 capa escolhida pelo usuário (sem título no relatório)"
                : "Amostras: até 3 capas visíveis (sem títulos no relatório)",
            "HTTPS padrão; sem login, bypass ou exceções de certificado",
            "Domínios permitidos: " + domains.joined(separator: ", ")
        ]
        if inspectSource, let selected = summaries.first {
            // Prefer metadata carried by the exact decoded row. The v0.1.4
            // legacy lookup by manga ID can refer to another ranking entry.
            if let snapshot = selected.coverDiagnostic {
                lines.append("Origem do diagnóstico: ficha selecionada (snapshot)")
                appendObservation(snapshot)
                runImageProbes()
            } else {
                lines.append("Origem do diagnóstico: consulta por ID (legado; pode divergir)")
                runtime.callDecoded(
                    "inspectCover",
                    arguments: [selected.id],
                    as: SourceCoverObservation.self
                ) { [weak self] outcome in
                    guard let self = self else { return }
                    switch outcome {
                    case .success(let trace):
                        self.appendObservation(trace)
                    case .failure:
                        self.lines.append("Metadados indisponíveis. Atualize Webtoons EN para 0.1.5.")
                    }
                    self.runImageProbes()
                }
            }
        } else {
            runImageProbes()
        }
    }

    private func appendObservation(_ trace: SourceCoverObservation) {
        lines.append("Registro da ficha: " + (trace.matched ? "SIM" : "NÃO"))
        lines.append("URL reconhecida pelo adaptador: " + (trace.coverFound ? "SIM" : "NÃO"))
        lines.append("URL de saída JS: " + (trace.outputClass ?? "(indisponível)") +
            ", caracteres=" + (trace.outputLength.map { String($0) } ?? "?"))
        lines.append("Elementos encontrados: " +
            (trace.fields.isEmpty ? "(nenhum)" : trace.fields.joined(separator: ", ")))
        lines.append("Atributos presentes: " +
            (trace.attributes.isEmpty ? "(nenhum)" : trace.attributes.joined(separator: ", ")))
        lines.append("Tipos de valores: " +
            (trace.kinds.isEmpty ? "(nenhum)" : trace.kinds.joined(separator: ", ")))
        if let selected = summaries.first {
            let modelHasCover = selected.cover != nil && !(selected.cover?.isEmpty ?? true)
            lines.append("URL recebida no modelo Swift: " + (modelHasCover ? "SIM" : "NÃO"))
            lines.append("JS e Swift concordam na presença da URL: " +
                (trace.coverFound == modelHasCover ? "SIM" : "NÃO"))
        }
    }

    private func runImageProbes() {
        probeVisibleCover(at: 0) { [weak self] rateLimited in
            guard let self = self else { return }
            if rateLimited {
                self.lines.append("Detalhes: não testados após HTTP 429")
                self.finish()
                return
            }

            guard let first = self.summaries.first else {
                self.finish()
                return
            }
            self.runtime.callDecoded(
                "details",
                arguments: [first.id],
                as: Manga.self
            ) { [weak self] result in
                guard let self = self else { return }
                switch result {
                case .success(let manga):
                    // Only inspect the metadata cached by the same details()
                    // request; no second HTML GET or per-title background scan.
                    if self.inspectSource {
                        self.runtime.callDecoded(
                            "inspectDetailsCover",
                            arguments: [first.id],
                            as: WebtoonsDetailsCoverTrace.self
                        ) { [weak self] detailResult in
                            guard let self = self else { return }
                            switch detailResult {
                            case .success(let trace):
                                self.lines.append("og:image encontrado: " +
                                    (trace.metaPresent ? "SIM" : "NÃO"))
                                self.lines.append("og:image content presente: " +
                                    (trace.contentPresent ? "SIM" : "NÃO"))
                                self.lines.append("og:image tipo: " + trace.contentClass)
                                self.lines.append("og:image resolvido pelo JS: " +
                                    (trace.resolvedFound ? "SIM" : "NÃO"))
                                self.lines.append("og:image URL de saída: " + trace.resolvedClass)
                            case .failure:
                                self.lines.append("Inspeção do og:image indisponível (requer fonte 0.1.5).")
                            }
                            self.probe("Capa dos detalhes", url: manga.cover) { [weak self] _ in
                                self?.finish()
                            }
                        }
                    } else {
                        self.probe("Capa dos detalhes", url: manga.cover) { [weak self] _ in
                            self?.finish()
                        }
                    }
                case .failure(let error):
                    self.lines.append("Obtenção dos detalhes: " + error.localizedDescription)
                    self.finish()
                }
            }
        }
    }

    private func probeVisibleCover(
        at index: Int,
        completion: @escaping (Bool) -> Void
    ) {
        guard index < summaries.count else {
            completion(false)
            return
        }
        probe("Capa da lista " + String(index + 1), url: summaries[index].cover) {
            [weak self] rateLimited in
            guard let self = self else { return }
            if rateLimited {
                completion(true)
            } else {
                self.probeVisibleCover(at: index + 1, completion: completion)
            }
        }
    }

    private func probe(
        _ label: String,
        url: String?,
        completion: @escaping (Bool) -> Void
    ) {
        guard let raw = url else {
            lines.append(label + ": URL ausente (nil no modelo Swift)")
            completion(false)
            return
        }
        guard !raw.isEmpty else {
            lines.append(label + ": URL vazia (string no modelo Swift)")
            completion(false)
            return
        }
        // Report only structural properties; never log the source URL,
        // including its query, path, or any embedded credentials.
        let sizeInfo = ", caracteres=" + String(raw.count)
        let unsafePercent = raw.range(
            of: "%(?![0-9A-Fa-f]{2})", options: .regularExpression
        ) != nil
        guard let parsed = URL(string: raw) else {
            lines.append(label + ": URL rejeitada por Foundation" + sizeInfo +
                ", percentual inválido=" + (unsafePercent ? "SIM" : "NÃO"))
            completion(false)
            return
        }
        guard parsed.scheme?.lowercased() == "https" else {
            lines.append(label + ": esquema diferente de HTTPS" + sizeInfo)
            completion(false)
            return
        }
        guard let host = parsed.host, !host.isEmpty else {
            lines.append(label + ": host ausente ou inválido" + sizeInfo)
            completion(false)
            return
        }

        lines.append(label + " URL: host=" + host.lowercased() +
            ", extensão=" + (parsed.pathExtension.isEmpty ? "(nenhuma)" : parsed.pathExtension.lowercased()) +
            ", query=" + (parsed.query == nil ? "não" : "sim"))

        let policy = HTTPPolicy(
            allowedDomains: domains,
            timeout: 15,
            maxRedirects: 3,
            maxResponseBytes: 5 * 1024 * 1024
        )
        guard policy.isURLAllowed(parsed) else {
            lines.append(label + ": host fora dos domínios autorizados")
            completion(false)
            return
        }

        let startedAt = Date()
        let currentClient = HTTPClient(policy: policy)
        client = currentClient // Retain URLSession until asynchronous completion.
        currentClient.send(HTTPRequest(url: raw)) { [weak self] outcome in
            guard let self = self else { return }
            self.client = nil
            let elapsedMilliseconds = Int(Date().timeIntervalSince(startedAt) * 1000)
            let latency = ", ms=" + String(max(0, elapsedMilliseconds))
            switch outcome {
            case .failure(let error):
                self.lines.append(label + ": " + error.localizedDescription + latency)
                completion(false)
            case .success(let response):
                let contentType = response.headers.first {
                    $0.key.lowercased() == "content-type"
                }?.value ?? "(ausente)"
                let mime = contentType.components(separatedBy: ";").first ?? contentType
                let decoded = UIImage(data: response.data) != nil
                let finalHost = URL(string: response.finalURL)?.host ?? "(desconhecido)"
                self.lines.append(
                    label + ": HTTP " + String(response.statusCode) +
                    ", tipo=" + String(mime.prefix(64)) +
                    ", bytes=" + String(response.data.count) +
                    ", UIImage=" + (decoded ? "SIM" : "NÃO") +
                    ", host final=" + finalHost + latency
                )
                completion(response.statusCode == 429)
            }
        }
    }

    private func finish() {
        client = nil
        let text = lines.joined(separator: "\n")
        let callback = finishCallback
        finishCallback = nil
        callback?(text)
    }
}

final class MangaDetailsViewController: UITableViewController {
    private let sourceRecord: InstalledSourceRecord
    private let runtime: JavaScriptSourceRuntime
    private let summary: SourceMangaSummary

    private var manga: Manga?
    private var chapters: [Chapter] = []
    private var pendingRequests = 0
    private var libraryRepository: LibraryRepository?
    private var readingRepository: ReadingProgressRepository?
    private var downloadManager: ChapterDownloadManager?
    private var chapterStates: [String: ChapterReadingState] = [:]
    private var isInLibrary = false
    private var hasCachedOfflineManga = false
    private var hasCachedOfflineChapters = false
    private var receivedRemoteDetails = false
    private var receivedRemoteChapters = false

    init(
        sourceRecord: InstalledSourceRecord,
        runtime: JavaScriptSourceRuntime,
        summary: SourceMangaSummary
    ) {
        self.sourceRecord = sourceRecord
        self.runtime = runtime
        self.summary = summary
        super.init(style: .grouped)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = summary.title
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 92
        tableView.register(
            MangaDetailsHeaderCell.self,
            forCellReuseIdentifier: MangaDetailsHeaderCell.reuseIdentifier
        )
        applyTheme()

        let refreshButton = UIBarButtonItem(
            barButtonSystemItem: .refresh,
            target: self,
            action: #selector(refreshTapped)
        )
        let libraryButton = UIBarButtonItem(
            title: "Biblioteca",
            style: .plain,
            target: self,
            action: #selector(libraryTapped)
        )
        let migrateButton = UIBarButtonItem(
            title: "Migrar",
            style: .plain,
            target: self,
            action: #selector(migrationTapped)
        )
        navigationItem.rightBarButtonItems = [
            refreshButton,
            libraryButton,
            migrateButton
        ]

        do {
            libraryRepository = try LibraryRepository.defaultRepository()
            isInLibrary = try libraryRepository?.isInLibrary(
                sourceID: sourceRecord.manifest.id,
                sourceMangaID: summary.id
            ) ?? false
            updateLibraryButton()
        } catch {
            libraryRepository = nil
        }

        readingRepository = try? ReadingProgressRepository.defaultRepository()
        downloadManager = try? ChapterDownloadManager.defaultManager()

        loadCachedOfflineChapters()
        loadDetailsAndChapters()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadReadingStates()
    }

    @objc private func refreshTapped() {
        loadDetailsAndChapters()
    }


    @objc private func migrationTapped() {
        guard isInLibrary,
              let manga = manga else {
            showMessage(
                title: "Migração",
                message: "Adicione esta obra à Biblioteca antes de migrar."
            )
            return
        }

        navigationController?.pushViewController(
            MigrationViewController(
                originalSource: sourceRecord,
                originalManga: manga,
                originalChapters: chapters
            ),
            animated: true
        )
    }

    @objc private func libraryTapped() {
        guard let manga = manga,
              let repository = libraryRepository else {
            showMessage(
                title: "Biblioteca",
                message: "Aguarde os detalhes do mangá terminarem de carregar."
            )
            return
        }

        do {
            if isInLibrary {
                try repository.remove(
                    sourceID: sourceRecord.manifest.id,
                    sourceMangaID: manga.id
                )
                isInLibrary = false
                showMessage(
                    title: "Biblioteca",
                    message: "Mangá removido da Biblioteca."
                )
            } else {
                try repository.add(
                    sourceID: sourceRecord.manifest.id,
                    manga: manga,
                    chapters: chapters
                )
                isInLibrary = true
                showMessage(
                    title: "Biblioteca",
                    message: "Mangá adicionado à Biblioteca."
                )
            }

            updateLibraryButton()
        } catch {
            showError(error)
        }
    }

    private func updateLibraryButton() {
        guard let items = navigationItem.rightBarButtonItems,
              items.count > 2 else {
            return
        }

        items[1].title = isInLibrary ? "Remover" : "Biblioteca"
        items[2].isEnabled = isInLibrary
    }

    // Use downloaded chapters already persisted in SQLite before refreshing
    // the source. A disconnected Library can still open the local pages.
    private func loadCachedOfflineChapters() {
        guard let repository = try? DownloadRepository.defaultRepository(),
              let snapshot = try? repository.completedOfflineSnapshot(
                  sourceID: sourceRecord.manifest.id,
                  sourceMangaID: summary.id
              ) else { return }

        manga = snapshot.manga
        chapters = snapshot.chapters
        hasCachedOfflineManga = true
        hasCachedOfflineChapters = true
        tableView.reloadData()
        reloadReadingStates()
    }

    private func reportSourceFailure(_ error: Error, hasOfflineFallback: Bool) {
        // Suppress only disconnected-network error when a local copy is
        // available. Other server failures and invalid data remain visible.
        if hasOfflineFallback,
           let sourceError = error as? SourceRuntimeError,
           case .remoteError(let reason) = sourceError,
           reason.contains("-1009") {
            return
        }
        showError(error)
    }

    private func loadDetailsAndChapters() {
        guard pendingRequests == 0 else { return }

        pendingRequests = 2
        receivedRemoteDetails = false
        receivedRemoteChapters = false
        navigationItem.prompt = "Carregando detalhes e capítulos…"
        navigationItem.rightBarButtonItems?.first?.isEnabled = false

        runtime.callDecoded(
            "details",
            arguments: [summary.id],
            as: Manga.self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }

                switch result {
                case .success(let manga):
                    self.receivedRemoteDetails = true
                    self.manga = manga
                    self.title = manga.title
                    self.tableView.reloadSections(
                        IndexSet(integer: 0),
                        with: .automatic
                    )

                case .failure(let error):
                    self.reportSourceFailure(error, hasOfflineFallback: self.hasCachedOfflineManga)
                }

                self.finishRequest()
            }
        }

        runtime.callDecoded(
            "chapters",
            arguments: [summary.id],
            as: [Chapter].self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }

                switch result {
                case .success(let chapters):
                    self.receivedRemoteChapters = true
                    self.chapters = chapters
                    self.reloadReadingStates()
                    self.tableView.reloadSections(
                        IndexSet(integer: 1),
                        with: .automatic
                    )

                case .failure(let error):
                    self.reportSourceFailure(error, hasOfflineFallback: self.hasCachedOfflineChapters)
                }

                self.finishRequest()
            }
        }
    }

    private func finishRequest() {
        pendingRequests = max(0, pendingRequests - 1)

        if pendingRequests == 0 {
            navigationItem.prompt = nil
            navigationItem.rightBarButtonItems?.first?.isEnabled = true

            // A partial offline snapshot must never replace a complete
            // previously persisted Library chapter list.
            if receivedRemoteDetails && receivedRemoteChapters &&
               isInLibrary,
               let manga = manga,
               let repository = libraryRepository {
                do {
                    try repository.add(
                        sourceID: sourceRecord.manifest.id,
                        manga: manga,
                        chapters: chapters
                    )
                } catch {
                    // Details remain usable even if refreshing cached Library
                    // metadata fails; the explicit Library action still reports
                    // persistence errors to the user.
                }
            }
        }
    }

    override func numberOfSections(in tableView: UITableView) -> Int {
        return 2
    }

    override func tableView(
        _ tableView: UITableView,
        titleForHeaderInSection section: Int
    ) -> String? {
        return section == 0 ? "Detalhes" : "Capítulos"
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        if section == 0 {
            return 1
        }

        return chapters.count
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        if indexPath.section == 0 {
            guard let cell = tableView.dequeueReusableCell(
                withIdentifier: MangaDetailsHeaderCell.reuseIdentifier,
                for: indexPath
            ) as? MangaDetailsHeaderCell else {
                return UITableViewCell()
            }

            cell.configure(
                manga: manga,
                fallback: summary,
                allowedDomains: sourceRecord.manifest.domains
            )
            return cell
        }

        let identifier = "ChapterCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)

        let chapter = chapters[indexPath.row]
        cell.textLabel?.text = chapter.name

        var detailParts: [String] = []

        if let number = chapter.number {
            detailParts.append("Cap. \(format(number))")
        }

        if let volume = chapter.volume {
            detailParts.append("Vol. \(format(volume))")
        }

        if let date = chapter.date, !date.isEmpty {
            detailParts.append(date)
        }

        if let scanlator = chapter.scanlator, !scanlator.isEmpty {
            detailParts.append(scanlator)
        }

        if let state = chapterStates[chapter.id] {
            if state.isRead {
                detailParts.append("Lido")
            } else if state.lastPageRead > 0 {
                detailParts.append("Página \(state.lastPageRead + 1)")
            }

            if state.downloaded {
                detailParts.append("Offline")
            }

            cell.accessoryType = state.isRead ? .checkmark : .disclosureIndicator
        } else {
            cell.accessoryType = .disclosureIndicator
        }

        cell.detailTextLabel?.text = detailParts.joined(separator: " • ")
        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        guard indexPath.section == 1 else { return }
        loadPages(for: chapters[indexPath.row])
    }

    private func loadPages(for chapter: Chapter) {
        guard let manga = manga else {
            showMessage(
                title: "Leitor",
                message: "Aguarde os detalhes do mangá terminarem de carregar."
            )
            return
        }

        if let manager = downloadManager,
           let localPages = try? manager.localPages(
                sourceID: sourceRecord.manifest.id,
                mangaID: manga.id,
                chapterID: chapter.id
           ),
           !localPages.isEmpty {
            openReader(
                manga: manga,
                chapter: chapter,
                pages: localPages
            )
            return
        }

        navigationItem.prompt = "Resolvendo páginas…"

        runtime.callDecoded(
            "pages",
            arguments: [chapter.id],
            as: [Page].self
        ) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.navigationItem.prompt = nil

                switch result {
                case .success(let pages):
                    guard !pages.isEmpty else {
                        self.showError(ReaderError.noPages)
                        return
                    }

                    self.openReader(
                        manga: manga,
                        chapter: chapter,
                        pages: pages
                    )

                case .failure(let error):
                    self.showError(error)
                }
            }
        }
    }

    private func openReader(
        manga: Manga,
        chapter: Chapter,
        pages: [Page]
    ) {
        let reader = ReaderViewController(
            sourceID: sourceRecord.manifest.id,
            manga: manga,
            chapter: chapter,
            pages: pages,
            manifest: sourceRecord.manifest,
            chapters: chapters,
            resolvePages: { [weak self] target, completion in
                guard let self = self else {
                    completion(.failure(ReaderError.noPages))
                    return
                }
                if let manager = self.downloadManager,
                   let local = try? manager.localPages(
                        sourceID: self.sourceRecord.manifest.id,
                        mangaID: manga.id,
                        chapterID: target.id
                   ),
                   !local.isEmpty {
                    completion(.success(local))
                    return
                }
                self.runtime.callDecoded(
                    "pages",
                    arguments: [target.id],
                    as: [Page].self,
                    completion: completion
                )
            }
        )

        reader.hidesBottomBarWhenPushed = true

        navigationController?.pushViewController(
            reader,
            animated: true
        )
    }

    private func reloadReadingStates() {
        guard let repository = readingRepository else { return }

        do {
            chapterStates = try repository.chapterStates(
                sourceID: sourceRecord.manifest.id,
                sourceMangaID: summary.id
            )
            if isViewLoaded {
                tableView.reloadData()
            }
        } catch {
            chapterStates = [:]
        }
    }

    private func downloadChapter(_ chapter: Chapter) {
        guard let manga = manga,
              let manager = downloadManager else {
            showMessage(
                title: "Download",
                message: "O gerenciador de downloads ainda não está disponível."
            )
            return
        }

        navigationItem.prompt = "Preparando download…"

        runtime.callDecoded(
            "pages",
            arguments: [chapter.id],
            as: [Page].self
        ) { [weak self] result in
            guard let self = self else { return }

            switch result {
            case .success(let pages):
                guard !pages.isEmpty else {
                    DispatchQueue.main.async {
                        self.navigationItem.prompt = nil
                        self.showError(ReaderError.noPages)
                    }
                    return
                }

                manager.download(
                    sourceID: self.sourceRecord.manifest.id,
                    manga: manga,
                    chapter: chapter,
                    pages: pages,
                    manifest: self.sourceRecord.manifest,
                    progress: { [weak self] value in
                        self?.navigationItem.prompt = String(
                            format: "Baixando… %.0f%%",
                            value * 100
                        )
                    },
                    completion: { [weak self] downloadResult in
                        DispatchQueue.main.async {
                            guard let self = self else { return }
                            self.navigationItem.prompt = nil

                            switch downloadResult {
                            case .success:
                                self.reloadReadingStates()
                                self.showMessage(
                                    title: "Download concluído",
                                    message: "\(chapter.name) está disponível offline."
                                )

                            case .failure(let error):
                                self.showError(error)
                            }
                        }
                    }
                )

            case .failure(let error):
                DispatchQueue.main.async {
                    self.navigationItem.prompt = nil
                    self.showError(error)
                }
            }
        }
    }

    private func removeDownload(_ chapter: Chapter) {
        guard let manga = manga,
              let manager = downloadManager else {
            return
        }

        do {
            try manager.remove(
                sourceID: sourceRecord.manifest.id,
                mangaID: manga.id,
                chapterID: chapter.id
            )
            reloadReadingStates()
            showMessage(
                title: "Download removido",
                message: "\(chapter.name) foi removido do armazenamento offline."
            )
        } catch {
            showError(error)
        }
    }

    override func tableView(
        _ tableView: UITableView,
        editActionsForRowAt indexPath: IndexPath
    ) -> [UITableViewRowAction]? {
        guard indexPath.section == 1,
              let manga = manga else {
            return nil
        }

        let chapter = chapters[indexPath.row]
        let state = chapterStates[chapter.id]
        let read = state?.isRead ?? false

        let readAction = UITableViewRowAction(
            style: .normal,
            title: read ? "Não lido" : "Lido"
        ) { [weak self] _, _ in
            guard let self = self,
                  let repository = self.readingRepository else {
                return
            }

            do {
                try repository.markRead(
                    sourceID: self.sourceRecord.manifest.id,
                    manga: manga,
                    chapter: chapter,
                    isRead: !read
                )
                self.reloadReadingStates()
            } catch {
                self.showError(error)
            }
        }

        let downloaded = state?.downloaded ?? false
        let downloadAction = UITableViewRowAction(
            style: downloaded ? .destructive : .normal,
            title: downloaded ? "Remover offline" : "Download"
        ) { [weak self] _, _ in
            if downloaded {
                self?.removeDownload(chapter)
            } else {
                self?.downloadChapter(chapter)
            }
        }

        return [downloadAction, readAction]
    }

    private func format(_ number: Double) -> String {
        if floor(number) == number {
            return String(Int(number))
        }
        return String(number)
    }

    private func showError(_ error: Error) {
        showMessage(title: "Erro da source", message: error.localizedDescription)
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


extension SourceBrowserViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        ThemeManager.shared.style(searchBar: sourceSearchController.searchBar)
        refreshControl?.tintColor = ThemeManager.shared.palette.secondaryText
        browseHeaderHint.textColor = ThemeManager.shared.palette.secondaryText
        browseHeaderButton.setTitleColor(ThemeManager.shared.palette.accent, for: .normal)
        tableView.reloadData()
        updateEmptyState()
    }
}

extension MangaDetailsViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.visibleCells.compactMap { $0 as? MangaDetailsHeaderCell }.forEach {
            $0.applyPalette()
        }
        tableView.reloadData()
    }
}
