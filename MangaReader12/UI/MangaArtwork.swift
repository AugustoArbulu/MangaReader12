import UIKit

final class CoverImageLoader {
    static let shared = CoverImageLoader()

    private let memoryCache = NSCache<NSString, UIImage>()
    private let fileManager: FileManager
    private let cacheDirectory: URL?
    private let queue = DispatchQueue(label: "com.mangareader12.cover-cache", qos: .utility)

    private init(fileManager: FileManager = .default) {
        self.fileManager = fileManager
        memoryCache.countLimit = 120

        if let base = fileManager.urls(for: .cachesDirectory, in: .userDomainMask).first {
            let directory = base
                .appendingPathComponent("MangaReader12", isDirectory: true)
                .appendingPathComponent("CoverCache", isDirectory: true)

            try? fileManager.createDirectory(
                at: directory,
                withIntermediateDirectories: true,
                attributes: nil
            )
            cacheDirectory = directory
        } else {
            cacheDirectory = nil
        }
    }

    func load(
        urlString: String?,
        allowedDomains: [String],
        completion: @escaping (UIImage?) -> Void
    ) {
        guard let raw = urlString,
              let url = URL(string: raw),
              let host = url.host else {
            completion(nil)
            return
        }

        let key = raw as NSString

        if let image = memoryCache.object(forKey: key) {
            completion(image)
            return
        }

        if let diskURL = cacheURL(for: raw),
           let data = try? Data(contentsOf: diskURL),
           let image = UIImage(data: data) {
            memoryCache.setObject(image, forKey: key)
            completion(image)
            return
        }

        let domains = allowedDomains.isEmpty ? [host] : allowedDomains
        let client = HTTPClient(
            policy: HTTPPolicy(
                allowedDomains: domains,
                timeout: 20,
                maxRedirects: 5,
                maxResponseBytes: 6 * 1024 * 1024
            )
        )

        client.send(HTTPRequest(url: raw)) { [weak self] result in
            switch result {
            case .success(let response):
                guard (200..<300).contains(response.statusCode),
                      let image = UIImage(data: response.data) else {
                    DispatchQueue.main.async { completion(nil) }
                    return
                }

                self?.memoryCache.setObject(image, forKey: key)

                if let diskURL = self?.cacheURL(for: raw) {
                    self?.queue.async {
                        try? response.data.write(to: diskURL, options: .atomic)
                    }
                }

                DispatchQueue.main.async {
                    completion(image)
                }

            case .failure:
                DispatchQueue.main.async {
                    completion(nil)
                }
            }
        }
    }

    func clearDiskCache() {
        guard let directory = cacheDirectory else { return }

        queue.async {
            if let files = try? self.fileManager.contentsOfDirectory(
                at: directory,
                includingPropertiesForKeys: nil,
                options: [.skipsHiddenFiles]
            ) {
                for file in files {
                    try? self.fileManager.removeItem(at: file)
                }
            }
            self.memoryCache.removeAllObjects()
        }
    }

    private func cacheURL(for value: String) -> URL? {
        guard let directory = cacheDirectory else { return nil }
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
}

final class MangaCoverCell: UITableViewCell {
    static let reuseIdentifier = "MangaCoverCell"

    private let coverView = UIImageView()
    private let titleView = UILabel()
    private let subtitleView = UILabel()
    private let badgeView = UILabel()
    private var representedURL: String?

    override init(style: UITableViewCell.CellStyle, reuseIdentifier: String?) {
        super.init(style: style, reuseIdentifier: reuseIdentifier)

        coverView.translatesAutoresizingMaskIntoConstraints = false
        coverView.contentMode = .scaleAspectFill
        coverView.clipsToBounds = true
        coverView.layer.cornerRadius = 5
        coverView.backgroundColor = UIColor(white: 0.25, alpha: 1)

        titleView.translatesAutoresizingMaskIntoConstraints = false
        titleView.font = UIFont.systemFont(ofSize: 16, weight: .semibold)
        titleView.numberOfLines = 2

        subtitleView.translatesAutoresizingMaskIntoConstraints = false
        subtitleView.font = UIFont.systemFont(ofSize: 12.5)
        subtitleView.numberOfLines = 2

        badgeView.translatesAutoresizingMaskIntoConstraints = false
        badgeView.font = UIFont.systemFont(ofSize: 10, weight: .semibold)
        badgeView.textAlignment = .center
        badgeView.layer.cornerRadius = 5
        badgeView.clipsToBounds = true
        badgeView.isHidden = true

        contentView.addSubview(coverView)
        contentView.addSubview(titleView)
        contentView.addSubview(subtitleView)
        contentView.addSubview(badgeView)

        NSLayoutConstraint.activate([
            coverView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 12),
            coverView.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 8),
            coverView.bottomAnchor.constraint(lessThanOrEqualTo: contentView.bottomAnchor, constant: -8),
            coverView.widthAnchor.constraint(equalToConstant: 58),
            coverView.heightAnchor.constraint(equalToConstant: 84),

            titleView.leadingAnchor.constraint(equalTo: coverView.trailingAnchor, constant: 12),
            titleView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -34),
            titleView.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 12),

            subtitleView.leadingAnchor.constraint(equalTo: titleView.leadingAnchor),
            subtitleView.trailingAnchor.constraint(equalTo: titleView.trailingAnchor),
            subtitleView.topAnchor.constraint(equalTo: titleView.bottomAnchor, constant: 6),
            subtitleView.bottomAnchor.constraint(lessThanOrEqualTo: contentView.bottomAnchor, constant: -12),

            badgeView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -12),
            badgeView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -10),
            badgeView.heightAnchor.constraint(equalToConstant: 20),
            badgeView.widthAnchor.constraint(greaterThanOrEqualToConstant: 42)
        ])
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func prepareForReuse() {
        super.prepareForReuse()
        representedURL = nil
        coverView.image = nil
        badgeView.isHidden = true
        badgeView.text = nil
    }

    func configure(
        title: String,
        subtitle: String?,
        coverURL: String?,
        allowedDomains: [String],
        badge: String? = nil
    ) {
        titleView.text = title
        subtitleView.text = subtitle
        representedURL = coverURL
        coverView.image = nil

        if let badge = badge, !badge.isEmpty {
            badgeView.text = "  \(badge)  "
            badgeView.isHidden = false
        } else {
            badgeView.isHidden = true
        }

        applyPalette()

        guard coverURL != nil else {
            coverView.image = nil
            return
        }

        CoverImageLoader.shared.load(
            urlString: coverURL,
            allowedDomains: allowedDomains
        ) { [weak self] image in
            guard let self = self,
                  self.representedURL == coverURL else {
                return
            }
            self.coverView.image = image
        }
    }

    func applyPalette() {
        let colors = ThemeManager.shared.palette
        backgroundColor = colors.cellBackground
        contentView.backgroundColor = colors.cellBackground
        titleView.textColor = colors.primaryText
        subtitleView.textColor = colors.secondaryText
        badgeView.backgroundColor = colors.accent
        badgeView.textColor = .white
        tintColor = colors.accent

        let selected = UIView()
        selected.backgroundColor = ThemeManager.shared.isDark
            ? UIColor(white: 0.20, alpha: 1)
            : UIColor(white: 0.90, alpha: 1)
        selectedBackgroundView = selected
    }
}

final class MangaDetailsHeaderCell: UITableViewCell {
    static let reuseIdentifier = "MangaDetailsHeaderCell"

    private let coverView = UIImageView()
    private let titleView = UILabel()
    private let metaView = UILabel()
    private let genresView = UILabel()
    private let descriptionView = UILabel()
    private var representedURL: String?

    override init(style: UITableViewCell.CellStyle, reuseIdentifier: String?) {
        super.init(style: style, reuseIdentifier: reuseIdentifier)

        selectionStyle = .none

        coverView.translatesAutoresizingMaskIntoConstraints = false
        coverView.contentMode = .scaleAspectFill
        coverView.clipsToBounds = true
        coverView.layer.cornerRadius = 7
        coverView.backgroundColor = UIColor(white: 0.25, alpha: 1)

        titleView.translatesAutoresizingMaskIntoConstraints = false
        titleView.font = UIFont.systemFont(ofSize: 20, weight: .bold)
        titleView.numberOfLines = 3

        metaView.translatesAutoresizingMaskIntoConstraints = false
        metaView.font = UIFont.systemFont(ofSize: 13)
        metaView.numberOfLines = 4

        genresView.translatesAutoresizingMaskIntoConstraints = false
        genresView.font = UIFont.systemFont(ofSize: 12, weight: .medium)
        genresView.numberOfLines = 3

        descriptionView.translatesAutoresizingMaskIntoConstraints = false
        descriptionView.font = UIFont.systemFont(ofSize: 13.5)
        descriptionView.numberOfLines = 0

        contentView.addSubview(coverView)
        contentView.addSubview(titleView)
        contentView.addSubview(metaView)
        contentView.addSubview(genresView)
        contentView.addSubview(descriptionView)

        NSLayoutConstraint.activate([
            coverView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 14),
            coverView.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 14),
            coverView.widthAnchor.constraint(equalToConstant: 108),
            coverView.heightAnchor.constraint(equalToConstant: 158),

            titleView.leadingAnchor.constraint(equalTo: coverView.trailingAnchor, constant: 14),
            titleView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -14),
            titleView.topAnchor.constraint(equalTo: coverView.topAnchor),

            metaView.leadingAnchor.constraint(equalTo: titleView.leadingAnchor),
            metaView.trailingAnchor.constraint(equalTo: titleView.trailingAnchor),
            metaView.topAnchor.constraint(equalTo: titleView.bottomAnchor, constant: 8),

            genresView.leadingAnchor.constraint(equalTo: titleView.leadingAnchor),
            genresView.trailingAnchor.constraint(equalTo: titleView.trailingAnchor),
            genresView.topAnchor.constraint(equalTo: metaView.bottomAnchor, constant: 8),

            descriptionView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 14),
            descriptionView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -14),
            descriptionView.topAnchor.constraint(greaterThanOrEqualTo: coverView.bottomAnchor, constant: 14),
            descriptionView.topAnchor.constraint(greaterThanOrEqualTo: genresView.bottomAnchor, constant: 14),
            descriptionView.bottomAnchor.constraint(equalTo: contentView.bottomAnchor, constant: -16)
        ])
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    func configure(
        manga: Manga?,
        fallback: SourceMangaSummary,
        allowedDomains: [String]
    ) {
        let valueTitle = manga?.title ?? fallback.title
        let coverURL = manga?.cover ?? fallback.cover

        titleView.text = valueTitle
        representedURL = coverURL
        coverView.image = nil

        if let manga = manga {
            var meta: [String] = []
            if let author = manga.author, !author.isEmpty {
                meta.append("Autor: \(author)")
            }
            if let artist = manga.artist, !artist.isEmpty, artist != manga.author {
                meta.append("Artista: \(artist)")
            }
            meta.append("Status: \(manga.status.rawValue)")
            metaView.text = meta.joined(separator: "\n")
            genresView.text = manga.genres.isEmpty
                ? nil
                : manga.genres.joined(separator: " • ")
            descriptionView.text = manga.description
        } else {
            metaView.text = "Carregando detalhes…"
            genresView.text = nil
            descriptionView.text = nil
        }

        applyPalette()

        CoverImageLoader.shared.load(
            urlString: coverURL,
            allowedDomains: allowedDomains
        ) { [weak self] image in
            guard let self = self,
                  self.representedURL == coverURL else {
                return
            }
            self.coverView.image = image
        }
    }

    func applyPalette() {
        let colors = ThemeManager.shared.palette
        backgroundColor = colors.cellBackground
        contentView.backgroundColor = colors.cellBackground
        titleView.textColor = colors.primaryText
        metaView.textColor = colors.secondaryText
        genresView.textColor = colors.accent
        descriptionView.textColor = colors.primaryText
    }
}


final class SourceIconCell: UITableViewCell {
    static let reuseIdentifier = "SourceIconCell"

    private let iconView = UIImageView()
    private let fallbackLabel = UILabel()
    private let titleView = UILabel()
    private let subtitleView = UILabel()
    private var representedURL: String?

    override init(style: UITableViewCell.CellStyle, reuseIdentifier: String?) {
        super.init(style: style, reuseIdentifier: reuseIdentifier)

        iconView.translatesAutoresizingMaskIntoConstraints = false
        iconView.contentMode = .scaleAspectFill
        iconView.clipsToBounds = true
        iconView.layer.cornerRadius = 9
        iconView.backgroundColor = UIColor(white: 0.22, alpha: 1)

        fallbackLabel.translatesAutoresizingMaskIntoConstraints = false
        fallbackLabel.font = UIFont.systemFont(ofSize: 15, weight: .bold)
        fallbackLabel.textAlignment = .center
        fallbackLabel.adjustsFontSizeToFitWidth = true
        fallbackLabel.minimumScaleFactor = 0.7
        iconView.addSubview(fallbackLabel)

        titleView.translatesAutoresizingMaskIntoConstraints = false
        titleView.font = UIFont.systemFont(ofSize: 16, weight: .semibold)
        titleView.numberOfLines = 1

        subtitleView.translatesAutoresizingMaskIntoConstraints = false
        subtitleView.font = UIFont.systemFont(ofSize: 12.5)
        subtitleView.numberOfLines = 2

        contentView.addSubview(iconView)
        contentView.addSubview(titleView)
        contentView.addSubview(subtitleView)

        NSLayoutConstraint.activate([
            iconView.leadingAnchor.constraint(equalTo: contentView.leadingAnchor, constant: 12),
            iconView.centerYAnchor.constraint(equalTo: contentView.centerYAnchor),
            iconView.widthAnchor.constraint(equalToConstant: 46),
            iconView.heightAnchor.constraint(equalToConstant: 46),

            fallbackLabel.leadingAnchor.constraint(equalTo: iconView.leadingAnchor, constant: 4),
            fallbackLabel.trailingAnchor.constraint(equalTo: iconView.trailingAnchor, constant: -4),
            fallbackLabel.topAnchor.constraint(equalTo: iconView.topAnchor, constant: 4),
            fallbackLabel.bottomAnchor.constraint(equalTo: iconView.bottomAnchor, constant: -4),

            titleView.leadingAnchor.constraint(equalTo: iconView.trailingAnchor, constant: 12),
            titleView.trailingAnchor.constraint(equalTo: contentView.trailingAnchor, constant: -34),
            titleView.topAnchor.constraint(equalTo: contentView.topAnchor, constant: 11),

            subtitleView.leadingAnchor.constraint(equalTo: titleView.leadingAnchor),
            subtitleView.trailingAnchor.constraint(equalTo: titleView.trailingAnchor),
            subtitleView.topAnchor.constraint(equalTo: titleView.bottomAnchor, constant: 4),
            subtitleView.bottomAnchor.constraint(lessThanOrEqualTo: contentView.bottomAnchor, constant: -10)
        ])

        applyPalette()
    }

    required init?(coder: NSCoder) {
        fatalError("init(coder:) has not been implemented")
    }

    override func prepareForReuse() {
        super.prepareForReuse()
        representedURL = nil
        iconView.image = nil
        fallbackLabel.isHidden = false
    }

    func configure(
        title: String,
        subtitle: String?,
        iconURL: String?
    ) {
        titleView.text = title
        subtitleView.text = subtitle
        representedURL = iconURL
        iconView.image = nil
        fallbackLabel.text = initials(for: title)
        fallbackLabel.isHidden = false
        applyPalette()

        CoverImageLoader.shared.load(
            urlString: iconURL,
            allowedDomains: []
        ) { [weak self] image in
            guard let self = self,
                  self.representedURL == iconURL else {
                return
            }

            if let image = image {
                self.iconView.image = image
                self.fallbackLabel.isHidden = true
            }
        }
    }

    func applyPalette() {
        let colors = ThemeManager.shared.palette
        backgroundColor = colors.cellBackground
        contentView.backgroundColor = colors.cellBackground
        titleView.textColor = colors.primaryText
        subtitleView.textColor = colors.secondaryText
        fallbackLabel.textColor = .white
        iconView.backgroundColor = colors.accent
        tintColor = colors.accent

        let selected = UIView()
        selected.backgroundColor = ThemeManager.shared.isDark
            ? UIColor(white: 0.20, alpha: 1)
            : UIColor(white: 0.90, alpha: 1)
        selectedBackgroundView = selected
    }

    private func initials(for title: String) -> String {
        let parts = title
            .split(separator: " ")
            .prefix(2)

        let value = parts.compactMap { $0.first }.map { String($0) }.joined()
        return value.isEmpty ? "S" : value.uppercased()
    }
}
