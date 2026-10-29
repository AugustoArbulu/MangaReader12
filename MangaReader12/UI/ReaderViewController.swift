import UIKit

enum ReaderDisplayMode: Int {
    case pages = 0
    case webtoon = 1
}

enum ReaderError: Error, LocalizedError {
    case invalidImage
    case httpStatus(Int)
    case noPages

    var errorDescription: String? {
        switch self {
        case .invalidImage:
            return "The downloaded page is not a valid image."
        case .httpStatus(let status):
            return "Image server returned HTTP \(status)."
        case .noPages:
            return "This chapter returned no pages."
        }
    }
}

final class ReaderImageLoader {
    private let client: HTTPClient
    private let memoryCache = NSCache<NSString, UIImage>()
    private let fileManager: FileManager
    private let diskCacheDirectory: URL?

    init(
        manifest: SourceManifest,
        fileManager: FileManager = .default
    ) {
        self.fileManager = fileManager
        self.client = HTTPClient(
            policy: HTTPPolicy(
                allowedDomains: manifest.domains,
                timeout: 25,
                maxRedirects: 5,
                maxResponseBytes: 20 * 1024 * 1024
            )
        )

        memoryCache.countLimit = 18

        if let base = fileManager.urls(
            for: .cachesDirectory,
            in: .userDomainMask
        ).first {
            let directory = base
                .appendingPathComponent("MangaReader12", isDirectory: true)
                .appendingPathComponent("ReaderImageCache", isDirectory: true)

            try? fileManager.createDirectory(
                at: directory,
                withIntermediateDirectories: true,
                attributes: nil
            )
            diskCacheDirectory = directory
            trimDiskCache(maxFiles: 160)
        } else {
            diskCacheDirectory = nil
        }
    }

    func load(
        page: Page,
        completion: @escaping (Result<UIImage, Error>) -> Void
    ) {
        let key = page.imageUrl as NSString

        if let cached = memoryCache.object(forKey: key) {
            completion(.success(cached))
            return
        }

        if let url = URL(string: page.imageUrl), url.isFileURL {
            do {
                let data = try Data(contentsOf: url)
                guard let image = UIImage(data: data) else {
                    completion(.failure(ReaderError.invalidImage))
                    return
                }

                memoryCache.setObject(image, forKey: key)
                completion(.success(image))
            } catch {
                completion(.failure(error))
            }
            return
        }

        if let diskURL = cacheFileURL(for: page.imageUrl),
           let data = try? Data(contentsOf: diskURL),
           let image = UIImage(data: data) {
            memoryCache.setObject(image, forKey: key)
            completion(.success(image))
            return
        }

        client.send(
            HTTPRequest(
                method: "GET",
                url: page.imageUrl,
                headers: page.headers
            )
        ) { [weak self] result in
            switch result {
            case .success(let response):
                guard (200..<300).contains(response.statusCode) else {
                    completion(.failure(ReaderError.httpStatus(response.statusCode)))
                    return
                }

                guard let image = UIImage(data: response.data) else {
                    completion(.failure(ReaderError.invalidImage))
                    return
                }

                self?.memoryCache.setObject(image, forKey: key)

                if let diskURL = self?.cacheFileURL(for: page.imageUrl) {
                    try? response.data.write(to: diskURL, options: .atomic)
                }

                completion(.success(image))

            case .failure(let error):
                completion(.failure(error))
            }
        }
    }

    func prefetch(page: Page) {
        load(page: page) { _ in }
    }

    private func cacheFileURL(for value: String) -> URL? {
        guard let directory = diskCacheDirectory else { return nil }
        return directory.appendingPathComponent(stableKey(value) + ".bin")
    }

    private func stableKey(_ value: String) -> String {
        var hash: UInt64 = 1469598103934665603
        for byte in value.utf8 {
            hash ^= UInt64(byte)
            hash = hash &* 1099511628211
        }
        return String(format: "%016llx", hash)
    }

    private func trimDiskCache(maxFiles: Int) {
        guard let directory = diskCacheDirectory,
              let files = try? fileManager.contentsOfDirectory(
                at: directory,
                includingPropertiesForKeys: [.contentModificationDateKey],
                options: [.skipsHiddenFiles]
              ),
              files.count > maxFiles else {
            return
        }

        let sorted = files.sorted { lhs, rhs in
            let leftDate = (try? lhs.resourceValues(
                forKeys: [.contentModificationDateKey]
            ).contentModificationDate) ?? .distantPast
            let rightDate = (try? rhs.resourceValues(
                forKeys: [.contentModificationDateKey]
            ).contentModificationDate) ?? .distantPast
            return leftDate < rightDate
        }

        for file in sorted.prefix(max(0, files.count - maxFiles)) {
            try? fileManager.removeItem(at: file)
        }
    }
}

final class ReaderPageCell: UICollectionViewCell, UIScrollViewDelegate {
    static let reuseIdentifier = "ReaderPageCell"

    private let zoomScrollView = UIScrollView()
    private let imageView = UIImageView()
    private let spinner = UIActivityIndicatorView(style: .whiteLarge)
    private let errorLabel = UILabel()
    private var representedURL: String?
    private var scaleMode: ReaderScaleMode = .fitScreen
    private var lastViewportSize: CGSize = .zero

    override init(frame: CGRect) {
        super.init(frame: frame)

        backgroundColor = .black
        contentView.backgroundColor = .black

        zoomScrollView.delegate = self
        zoomScrollView.minimumZoomScale = 1
        zoomScrollView.maximumZoomScale = 4
        zoomScrollView.showsHorizontalScrollIndicator = false
        zoomScrollView.showsVerticalScrollIndicator = false
        contentView.addSubview(zoomScrollView)

        imageView.contentMode = .scaleAspectFit
        imageView.backgroundColor = .black
        zoomScrollView.addSubview(imageView)

        spinner.hidesWhenStopped = true
        contentView.addSubview(spinner)

        errorLabel.textColor = .white
        errorLabel.font = UIFont.systemFont(ofSize: 13)
        errorLabel.textAlignment = .center
        errorLabel.numberOfLines = 0
        errorLabel.isHidden = true
        contentView.addSubview(errorLabel)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func prepareForReuse() {
        super.prepareForReuse()
        representedURL = nil
        imageView.image = nil
        errorLabel.isHidden = true
        errorLabel.text = nil
        zoomScrollView.zoomScale = 1
        zoomScrollView.contentInset = .zero
        zoomScrollView.contentSize = .zero
        lastViewportSize = .zero
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        zoomScrollView.frame = contentView.bounds
        if lastViewportSize != contentView.bounds.size {
            lastViewportSize = contentView.bounds.size
            layoutImage(resetZoom: true)
        }
        spinner.center = CGPoint(
            x: contentView.bounds.midX,
            y: contentView.bounds.midY
        )
        errorLabel.frame = contentView.bounds.insetBy(dx: 24, dy: 24)
    }

    func configure(
        page: Page,
        loader: ReaderImageLoader,
        zoomEnabled: Bool,
        scaleMode: ReaderScaleMode,
        backgroundColor: UIColor,
        foregroundColor: UIColor,
        imageLoaded: @escaping (UIImage) -> Void
    ) {
        representedURL = page.imageUrl
        self.scaleMode = scaleMode
        imageView.image = nil
        errorLabel.isHidden = true
        zoomScrollView.zoomScale = 1
        zoomScrollView.maximumZoomScale = zoomEnabled ? 4 : 1
        self.backgroundColor = backgroundColor
        contentView.backgroundColor = backgroundColor
        zoomScrollView.backgroundColor = backgroundColor
        imageView.backgroundColor = backgroundColor
        errorLabel.textColor = foregroundColor
        spinner.startAnimating()

        loader.load(page: page) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self,
                      self.representedURL == page.imageUrl else {
                    return
                }

                self.spinner.stopAnimating()

                switch result {
                case .success(let image):
                    self.imageView.image = image
                    self.layoutImage(resetZoom: true)
                    imageLoaded(image)

                case .failure(let error):
                    self.errorLabel.text = error.localizedDescription
                    self.errorLabel.isHidden = false
                }
            }
        }
    }

    private func layoutImage(resetZoom: Bool) {
        guard let image = imageView.image, image.size.width > 0, image.size.height > 0 else {
            imageView.frame = zoomScrollView.bounds
            zoomScrollView.contentSize = zoomScrollView.bounds.size
            return
        }

        let viewport = zoomScrollView.bounds.size
        let width = max(1, viewport.width)
        let height = max(1, viewport.height)
        let horizontal = width / image.size.width
        let vertical = height / image.size.height
        let factor: CGFloat
        switch scaleMode {
        case .fitScreen: factor = min(horizontal, vertical)
        case .fitWidth: factor = horizontal
        case .fitHeight: factor = vertical
        case .original: factor = 1
        }

        if resetZoom {
            zoomScrollView.setZoomScale(1, animated: false)
        }

        let scaledSize = CGSize(
            width: max(1, image.size.width * factor),
            height: max(1, image.size.height * factor)
        )
        imageView.frame = CGRect(origin: .zero, size: scaledSize)
        zoomScrollView.contentSize = scaledSize
        centerImage()
    }

    private func centerImage() {
        let viewSize = zoomScrollView.bounds.size
        let imageSize = imageView.frame.size
        let vertical = max(0, (viewSize.height - imageSize.height) / 2)
        let horizontal = max(0, (viewSize.width - imageSize.width) / 2)
        zoomScrollView.contentInset = UIEdgeInsets(
            top: vertical, left: horizontal,
            bottom: vertical, right: horizontal
        )
    }

    func scrollViewDidZoom(_ scrollView: UIScrollView) {
        centerImage()
    }

    func toggleZoom() {
        guard zoomScrollView.maximumZoomScale > 1 else { return }
        let target: CGFloat = zoomScrollView.zoomScale > 1.05 ? 1 : 2.5
        zoomScrollView.setZoomScale(target, animated: true)
    }

    func viewForZooming(in scrollView: UIScrollView) -> UIView? {
        return imageView
    }
}

final class ReaderViewController: UIViewController,
    UICollectionViewDataSource,
    UICollectionViewDelegateFlowLayout,
    UICollectionViewDataSourcePrefetching,
    UIScrollViewDelegate {

    private let sourceID: String
    private let manga: Manga
    private var chapter: Chapter
    private var pages: [Page]
    private let imageLoader: ReaderImageLoader
    private let progressRepository: ReadingProgressRepository?
    private let originalBrightness: CGFloat
    private let originalIdleTimerDisabled: Bool
    private let preferences = ReaderPreferences.shared
    private let chaptersInReadingOrder: [Chapter]
    private let pageResolver: ((Chapter, @escaping (Result<[Page], Error>) -> Void) -> Void)?

    private let layout = UICollectionViewFlowLayout()
    private lazy var collectionView = UICollectionView(
        frame: .zero,
        collectionViewLayout: layout
    )
    private let modeControl = UISegmentedControl(items: ["Páginas", "Webtoon"])
    private let controlsView = UIView()
    private let brightnessSlider = UISlider()
    private let brightnessLabel = UILabel()
    private let directionButton = UIButton(type: .system)

    private var displayMode: ReaderDisplayMode = ReaderPreferences.shared.displayMode
    private var pageDirection: ReaderPageDirection = ReaderPreferences.shared.pageDirection
    private var aspectRatios: [Int: CGFloat] = [:]
    private var lastPersistedIndex = -1
    private var initialPageIndex = 0
    private var didRestoreInitialPage = false
    private var controlsHidden = false
    private var scaleMode: ReaderScaleMode = ReaderPreferences.shared.scaleMode
    private var isChangingChapter = false
    private var prefetchingChapterID: String?
    private var prefetchedChapterID: String?
    private var prefetchedChapterPages: [Page] = []

    init(
        sourceID: String,
        manga: Manga,
        chapter: Chapter,
        pages: [Page],
        manifest: SourceManifest,
        chapters: [Chapter] = [],
        resolvePages: ((Chapter, @escaping (Result<[Page], Error>) -> Void) -> Void)? = nil
    ) {
        self.sourceID = sourceID
        self.manga = manga
        self.chapter = chapter
        self.pages = pages
        // Numeric chapter order wins when all chapters have valid numbers;
        // otherwise sources normally list newest first, so reverse that list.
        if !chapters.isEmpty && chapters.allSatisfy({ $0.number?.isFinite == true }) {
            self.chaptersInReadingOrder = chapters.enumerated().sorted {
                let left = $0.element.number ?? 0
                let right = $1.element.number ?? 0
                return left == right ? $0.offset > $1.offset : left < right
            }.map { $0.element }
        } else {
            self.chaptersInReadingOrder = Array(chapters.reversed())
        }
        self.pageResolver = resolvePages
        self.imageLoader = ReaderImageLoader(manifest: manifest)
        self.progressRepository = try? ReadingProgressRepository.defaultRepository()
        self.originalBrightness = UIScreen.main.brightness
        self.originalIdleTimerDisabled = UIApplication.shared.isIdleTimerDisabled
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = chapter.name
        let background = readerBackgroundColor()
        view.backgroundColor = background

        layout.minimumLineSpacing = displayMode == .webtoon && preferences.webtoonGapEnabled ? 8 : 0
        layout.minimumInteritemSpacing = 0
        layout.scrollDirection = displayMode == .pages ? .horizontal : .vertical

        collectionView.translatesAutoresizingMaskIntoConstraints = false
        collectionView.backgroundColor = background
        collectionView.dataSource = self
        collectionView.prefetchDataSource = self
        collectionView.delegate = self
        collectionView.isPagingEnabled = displayMode == .pages
        collectionView.showsHorizontalScrollIndicator = false
        collectionView.showsVerticalScrollIndicator = false
        collectionView.register(
            ReaderPageCell.self,
            forCellWithReuseIdentifier: ReaderPageCell.reuseIdentifier
        )
        view.addSubview(collectionView)

        configureControls()
        configureGestures()

        NSLayoutConstraint.activate([
            collectionView.topAnchor.constraint(equalTo: view.topAnchor),
            collectionView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            collectionView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            collectionView.bottomAnchor.constraint(equalTo: view.bottomAnchor),

            controlsView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            controlsView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            controlsView.bottomAnchor.constraint(equalTo: view.safeAreaLayoutGuide.bottomAnchor),
            controlsView.heightAnchor.constraint(equalToConstant: 48),

            brightnessLabel.leadingAnchor.constraint(equalTo: controlsView.leadingAnchor, constant: 14),
            brightnessLabel.centerYAnchor.constraint(equalTo: controlsView.centerYAnchor),
            brightnessLabel.widthAnchor.constraint(equalToConstant: 58),

            brightnessSlider.leadingAnchor.constraint(equalTo: brightnessLabel.trailingAnchor, constant: 8),
            brightnessSlider.trailingAnchor.constraint(equalTo: directionButton.leadingAnchor, constant: -10),
            brightnessSlider.centerYAnchor.constraint(equalTo: controlsView.centerYAnchor),

            directionButton.trailingAnchor.constraint(equalTo: controlsView.trailingAnchor, constant: -12),
            directionButton.centerYAnchor.constraint(equalTo: controlsView.centerYAnchor),
            directionButton.widthAnchor.constraint(equalToConstant: 66)
        ])

        modeControl.selectedSegmentIndex = displayMode.rawValue
        modeControl.addTarget(
            self,
            action: #selector(modeChanged),
            for: .valueChanged
        )
        navigationItem.titleView = modeControl
        navigationItem.rightBarButtonItem = UIBarButtonItem(
            title: "Opções",
            style: .plain,
            target: self,
            action: #selector(optionsTapped)
        )

        applyPageDirection()
        loadInitialProgress()
        updatePagePrompt()
        UIApplication.shared.isIdleTimerDisabled = preferences.keepScreenOn
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        layout.invalidateLayout()
    }

    override func viewDidAppear(_ animated: Bool) {
        super.viewDidAppear(animated)

        guard !didRestoreInitialPage,
              !pages.isEmpty else {
            return
        }

        didRestoreInitialPage = true
        let index = min(max(0, initialPageIndex), pages.count - 1)

        collectionView.layoutIfNeeded()
        collectionView.scrollToItem(
            at: IndexPath(item: index, section: 0),
            at: displayMode == .pages ? .centeredHorizontally : .top,
            animated: false
        )
        updatePagePrompt()
        persistProgress(index: index)
        prefetchUpcomingChapterIfNeeded()
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)

        if isMovingFromParent || navigationController?.isBeingDismissed == true {
            UIScreen.main.brightness = originalBrightness
            UIApplication.shared.isIdleTimerDisabled = originalIdleTimerDisabled
            navigationController?.setNavigationBarHidden(false, animated: false)
        }
    }

    private func configureGestures() {
        let singleTap = UITapGestureRecognizer(
            target: self,
            action: #selector(handleReaderTap(_:))
        )
        singleTap.numberOfTapsRequired = 1
        singleTap.cancelsTouchesInView = false

        let doubleTap = UITapGestureRecognizer(
            target: self,
            action: #selector(handleReaderDoubleTap(_:))
        )
        doubleTap.numberOfTapsRequired = 2
        doubleTap.cancelsTouchesInView = false

        singleTap.require(toFail: doubleTap)
        view.addGestureRecognizer(singleTap)
        view.addGestureRecognizer(doubleTap)
    }

    @objc private func handleReaderDoubleTap(_ gesture: UITapGestureRecognizer) {
        guard preferences.doubleTapZoomEnabled,
              displayMode == .pages else {
            return
        }

        let index = currentPageIndex()
        guard let cell = collectionView.cellForItem(
            at: IndexPath(item: index, section: 0)
        ) as? ReaderPageCell else {
            return
        }

        cell.toggleZoom()
    }

    @objc private func handleReaderTap(_ gesture: UITapGestureRecognizer) {
        guard preferences.tapZonesEnabled else {
            return
        }

        let point = gesture.location(in: view)
        let width = max(1, view.bounds.width)

        if displayMode == .webtoon || point.x >= width / 3 && point.x <= width * 2 / 3 {
            toggleControls()
            return
        }

        let leftSide = point.x < width / 3
        let shouldAdvance: Bool

        if pageDirection == .rightToLeft {
            shouldAdvance = leftSide
        } else {
            shouldAdvance = !leftSide
        }

        movePage(forward: shouldAdvance)
    }

    private func movePage(forward: Bool) {
        guard displayMode == .pages, !pages.isEmpty else { return }

        let current = currentPageIndex()
        let target = current + (forward ? 1 : -1)

        guard target >= 0, target < pages.count else { return }

        collectionView.scrollToItem(
            at: IndexPath(item: target, section: 0),
            at: .centeredHorizontally,
            animated: true
        )
        persistProgress(index: target)
        if target >= pages.count - 2 { prefetchUpcomingChapterIfNeeded(for: target) }

        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { [weak self] in
            self?.updatePagePrompt()
        }
    }

    private func adjacentChapter(forward: Bool) -> Chapter? {
        guard let index = chaptersInReadingOrder.firstIndex(where: { $0.id == chapter.id }) else {
            return nil
        }
        let target = index + (forward ? 1 : -1)
        guard chaptersInReadingOrder.indices.contains(target) else { return nil }
        return chaptersInReadingOrder[target]
    }

    @objc private func optionsTapped() {
        let sheet = UIAlertController(title: "Leitor", message: nil, preferredStyle: .actionSheet)
        if let previous = adjacentChapter(forward: false) {
            sheet.addAction(UIAlertAction(
                title: "Anterior: \(previous.name)",
                style: .default
            ) { [weak self] _ in self?.changeChapter(to: previous) })
        }
        if let next = adjacentChapter(forward: true) {
            sheet.addAction(UIAlertAction(
                title: "Próximo: \(next.name)",
                style: .default
            ) { [weak self] _ in self?.changeChapter(to: next) })
        }
        if displayMode == .pages {
            sheet.addAction(UIAlertAction(
                title: "Escala: \(scaleMode.title)",
                style: .default
            ) { [weak self] _ in self?.showScalePicker() })
        }
        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        if let popover = sheet.popoverPresentationController {
            popover.barButtonItem = navigationItem.rightBarButtonItem
        }
        present(sheet, animated: true)
    }

    private func showScalePicker() {
        let sheet = UIAlertController(
            title: "Escala das páginas",
            message: "No Webtoon, as imagens sempre ocupam a largura da tela.",
            preferredStyle: .actionSheet
        )
        for mode in [ReaderScaleMode.fitScreen, .fitWidth, .fitHeight, .original] {
            sheet.addAction(UIAlertAction(title: mode.title, style: .default) { [weak self] _ in
                guard let self = self else { return }
                self.scaleMode = mode
                self.preferences.scaleMode = mode
                self.collectionView.reloadData()
            })
        }
        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        if let popover = sheet.popoverPresentationController {
            popover.barButtonItem = navigationItem.rightBarButtonItem
        }
        present(sheet, animated: true)
    }

    private func changeChapter(to newChapter: Chapter) {
        guard !isChangingChapter,
              newChapter.id != chapter.id,
              let resolve = pageResolver else { return }

        if prefetchedChapterID == newChapter.id && !prefetchedChapterPages.isEmpty {
            displayChapter(newChapter, pages: prefetchedChapterPages)
            return
        }

        isChangingChapter = true
        navigationItem.rightBarButtonItem?.isEnabled = false
        navigationItem.prompt = "Carregando capítulo…"
        resolve(newChapter) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.isChangingChapter = false
                self.navigationItem.rightBarButtonItem?.isEnabled = true
                switch result {
                case .success(let newPages):
                    if newPages.isEmpty {
                        self.presentReaderError(ReaderError.noPages)
                    } else {
                        self.displayChapter(newChapter, pages: newPages)
                    }
                case .failure(let error):
                    self.presentReaderError(error)
                }
                self.updatePagePrompt()
            }
        }
    }

    private func presentReaderError(_ error: Error) {
        let alert = UIAlertController(
            title: "Não foi possível abrir o capítulo",
            message: error.localizedDescription,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }

    private func displayChapter(_ newChapter: Chapter, pages newPages: [Page]) {
        // Persist the outgoing chapter before changing the active identity.
        persistProgress(index: currentPageIndex())
        chapter = newChapter
        pages = newPages
        title = newChapter.name
        aspectRatios.removeAll()
        lastPersistedIndex = -1
        initialPageIndex = 0
        prefetchedChapterID = nil
        prefetchedChapterPages.removeAll()
        prefetchingChapterID = nil
        loadInitialProgress()

        collectionView.setContentOffset(.zero, animated: false)
        collectionView.reloadData()
        layout.invalidateLayout()
        let index = min(max(0, initialPageIndex), newPages.count - 1)
        DispatchQueue.main.async { [weak self] in
            guard let self = self else { return }
            self.collectionView.layoutIfNeeded()
            self.collectionView.scrollToItem(
                at: IndexPath(item: index, section: 0),
                at: self.displayMode == .pages ? .centeredHorizontally : .top,
                animated: false
            )
            self.updatePagePrompt()
            self.persistProgress(index: index)
            self.prefetchUpcomingChapterIfNeeded()
        }
    }

    private func prefetchUpcomingChapterIfNeeded(for index: Int? = nil) {
        guard preferences.preloadNextChapter,
              let resolve = pageResolver,
              !pages.isEmpty,
              (index ?? currentPageIndex()) >= max(0, pages.count - 2),
              let next = adjacentChapter(forward: true),
              prefetchedChapterID != next.id,
              prefetchingChapterID != next.id else {
            return
        }
        let originChapterID = chapter.id
        prefetchingChapterID = next.id
        resolve(next) { [weak self] result in
            DispatchQueue.main.async {
                guard let self = self else { return }
                if self.prefetchingChapterID == next.id {
                    self.prefetchingChapterID = nil
                }
                guard self.chapter.id == originChapterID else { return }
                if case .success(let upcomingPages) = result, !upcomingPages.isEmpty {
                    self.prefetchedChapterID = next.id
                    self.prefetchedChapterPages = upcomingPages
                    for page in upcomingPages.prefix(2) {
                        self.imageLoader.prefetch(page: page)
                    }
                }
                // Preload failures must not interrupt the currently open chapter.
            }
        }
    }

    private func toggleControls() {
        controlsHidden.toggle()
        controlsView.isHidden = controlsHidden

        navigationController?.setNavigationBarHidden(
            controlsHidden,
            animated: true
        )
    }

    private func configureControls() {
        controlsView.translatesAutoresizingMaskIntoConstraints = false
        controlsView.backgroundColor = UIColor(white: 0.08, alpha: 0.88)
        view.addSubview(controlsView)

        brightnessLabel.translatesAutoresizingMaskIntoConstraints = false
        brightnessLabel.text = "Brilho"
        brightnessLabel.textColor = .white
        brightnessLabel.font = UIFont.systemFont(ofSize: 13, weight: .medium)
        controlsView.addSubview(brightnessLabel)

        brightnessSlider.translatesAutoresizingMaskIntoConstraints = false
        brightnessSlider.minimumValue = 0.05
        brightnessSlider.maximumValue = 1
        brightnessSlider.value = Float(UIScreen.main.brightness)
        brightnessSlider.addTarget(
            self,
            action: #selector(brightnessChanged),
            for: .valueChanged
        )
        controlsView.addSubview(brightnessSlider)

        directionButton.translatesAutoresizingMaskIntoConstraints = false
        directionButton.titleLabel?.font = UIFont.systemFont(ofSize: 12, weight: .semibold)
        directionButton.addTarget(
            self,
            action: #selector(directionTapped),
            for: .touchUpInside
        )
        controlsView.addSubview(directionButton)
        updateDirectionButton()
    }

    @objc private func brightnessChanged() {
        UIScreen.main.brightness = CGFloat(brightnessSlider.value)
    }

    @objc private func modeChanged() {
        let current = currentPageIndex()
        displayMode = ReaderDisplayMode(rawValue: modeControl.selectedSegmentIndex) ?? .pages
        ReaderPreferences.shared.displayMode = displayMode

        layout.scrollDirection = displayMode == .pages ? .horizontal : .vertical
        layout.minimumLineSpacing = displayMode == .webtoon && preferences.webtoonGapEnabled ? 8 : 0
        collectionView.isPagingEnabled = displayMode == .pages
        applyPageDirection()
        collectionView.reloadData()
        layout.invalidateLayout()

        DispatchQueue.main.async { [weak self] in
            guard let self = self,
                  current < self.pages.count else {
                return
            }

            self.collectionView.scrollToItem(
                at: IndexPath(item: current, section: 0),
                at: self.displayMode == .pages ? .centeredHorizontally : .top,
                animated: false
            )
            self.updatePagePrompt()
        }
    }

    @objc private func directionTapped() {
        guard displayMode == .pages else { return }

        let current = currentPageIndex()
        pageDirection = pageDirection == .leftToRight
            ? .rightToLeft
            : .leftToRight
        ReaderPreferences.shared.pageDirection = pageDirection

        applyPageDirection()
        collectionView.reloadData()
        layout.invalidateLayout()

        DispatchQueue.main.async { [weak self] in
            guard let self = self,
                  current < self.pages.count else {
                return
            }

            self.collectionView.scrollToItem(
                at: IndexPath(item: current, section: 0),
                at: .centeredHorizontally,
                animated: false
            )
            self.updatePagePrompt()
        }
    }

    private func applyPageDirection() {
        collectionView.semanticContentAttribute = pageDirection == .rightToLeft
            ? .forceRightToLeft
            : .forceLeftToRight
        directionButton.isEnabled = displayMode == .pages
        directionButton.alpha = displayMode == .pages ? 1 : 0.45
        updateDirectionButton()
    }

    private func updateDirectionButton() {
        directionButton.setTitle(
            pageDirection == .rightToLeft ? "← RTL" : "LTR →",
            for: .normal
        )
    }

    private func loadInitialProgress() {
        guard let repository = progressRepository else { return }

        do {
            if let state = try repository.chapterState(
                sourceID: sourceID,
                sourceMangaID: manga.id,
                sourceChapterID: chapter.id
            ) {
                initialPageIndex = state.lastPageRead
            }
        } catch {
            initialPageIndex = 0
        }
    }

    func collectionView(
        _ collectionView: UICollectionView,
        numberOfItemsInSection section: Int
    ) -> Int {
        return pages.count
    }

    func collectionView(
        _ collectionView: UICollectionView,
        cellForItemAt indexPath: IndexPath
    ) -> UICollectionViewCell {
        guard let cell = collectionView.dequeueReusableCell(
            withReuseIdentifier: ReaderPageCell.reuseIdentifier,
            for: indexPath
        ) as? ReaderPageCell else {
            return UICollectionViewCell()
        }

        let page = pages[indexPath.item]
        let renderedChapterID = chapter.id
        cell.configure(
            page: page,
            loader: imageLoader,
            zoomEnabled: displayMode == .pages,
            scaleMode: displayMode == .webtoon ? .fitWidth : scaleMode,
            backgroundColor: readerBackgroundColor(),
            foregroundColor: readerForegroundColor()
        ) { [weak self] image in
            guard let self = self,
                  renderedChapterID == self.chapter.id,
                  image.size.width > 0 else {
                return
            }

            let ratio = max(0.25, min(image.size.height / image.size.width, 8))
            if self.aspectRatios[indexPath.item] != ratio {
                self.aspectRatios[indexPath.item] = ratio

                if self.displayMode == .webtoon {
                    self.layout.invalidateLayout()
                }
            }
        }

        return cell
    }

    func collectionView(
        _ collectionView: UICollectionView,
        prefetchItemsAt indexPaths: [IndexPath]
    ) {
        for indexPath in indexPaths where indexPath.item < pages.count {
            imageLoader.prefetch(page: pages[indexPath.item])
        }
    }

    func collectionView(
        _ collectionView: UICollectionView,
        willDisplay cell: UICollectionViewCell,
        forItemAt indexPath: IndexPath
    ) {
        if displayMode == .webtoon {
            persistProgress(index: indexPath.item)
        }
        if indexPath.item >= pages.count - 2 {
            prefetchUpcomingChapterIfNeeded(for: indexPath.item)
        }
    }

    func collectionView(
        _ collectionView: UICollectionView,
        layout collectionViewLayout: UICollectionViewLayout,
        sizeForItemAt indexPath: IndexPath
    ) -> CGSize {
        let width = max(1, collectionView.bounds.width)

        if displayMode == .pages {
            return CGSize(
                width: width,
                height: max(1, collectionView.bounds.height)
            )
        }

        let ratio = aspectRatios[indexPath.item] ?? 1.5
        return CGSize(width: width, height: max(180, width * ratio))
    }

    func scrollViewDidEndDecelerating(_ scrollView: UIScrollView) {
        updatePagePrompt()
        persistProgress(index: currentPageIndex())
        prefetchUpcomingChapterIfNeeded()
    }

    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        if displayMode == .webtoon {
            updatePagePrompt()
        }
    }

    private func currentPageIndex() -> Int {
        guard !pages.isEmpty else { return 0 }

        if displayMode == .pages {
            let center = CGPoint(
                x: collectionView.contentOffset.x + collectionView.bounds.width / 2,
                y: collectionView.contentOffset.y + collectionView.bounds.height / 2
            )

            if let indexPath = collectionView.indexPathForItem(at: center) {
                return indexPath.item
            }

            return 0
        }

        let visible = collectionView.indexPathsForVisibleItems
            .sorted { $0.item < $1.item }
        return visible.first?.item ?? 0
    }

    private func updatePagePrompt() {
        guard preferences.showPageNumber else {
            navigationItem.prompt = nil
            return
        }

        guard !pages.isEmpty else {
            navigationItem.prompt = "0 páginas"
            return
        }

        let index = currentPageIndex()
        navigationItem.prompt = "\(index + 1) / \(pages.count)"
    }

    private func readerBackgroundColor() -> UIColor {
        switch preferences.backgroundStyle {
        case .black:
            return .black
        case .gray:
            return UIColor(white: 0.20, alpha: 1)
        case .white:
            return .white
        }
    }

    private func readerForegroundColor() -> UIColor {
        return preferences.backgroundStyle == .white ? .black : .white
    }

    private func persistProgress(index: Int) {
        guard index >= 0,
              index < pages.count,
              index != lastPersistedIndex else {
            return
        }

        lastPersistedIndex = index

        // Capture an immutable chapter snapshot: next/previous chapter may
        // change while SQLite persistence is queued on a background thread.
        let currentChapter = chapter
        let currentManga = manga
        let currentSourceID = sourceID
        let pageCount = pages.count
        let repository = progressRepository
        DispatchQueue.global(qos: .utility).async {
            try? repository?.recordProgress(
                sourceID: currentSourceID,
                manga: currentManga,
                chapter: currentChapter,
                pageIndex: index,
                totalPages: pageCount
            )
        }
    }
}
