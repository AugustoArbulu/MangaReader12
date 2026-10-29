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
    private let cache = NSCache<NSString, UIImage>()

    init(manifest: SourceManifest) {
        client = HTTPClient(
            policy: HTTPPolicy(
                allowedDomains: manifest.domains,
                timeout: 25,
                maxRedirects: 5,
                maxResponseBytes: 20 * 1024 * 1024
            )
        )
        cache.countLimit = 12
    }

    func load(
        page: Page,
        completion: @escaping (Result<UIImage, Error>) -> Void
    ) {
        let key = page.imageUrl as NSString

        if let cached = cache.object(forKey: key) {
            completion(.success(cached))
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

                self?.cache.setObject(image, forKey: key)
                completion(.success(image))

            case .failure(let error):
                completion(.failure(error))
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
    }

    override func layoutSubviews() {
        super.layoutSubviews()
        zoomScrollView.frame = contentView.bounds
        imageView.frame = zoomScrollView.bounds
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
        imageLoaded: @escaping (UIImage) -> Void
    ) {
        representedURL = page.imageUrl
        imageView.image = nil
        errorLabel.isHidden = true
        zoomScrollView.zoomScale = 1
        zoomScrollView.maximumZoomScale = zoomEnabled ? 4 : 1
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
                    imageLoaded(image)

                case .failure(let error):
                    self.errorLabel.text = error.localizedDescription
                    self.errorLabel.isHidden = false
                }
            }
        }
    }

    func viewForZooming(in scrollView: UIScrollView) -> UIView? {
        return imageView
    }
}

final class ReaderViewController: UIViewController,
    UICollectionViewDataSource,
    UICollectionViewDelegateFlowLayout,
    UIScrollViewDelegate {

    private let chapter: Chapter
    private let pages: [Page]
    private let imageLoader: ReaderImageLoader
    private let layout = UICollectionViewFlowLayout()
    private lazy var collectionView = UICollectionView(
        frame: .zero,
        collectionViewLayout: layout
    )
    private let modeControl = UISegmentedControl(items: ["Páginas", "Webtoon"])
    private var displayMode: ReaderDisplayMode = .pages
    private var aspectRatios: [Int: CGFloat] = [:]

    init(
        chapter: Chapter,
        pages: [Page],
        manifest: SourceManifest
    ) {
        self.chapter = chapter
        self.pages = pages
        self.imageLoader = ReaderImageLoader(manifest: manifest)
        super.init(nibName: nil, bundle: nil)
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = chapter.name
        view.backgroundColor = .black

        layout.minimumLineSpacing = 0
        layout.minimumInteritemSpacing = 0
        layout.scrollDirection = .horizontal

        collectionView.translatesAutoresizingMaskIntoConstraints = false
        collectionView.backgroundColor = .black
        collectionView.dataSource = self
        collectionView.delegate = self
        collectionView.isPagingEnabled = true
        collectionView.showsHorizontalScrollIndicator = false
        collectionView.showsVerticalScrollIndicator = false
        collectionView.register(
            ReaderPageCell.self,
            forCellWithReuseIdentifier: ReaderPageCell.reuseIdentifier
        )
        view.addSubview(collectionView)

        NSLayoutConstraint.activate([
            collectionView.topAnchor.constraint(equalTo: view.topAnchor),
            collectionView.leadingAnchor.constraint(equalTo: view.leadingAnchor),
            collectionView.trailingAnchor.constraint(equalTo: view.trailingAnchor),
            collectionView.bottomAnchor.constraint(equalTo: view.bottomAnchor)
        ])

        modeControl.selectedSegmentIndex = ReaderDisplayMode.pages.rawValue
        modeControl.addTarget(
            self,
            action: #selector(modeChanged),
            for: .valueChanged
        )
        navigationItem.titleView = modeControl

        updatePagePrompt()
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        layout.invalidateLayout()
    }

    @objc private func modeChanged() {
        displayMode = ReaderDisplayMode(rawValue: modeControl.selectedSegmentIndex) ?? .pages

        layout.scrollDirection = displayMode == .pages ? .horizontal : .vertical
        collectionView.isPagingEnabled = displayMode == .pages
        collectionView.setContentOffset(.zero, animated: false)
        collectionView.reloadData()
        layout.invalidateLayout()
        updatePagePrompt()
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
        cell.configure(
            page: page,
            loader: imageLoader,
            zoomEnabled: displayMode == .pages
        ) { [weak self] image in
            guard let self = self,
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
    }

    func scrollViewDidScroll(_ scrollView: UIScrollView) {
        if displayMode == .webtoon {
            updatePagePrompt()
        }
    }

    private func updatePagePrompt() {
        guard !pages.isEmpty else {
            navigationItem.prompt = "0 páginas"
            return
        }

        let index: Int

        if displayMode == .pages {
            let width = max(1, collectionView.bounds.width)
            index = min(
                pages.count - 1,
                max(0, Int(round(collectionView.contentOffset.x / width)))
            )
        } else {
            let visible = collectionView.indexPathsForVisibleItems
                .sorted { $0.item < $1.item }
            index = visible.first?.item ?? 0
        }

        navigationItem.prompt = "\(index + 1) / \(pages.count)"
    }
}
