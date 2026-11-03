import UIKit

// This shelf is independent of third-party source installations and of the
// remote manga Library. Files never go through HTTPClient or remote parsers.
struct LocalComic: Codable {
    let id: String
    let title: String
    let createdAt: TimeInterval
    let pages: [String]
}

final class LocalComicStore {
    static let shared = LocalComicStore()
    private let manager = FileManager.default

    private var root: URL? {
        return manager.urls(for: .documentDirectory, in: .userDomainMask)
            .first?.appendingPathComponent("LocalComics", isDirectory: true)
    }

    func list() throws -> [LocalComic] {
        guard let root = root else { return [] }
        try manager.createDirectory(
            at: root, withIntermediateDirectories: true, attributes: nil
        )
        let directories = try manager.contentsOfDirectory(
            at: root, includingPropertiesForKeys: [.isDirectoryKey],
            options: [.skipsHiddenFiles]
        )
        var comics: [LocalComic] = []
        for folder in directories {
            guard UUID(uuidString: folder.lastPathComponent) != nil,
                  (try? folder.resourceValues(forKeys: [.isDirectoryKey])
                    .isDirectory) == true,
                  let bytes = try? Data(contentsOf:
                    folder.appendingPathComponent("manifest.json")),
                  bytes.count < 256 * 1024,
                  let comic = try? JSONDecoder().decode(LocalComic.self, from: bytes),
                  comic.id == folder.lastPathComponent,
                  !comic.pages.isEmpty,
                  comic.pages.count <= 1200,
                  comic.pages.allSatisfy({ Self.isSafePageName($0) }) else {
                continue
            }
            comics.append(comic)
        }
        return comics.sorted { $0.createdAt > $1.createdAt }
    }

    func find(id: String) throws -> LocalComic? {
        return try list().first { $0.id == id }
    }

    private static func isSafePageName(_ value: String) -> Bool {
        return value.range(
            of: "^page-[0-9]{5}\\.(jpg|png)$",
            options: .regularExpression
        ) != nil
    }

    func pages(for comic: LocalComic) -> [Page] {
        guard let root = root,
              UUID(uuidString: comic.id) != nil else { return [] }
        let folder = root.appendingPathComponent(comic.id, isDirectory: true)
        return comic.pages.enumerated().compactMap { index, file -> Page? in
            guard Self.isSafePageName(file) else { return nil }
            let url = folder.appendingPathComponent(file)
            guard manager.fileExists(atPath: url.path) else { return nil }
            return Page(index: index, imageUrl: url.absoluteString, headers: [:])
        }
    }

    // Called on a utility queue. Existing LocalComics remain untouched when
    // an import fails; the private staging directory is removed in all cases.
    func importArchive(_ url: URL) throws -> LocalComic {
        guard ["cbz", "zip"].contains(url.pathExtension.lowercased()),
              let root = root else {
            throw SafeCBZError.unsupported
        }
        try manager.createDirectory(
            at: root, withIntermediateDirectories: true, attributes: nil
        )
        let id = UUID().uuidString
        let staging = root.appendingPathComponent(".import-" + id, isDirectory: true)
        let final = root.appendingPathComponent(id, isDirectory: true)
        try manager.createDirectory(
            at: staging, withIntermediateDirectories: false, attributes: nil
        )
        defer { try? manager.removeItem(at: staging) }
        let filenames = try SafeCBZArchive.extract(archiveURL: url, into: staging)
        let display = url.deletingPathExtension().lastPathComponent
            .trimmingCharacters(in: .whitespacesAndNewlines)
        let comic = LocalComic(
            id: id,
            title: String((display.isEmpty ? "Quadrinho local" : display).prefix(120)),
            createdAt: Date().timeIntervalSince1970,
            pages: filenames
        )
        let manifest = try JSONEncoder().encode(comic)
        try manifest.write(
            to: staging.appendingPathComponent("manifest.json"), options: .atomic
        )
        try manager.moveItem(at: staging, to: final)
        return comic
    }

    func remove(_ comic: LocalComic) throws {
        guard let root = root,
              UUID(uuidString: comic.id) != nil else {
            throw SafeCBZError.unsafeEntry
        }
        let folder = root.appendingPathComponent(comic.id, isDirectory: true)
        try manager.removeItem(at: folder)
        // Local file deletion must not touch other sources' reading progress.
        try? ReadingProgressRepository.defaultRepository().removeHistory(
            sourceID: "local.cbz", sourceMangaID: comic.id
        )
    }

    static func open(
        _ comic: LocalComic,
        from navigation: UINavigationController?
    ) throws {
        let pages = LocalComicStore.shared.pages(for: comic)
        guard !pages.isEmpty else { throw SafeCBZError.noImages }
        let manga = Manga(
            id: comic.id, title: comic.title, altTitles: [], cover: nil,
            author: nil, artist: nil,
            description: "Arquivo CBZ/ZIP importado do app Arquivos.",
            status: .unknown, genres: [], url: nil
        )
        let chapter = Chapter(
            id: "archive", name: comic.title,
            number: 1, volume: nil, date: nil,
            scanlator: nil, language: nil, url: nil
        )
        // The dummy manifest is used solely for the ReaderImageLoader
        // initializer. All page URLs are local file:// URLs under Documents,
        // and ReaderImageLoader NEVER sends HTTPS requests for local pages.
        let manifest = SourceManifest(
            id: "local.cbz", name: "Arquivos locais", version: "1.0.0",
            lang: "und", author: "MangaReader12",
            script: "https://localhost.invalid/not-used",
            icon: nil, apiVersion: 1, minAppVersion: "0.1.0",
            domains: ["localhost.invalid"], nsfw: false, sha256: nil
        )
        let reader = ReaderViewController(
            sourceID: "local.cbz", manga: manga, chapter: chapter,
            pages: pages, manifest: manifest, chapters: [chapter]
        )
        reader.hidesBottomBarWhenPushed = true
        navigation?.pushViewController(reader, animated: true)
    }
}

final class LocalComicsViewController:
    UITableViewController, UIDocumentPickerDelegate {

    private var comics: [LocalComic] = []
    private var importing = false
    private let subtitle = UILabel()

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Arquivos locais"
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 76
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            title: "Importar", style: .plain,
            target: self, action: #selector(importTapped)
        )
        let header = UIView(frame: CGRect(
            x: 0, y: 0, width: max(1, tableView.bounds.width), height: 70
        ))
        subtitle.frame = header.bounds.insetBy(dx: 14, dy: 8)
        subtitle.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        subtitle.text = "CBZ/ZIP com imagens JPEG ou PNG.\n" +
            "Armazenamento local • disponível sem internet."
        subtitle.textColor = ThemeManager.shared.palette.secondaryText
        subtitle.font = UIFont.systemFont(ofSize: 13)
        subtitle.numberOfLines = 0
        header.addSubview(subtitle)
        tableView.tableHeaderView = header
        applyTheme()
        reloadShelf()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        reloadShelf()
    }

    private func reloadShelf() {
        do {
            comics = try LocalComicStore.shared.list()
            tableView.backgroundView = comics.isEmpty
                ? emptyMessage("Nenhum arquivo importado.\nToque em Importar para selecionar CBZ/ZIP.")
                : nil
            tableView.reloadData()
        } catch {
            showError(error)
        }
    }

    private func emptyMessage(_ text: String) -> UIView {
        let label = UILabel()
        label.text = text
        label.textAlignment = .center
        label.numberOfLines = 0
        label.textColor = ThemeManager.shared.palette.secondaryText
        return label
    }

    @objc private func importTapped() {
        guard !importing else { return }
        // iOS 12 API: .import grants an app-local copy from Files.
        // public.data also permits .cbz files from providers that do not
        // advertise the nonstandard CBZ UTI; extension is checked afterward.
        let picker = UIDocumentPickerViewController(
            documentTypes: ["public.zip-archive", "public.data"],
            in: .import
        )
        picker.delegate = self
        picker.allowsMultipleSelection = false
        present(picker, animated: true)
    }

    func documentPicker(
        _ controller: UIDocumentPickerViewController,
        didPickDocumentsAt urls: [URL]
    ) {
        guard let url = urls.first,
              ["cbz", "zip"].contains(url.pathExtension.lowercased()),
              !importing else {
            showMessage(
                title: "Arquivo incompatível",
                message: "Selecione um CBZ ou ZIP com imagens JPEG/PNG."
            )
            return
        }
        importing = true
        navigationItem.rightBarButtonItem?.isEnabled = false
        navigationItem.prompt = "Verificando arquivo…"
        DispatchQueue.global(qos: .utility).async { [weak self] in
            let result = Result { try LocalComicStore.shared.importArchive(url) }
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.importing = false
                self.navigationItem.prompt = nil
                self.navigationItem.rightBarButtonItem?.isEnabled = true
                switch result {
                case .success(let comic):
                    self.reloadShelf()
                    self.showMessage(
                        title: "Importação concluída",
                        message: comic.title + " • " + String(comic.pages.count) +
                            " páginas disponíveis offline."
                    )
                case .failure(let error):
                    self.showError(error)
                }
            }
        }
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {}

    override func tableView(
        _ tableView: UITableView, numberOfRowsInSection section: Int
    ) -> Int {
        return comics.count
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let cell = tableView.dequeueReusableCell(withIdentifier: "LocalComicCell")
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: "LocalComicCell")
        ThemeManager.shared.style(cell: cell)
        let comic = comics[indexPath.row]
        cell.textLabel?.text = comic.title
        cell.detailTextLabel?.text =
            String(comic.pages.count) + " páginas • disponível offline"
        cell.accessoryType = .disclosureIndicator
        return cell
    }

    override func tableView(
        _ tableView: UITableView, didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        do {
            try LocalComicStore.open(comics[indexPath.row], from: navigationController)
        } catch {
            showError(error)
        }
    }

    override func tableView(
        _ tableView: UITableView,
        commit editingStyle: UITableViewCell.EditingStyle,
        forRowAt indexPath: IndexPath
    ) {
        guard editingStyle == .delete else { return }
        let comic = comics[indexPath.row]
        let alert = UIAlertController(
            title: "Excluir arquivo local?",
            message: "Isso remove as páginas importadas do armazenamento. " +
                "Não altera sua Biblioteca online nem os downloads das fontes.",
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(title: "Excluir", style: .destructive) {
            [weak self] _ in
            do {
                try LocalComicStore.shared.remove(comic)
                self?.reloadShelf()
            } catch {
                self?.showError(error)
            }
        })
        present(alert, animated: true)
    }

    private func showError(_ error: Error) {
        showMessage(title: "Arquivos locais", message: error.localizedDescription)
    }

    private func showMessage(title: String, message: String) {
        let alert = UIAlertController(
            title: title, message: message, preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        subtitle.textColor = ThemeManager.shared.palette.secondaryText
        tableView.tableHeaderView?.backgroundColor =
            ThemeManager.shared.palette.background
        tableView.reloadData()
    }
}

extension LocalComicsViewController: ThemeApplicable {}
