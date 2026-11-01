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

// iOS 12 reader image pipeline. File IO, image construction, and the
// scheduling state live on one utility queue; completion always arrives on
// the main queue. Identical requests share one bounded network transfer.
final class ReaderImageLoader {
    private struct PendingPage {
        let key: String
        let page: Page
    }

    private typealias ImageCompletion = (Result<UIImage, Error>) -> Void
    private let client: HTTPClient
    private let memoryCache = NSCache<NSString, UIImage>()
    private let fileManager: FileManager
    private let diskCacheDirectory: URL?
    private let workQueue = DispatchQueue(
        label: "com.mangareader12.reader-image-cache", qos: .userInitiated
    )
    private let maxConcurrentTransfers = 3
    private var activeTransfers = 0
    private var pending: [PendingPage] = []
    private var waiting: [String: [ImageCompletion]] = [:]
    private var diskWritesSinceTrim = 0
    private var memoryWarningObserver: NSObjectProtocol?

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

        // Count-only caching allows 18 tall webtoon strips to exhaust RAM.
        // NSCache uses the estimated decoded pixel footprint (not JPEG bytes).
        memoryCache.countLimit = 8
        memoryCache.totalCostLimit = 48 * 1024 * 1024

        if let base = fileManager.urls(
            for: .cachesDirectory, in: .userDomainMask
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
        } else {
            diskCacheDirectory = nil
        }

        // No directory enumeration or image decoding on the UIKit path.
        workQueue.async { [weak self] in
            self?.trimDiskCache(maxFiles: 160, maxBytes: 192 * 1024 * 1024)
        }
        memoryWarningObserver = NotificationCenter.default.addObserver(
            forName: UIApplication.didReceiveMemoryWarningNotification,
            object: nil,
            queue: nil
        ) { [weak self] _ in
            self?.workQueue.async { [weak self] in
                self?.memoryCache.removeAllObjects()
            }
        }
    }

    deinit {
        if let token = memoryWarningObserver {
            NotificationCenter.default.removeObserver(token)
        }
    }

    func load(
        page: Page,
        completion: @escaping (Result<UIImage, Error>) -> Void
    ) {
        workQueue.async { [weak self] in
            self?.loadOnWorker(page: page, completion: completion)
        }
    }

    func prefetch(page: Page) {
        load(page: page) { _ in }
    }

    // Only called on workQueue. The existing HTTPS/domain policy is applied
    // even for disk hits. Local downloaded pages remain usable offline.
    private func loadOnWorker(page: Page, completion: @escaping ImageCompletion) {
        let fileURL = URL(string: page.imageUrl)
        let isLocalFile = fileURL?.isFileURL == true
        if !isLocalFile {
            do {
                _ = try client.policy.validatedURL(page.imageUrl)
            } catch {
                deliver(.failure(error), to: [completion])
                return
            }
        }

        // Source domain scope and request headers are part of this digest:
        // another source/Referer cannot reuse cached content for the same URL.
        // Raw auth headers and URLs are never stored as cache filenames.
        let key = cacheKey(for: page)
        if let image = memoryCache.object(forKey: key as NSString) {
            deliver(.success(image), to: [completion])
            return
        }

        if waiting[key] != nil {
            waiting[key]?.append(completion)
            return
        }

        if isLocalFile, let url = fileURL {
            do {
                let data = try Data(contentsOf: url)
                guard let image = UIImage(data: data) else {
                    deliver(.failure(ReaderError.invalidImage), to: [completion])
                    return
                }
                remember(image, for: key)
                deliver(.success(image), to: [completion])
            } catch {
                deliver(.failure(error), to: [completion])
            }
            return
        }

        if let diskURL = cacheFileURL(for: key),
           let data = try? Data(contentsOf: diskURL) {
            if let image = UIImage(data: data) {
                remember(image, for: key)
                deliver(.success(image), to: [completion])
                return
            }
            // Corrupt cached files must not repeatedly block a valid fetch.
            try? fileManager.removeItem(at: diskURL)
        }

        waiting[key] = [completion]
        pending.append(PendingPage(key: key, page: page))
        startPendingTransfers()
    }

    // No overlapping transfer for the same cache key and at most 3 total.
    private func startPendingTransfers() {
        while activeTransfers < maxConcurrentTransfers && !pending.isEmpty {
            let request = pending.removeFirst()
            activeTransfers += 1
            client.send(
                HTTPRequest(
                    method: "GET",
                    url: request.page.imageUrl,
                    headers: request.page.headers
                )
            ) { [weak self] result in
                self?.workQueue.async { [weak self] in
                    self?.finish(request, result: result)
                }
            }
        }
    }

    private func finish(
        _ request: PendingPage,
        result: Result<HTTPResponse, Error>
    ) {
        activeTransfers = max(0, activeTransfers - 1)
        let output: Result<UIImage, Error>
        switch result {
        case .success(let response):
            if !(200..<300).contains(response.statusCode) {
                output = .failure(ReaderError.httpStatus(response.statusCode))
            } else if let image = UIImage(data: response.data) {
                remember(image, for: request.key)
                if let diskURL = cacheFileURL(for: request.key) {
                    do {
                        try response.data.write(to: diskURL, options: .atomic)
                        diskWritesSinceTrim += 1
                        if diskWritesSinceTrim >= 8 {
                            diskWritesSinceTrim = 0
                            trimDiskCache(
                                maxFiles: 160,
                                maxBytes: 192 * 1024 * 1024
                            )
                        }
                    } catch {
                        // Cache failures must not break live online reading.
                    }
                }
                output = .success(image)
            } else {
                output = .failure(ReaderError.invalidImage)
            }
        case .failure(let error):
            output = .failure(error)
        }

        if let completions = waiting.removeValue(forKey: request.key) {
            deliver(output, to: completions)
        }
        startPendingTransfers()
    }

    private func remember(_ image: UIImage, for key: String) {
        // Even a small compressed JPEG may expand to tens of MB of pixels.
        let pixelWidth = image.size.width * image.scale
        let pixelHeight = image.size.height * image.scale
        guard pixelWidth.isFinite, pixelHeight.isFinite else { return }
        let width = Int(max(1, min(32_000, pixelWidth)))
        let height = Int(max(1, min(32_000, pixelHeight)))
        memoryCache.setObject(
            image, forKey: key as NSString, cost: width * height * 4
        )
    }

    private func deliver(
        _ result: Result<UIImage, Error>,
        to completions: [ImageCompletion]
    ) {
        DispatchQueue.main.async {
            completions.forEach { $0(result) }
        }
    }

    private func cacheKey(for page: Page) -> String {
        let scope = client.policy.allowedDomains.sorted().joined(separator: ",")
        let headers = page.headers.keys.sorted().map {
            $0.lowercased() + ":" + (page.headers[$0] ?? "")
        }.joined(separator: "\u{0}")
        let input = page.imageUrl + "\u{0}" + scope + "\u{0}" + headers
        return SHA256Digest.hex(Data(input.utf8))
    }

    private func cacheFileURL(for key: String) -> URL? {
        guard let directory = diskCacheDirectory else { return nil }
        return directory.appendingPathComponent(key + ".bin")
    }

    // Bounded by disk bytes AND count. Run at startup and periodically after
    // successful writes, always on workQueue and never on the main thread.
    private func trimDiskCache(maxFiles: Int, maxBytes: Int) {
        guard let directory = diskCacheDirectory,
              let files = try? fileManager.contentsOfDirectory(
                at: directory,
                includingPropertiesForKeys: [
                    .contentModificationDateKey, .fileSizeKey, .isRegularFileKey
                ],
                options: [.skipsHiddenFiles]
              ) else { return }

        let entries: [(url: URL, size: Int, date: Date)] = files.compactMap { url in
            guard let values = try? url.resourceValues(
                forKeys: [.contentModificationDateKey, .fileSizeKey, .isRegularFileKey]
            ), values.isRegularFile == true else { return nil }
            return (url, max(0, values.fileSize ?? 0),
                values.contentModificationDate ?? .distantPast)
        }
        var totalBytes = entries.reduce(0) { $0 + $1.size }
        var totalFiles = entries.count
        for entry in entries.sorted(by: { $0.date < $1.date }) {
            guard totalFiles > maxFiles || totalBytes > maxBytes else { break }
            do {
                try fileManager.removeItem(at: entry.url)
                totalFiles -= 1
                totalBytes -= entry.size
            } catch {
                // Failure to trim disk cache must not block the reader.
            }
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

    func setScaleMode(_ mode: ReaderScaleMode) {
        scaleMode = mode
        // Update the image already displayed without reloading the chapter,
        // moving the collection, or triggering image downloads.
        layoutImage(resetZoom: true)
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
    UIScrollViewDelegate,
    UIGestureRecognizerDelegate {

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
    private let scaleComparisonView = UIView()
    private let scaleComparisonLabel = UILabel()
    private let scaleComparisonControl = UISegmentedControl(
        items: ["Tela", "Largura", "Altura", "Original"]
    )
    private let scaleComparisonCloseButton = UIButton(type: .system)

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
    private var attemptedPreloadChapterID: String?
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
        configureScaleComparison()
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

            scaleComparisonView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            scaleComparisonView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            scaleComparisonView.bottomAnchor.constraint(equalTo: controlsView.topAnchor),
            scaleComparisonView.heightAnchor.constraint(equalToConstant: 84),

            scaleComparisonLabel.leadingAnchor.constraint(
                equalTo: scaleComparisonView.leadingAnchor, constant: 14
            ),
            scaleComparisonLabel.topAnchor.constraint(
                equalTo: scaleComparisonView.topAnchor, constant: 7
            ),

            scaleComparisonCloseButton.trailingAnchor.constraint(
                equalTo: scaleComparisonView.trailingAnchor, constant: -14
            ),
            scaleComparisonCloseButton.centerYAnchor.constraint(
                equalTo: scaleComparisonLabel.centerYAnchor
            ),

            scaleComparisonControl.leadingAnchor.constraint(
                equalTo: scaleComparisonView.leadingAnchor, constant: 12
            ),
            scaleComparisonControl.trailingAnchor.constraint(
                equalTo: scaleComparisonView.trailingAnchor, constant: -12
            ),
            scaleComparisonControl.bottomAnchor.constraint(
                equalTo: scaleComparisonView.bottomAnchor, constant: -8
            ),
            scaleComparisonControl.heightAnchor.constraint(equalToConstant: 32),

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
            scaleComparisonView.isHidden = true
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
        singleTap.delegate = self

        let doubleTap = UITapGestureRecognizer(
            target: self,
            action: #selector(handleReaderDoubleTap(_:))
        )
        doubleTap.numberOfTapsRequired = 2
        doubleTap.cancelsTouchesInView = false
        doubleTap.delegate = self

        singleTap.require(toFail: doubleTap)
        view.addGestureRecognizer(singleTap)
        view.addGestureRecognizer(doubleTap)
    }

    // The reader owns root-level tap recognizers for its left/center/right
    // navigation zones. Those recognizers must never react to controls
    // placed over the image (especially the central scale selector).
    // Delegate filtering runs before recognizing either single or double taps.
    func gestureRecognizer(
        _ gestureRecognizer: UIGestureRecognizer,
        shouldReceive touch: UITouch
    ) -> Bool {
        let location = touch.location(in: view)
        if (!scaleComparisonView.isHidden &&
            scaleComparisonView.frame.contains(location)) ||
           (!controlsView.isHidden &&
            controlsView.frame.contains(location)) {
            return false
        }

        // Also respect controls added by future in-reader overlays.
        var candidate = touch.view
        while let current = candidate {
            if current is UIControl {
                return false
            }
            candidate = current.superview
        }

        return true
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
                title: "Comparar escalas: \(scaleMode.title)",
                style: .default
            ) { [weak self] _ in self?.showScaleComparison() })
        }
        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        if let popover = sheet.popoverPresentationController {
            popover.barButtonItem = navigationItem.rightBarButtonItem
        }
        present(sheet, animated: true)
    }

    private func showScaleComparison() {
        guard displayMode == .pages else { return }
        if controlsHidden {
            controlsHidden = false
            controlsView.isHidden = false
            navigationController?.setNavigationBarHidden(false, animated: true)
        }
        scaleComparisonControl.selectedSegmentIndex = scaleMode.rawValue
        scaleComparisonView.isHidden = false
    }

    @objc private func closeScaleComparison() {
        scaleComparisonView.isHidden = true
    }

    @objc private func comparisonScaleChanged(_ sender: UISegmentedControl) {
        guard displayMode == .pages,
              let selected = ReaderScaleMode(rawValue: sender.selectedSegmentIndex),
              selected != scaleMode else { return }

        scaleMode = selected
        preferences.scaleMode = selected

        // The current page stays visible throughout comparison, without a
        // collection reload, progress mutation, or new source request.
        for case let cell as ReaderPageCell in collectionView.visibleCells {
            cell.setScaleMode(selected)
        }
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
        attemptedPreloadChapterID = nil
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
              prefetchingChapterID != next.id,
              attemptedPreloadChapterID != next.id else {
            return
        }
        let originChapterID = chapter.id
        prefetchingChapterID = next.id
        attemptedPreloadChapterID = next.id
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
        if controlsHidden {
            scaleComparisonView.isHidden = true
        }

        navigationController?.setNavigationBarHidden(
            controlsHidden,
            animated: true
        )
    }

    private func configureScaleComparison() {
        scaleComparisonView.translatesAutoresizingMaskIntoConstraints = false
        scaleComparisonView.backgroundColor = UIColor(white: 0.08, alpha: 0.94)
        scaleComparisonView.isHidden = true
        view.addSubview(scaleComparisonView)

        scaleComparisonLabel.translatesAutoresizingMaskIntoConstraints = false
        scaleComparisonLabel.text = "Escala das páginas"
        scaleComparisonLabel.font = UIFont.systemFont(ofSize: 13, weight: .semibold)
        scaleComparisonLabel.textColor = .white
        scaleComparisonView.addSubview(scaleComparisonLabel)

        scaleComparisonCloseButton.translatesAutoresizingMaskIntoConstraints = false
        scaleComparisonCloseButton.setTitle("Fechar", for: .normal)
        scaleComparisonCloseButton.setTitleColor(.white, for: .normal)
        scaleComparisonCloseButton.titleLabel?.font = UIFont.systemFont(ofSize: 13)
        scaleComparisonCloseButton.addTarget(
            self, action: #selector(closeScaleComparison), for: .touchUpInside
        )
        scaleComparisonView.addSubview(scaleComparisonCloseButton)

        scaleComparisonControl.translatesAutoresizingMaskIntoConstraints = false
        scaleComparisonControl.selectedSegmentIndex = scaleMode.rawValue
        scaleComparisonControl.tintColor = .white
        scaleComparisonControl.setTitleTextAttributes(
            [.font: UIFont.systemFont(ofSize: 11)], for: .normal
        )
        scaleComparisonControl.addTarget(
            self, action: #selector(comparisonScaleChanged(_:)), for: .valueChanged
        )
        scaleComparisonView.addSubview(scaleComparisonControl)
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
        closeScaleComparison()
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
