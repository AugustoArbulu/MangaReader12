import UIKit
import ImageIO

// BEGIN IMAGE_RESPONSE_DIAGNOSTICS
// Safe, content-based diagnosis. Never include URL paths/queries, headers
// other than sanitized MIME, body content, credentials, cookies or tokens.
enum ImageResponseDiagnostics {
    static func format(_ data: Data) -> String {
        if data.count >= 12 {
            let b = [UInt8](data.prefix(12))
            if b[0...3].elementsEqual([82, 73, 70, 70]) &&
                b[8...11].elementsEqual([87, 69, 66, 80]) { return "WebP" }
            if b[4...7].elementsEqual([102, 116, 121, 112]) {
                if b[8...11].elementsEqual([97, 118, 105, 102]) ||
                    b[8...11].elementsEqual([97, 118, 105, 115]) { return "AVIF" }
                if b[8...11].elementsEqual([104, 101, 105, 99]) ||
                    b[8...11].elementsEqual([104, 101, 105, 120]) { return "HEIC" }
            }
        }
        if data.starts(with: [0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A]) {
            return "PNG"
        }
        if data.starts(with: [0xFF, 0xD8, 0xFF]) { return "JPEG" }
        if data.starts(with: [71, 73, 70, 56]) { return "GIF" }
        if data.starts(with: [37, 80, 68, 70]) { return "PDF" }
        if data.isEmpty { return "empty" }
        // Examine only the first 64 bytes; never include the content.
        let prefix = String(data: data.prefix(64), encoding: .utf8)?
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased() ?? ""
        if prefix.hasPrefix("<!doctype html") || prefix.hasPrefix("<html") ||
            prefix.hasPrefix("<head") || prefix.hasPrefix("<body") { return "HTML" }
        if prefix.hasPrefix("<?xml") { return "XML" }
        if prefix.hasPrefix("{") || prefix.hasPrefix("[") { return "JSON-like" }
        return "unrecognized"
    }

    static func mime(_ headers: [String: String]) -> String {
        guard let raw = headers.first(where: {
            $0.key.caseInsensitiveCompare("content-type") == .orderedSame
        })?.value else { return "(missing)" }
        let value = raw.components(separatedBy: ";").first?
            .trimmingCharacters(in: .whitespacesAndNewlines).lowercased() ?? ""
        // Permit only innocuous MIME syntax. Never reflect arbitrary header text.
        guard value.count > 0, value.count <= 64,
              value.range(of: "^[a-z0-9.+_-]+/[a-z0-9.+_-]+$",
                          options: .regularExpression) != nil else {
            return "(invalid)"
        }
        return value
    }

    static func host(_ url: String) -> String {
        guard let parsed = URLComponents(string: url),
              parsed.scheme?.lowercased() == "https",
              let host = parsed.host?.lowercased(),
              host.range(of: "^[a-z0-9.-]{1,253}$",
                         options: .regularExpression) != nil else {
            return "(invalid)"
        }
        return host
    }

    static func summary(data: Data, headers: [String: String], status: Int,
                        url: String) -> String {
        return "HTTP " + String(status) + ", formato=" + format(data) +
            ", MIME=" + mime(headers) + ", bytes=" + String(data.count) +
            ", host=" + host(url)
    }
}
// END IMAGE_RESPONSE_DIAGNOSTICS

// BEGIN WEBP_IMAGE_DECODER
// WebP is not decoded by iOS 12 UIImage/ImageIO. Use libwebp's C decoder,
// statically linked for iOS 12.0, with hard limits on compressed bytes and
// decoded pixels. No remote fetches, WAF/session state or URL manipulation.
enum WebPImageDecoder {
    private static let maxInputBytes = 20 * 1024 * 1024
    static let maximumReaderPixels = 24_000_000
    static let maximumCoverPixels = 4_000_000

    static func isWebP(_ data: Data) -> Bool {
        return ImageResponseDiagnostics.format(data) == "WebP"
    }

    static func image(from data: Data, maxPixels: Int = maximumReaderPixels) -> UIImage? {
        guard isWebP(data) else { return UIImage(data: data) }
        guard data.count >= 20, data.count <= maxInputBytes,
              maxPixels >= 1 else { return nil }
        var width: Int32 = 0
        var height: Int32 = 0
        let recognized: Bool = data.withUnsafeBytes { raw in
            guard let input = raw.baseAddress?.assumingMemoryBound(to: UInt8.self) else {
                return false
            }
            return WebPGetInfo(input, data.count, &width, &height) == 1
        }
        guard recognized, width > 0, height > 0,
              width <= 100_000, height <= 100_000 else { return nil }

        // Avoid integer overflow and unbounded allocations on older iPads.
        let w = Int(width), h = Int(height)
        guard w <= maxPixels / h, w <= Int(Int32.max) / 4 else { return nil }
        let stride = w * 4
        let totalBytes = stride * h
        guard totalBytes <= maxPixels * 4 else { return nil }

        // Explicit BGRA output avoids libwebp's implicit large allocations.
        // The decoder writes into this Swift-owned bounded buffer.
        var pixels = Data(count: totalBytes)
        let decoded: Bool = pixels.withUnsafeMutableBytes { destination in
            guard let output = destination.baseAddress?
                .assumingMemoryBound(to: UInt8.self) else { return false }
            return data.withUnsafeBytes { source in
                guard let input = source.baseAddress?
                    .assumingMemoryBound(to: UInt8.self) else { return false }
                return WebPDecodeBGRAInto(input, data.count, output,
                                         totalBytes, Int32(stride)) != nil
            }
        }
        guard decoded else { return nil }

        // CGImage/Quartz expects premultiplied BGRA on iOS 12. WebP's
        // BGRAInto writes straight-alpha samples; premultiply explicitly.
        pixels.withUnsafeMutableBytes { buffer in
            guard let bytes = buffer.baseAddress?.assumingMemoryBound(to: UInt8.self)
                else { return }
            for i in Swift.stride(from: 0, to: totalBytes, by: 4) {
                let alpha = Int(bytes[i + 3])
                if alpha < 255 {
                    bytes[i] = UInt8((Int(bytes[i]) * alpha + 127) / 255)
                    bytes[i + 1] = UInt8((Int(bytes[i + 1]) * alpha + 127) / 255)
                    bytes[i + 2] = UInt8((Int(bytes[i + 2]) * alpha + 127) / 255)
                }
            }
        }
        guard let provider = CGDataProvider(data: pixels as CFData),
              let cgImage = CGImage(
                width: w, height: h,
                bitsPerComponent: 8, bitsPerPixel: 32,
                bytesPerRow: stride, space: CGColorSpaceCreateDeviceRGB(),
                bitmapInfo: CGBitmapInfo.byteOrder32Little.union(
                    CGBitmapInfo(rawValue: CGImageAlphaInfo.premultipliedFirst.rawValue)
                ), provider: provider, decode: nil,
                shouldInterpolate: true, intent: .defaultIntent
              ) else { return nil }
        return UIImage(cgImage: cgImage)
    }
}
// END WEBP_IMAGE_DECODER

// A bounded thumbnail pipeline for older iOS devices. One HTTP client per
// active transfer is retained until completion; at most three are active.
// Identical URLs under identical host policies share a single fetch.
final class CoverImageLoader {
    static let shared = CoverImageLoader()

    private struct PendingCover {
        let key: String
        let url: String
        let policy: HTTPPolicy
        let generation: UInt64
    }

    private let memoryCache = NSCache<NSString, UIImage>()
    private let fileManager: FileManager
    private let cacheDirectory: URL?
    private let workQueue = DispatchQueue(label: "com.mangareader12.cover-cache", qos: .utility)
    private let maxConcurrentTransfers = 3

    // All mutable scheduling state belongs exclusively to workQueue.
    private var pending: [PendingCover] = []
    private var activeClients: [String: HTTPClient] = [:]
    private var waiting: [String: [(UIImage?) -> Void]] = [:]
    private var cacheGeneration: UInt64 = 0

    private init(fileManager: FileManager = .default) {
        self.fileManager = fileManager
        memoryCache.countLimit = 120
        memoryCache.totalCostLimit = 24 * 1024 * 1024

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
            DispatchQueue.main.async { completion(nil) }
            return
        }

        // Validate every caller before looking up any cache or joining
        // an existing request. The policy scope is part of the cache key,
        // so permissive sources cannot populate stricter sources' caches.
        let domains = allowedDomains.isEmpty ? [host] : allowedDomains
        let policy = HTTPPolicy(
            allowedDomains: domains,
            timeout: 20,
            maxRedirects: 5,
            maxResponseBytes: 6 * 1024 * 1024
        )
        guard policy.isURLAllowed(url) else {
            DispatchQueue.main.async { completion(nil) }
            return
        }

        let key = cacheKey(for: raw, domains: domains)
        if let image = memoryCache.object(forKey: key as NSString) {
            DispatchQueue.main.async { completion(image) }
            return
        }

        // Avoid Data(contentsOf:), JPEG decode, and cache file operations on
        // the UIKit table-view path; these can stall scrolling on iOS 12.
        workQueue.async {
            if let image = self.memoryCache.object(forKey: key as NSString) {
                self.deliver(image, completions: [completion])
                return
            }

            if let diskURL = self.cacheURL(for: key),
               let data = try? Data(contentsOf: diskURL),
               let image = self.decodeCover(data) {
                self.remember(image, for: key)
                self.deliver(image, completions: [completion])
                return
            }

            if self.waiting[key] != nil {
                self.waiting[key]?.append(completion)
                return
            }

            self.waiting[key] = [completion]
            self.pending.append(PendingCover(
                key: key,
                url: raw,
                policy: policy,
                generation: self.cacheGeneration
            ))
            self.startPendingTransfers()
        }
    }

    // Called only on workQueue. No unbounded independent URLSession bursts.
    private func startPendingTransfers() {
        while activeClients.count < maxConcurrentTransfers && !pending.isEmpty {
            let next = pending.removeFirst()
            let client = HTTPClient(policy: next.policy)
            activeClients[next.key] = client

            client.send(HTTPRequest(url: next.url)) { [weak self] result in
                guard let self = self else { return }
                self.workQueue.async {
                    self.finish(next, result: result)
                }
            }
        }
    }

    // Called only on workQueue. Failed/403/429 responses are never cached as
    // images, and there are no automatic retries or alternate-host requests.
    private func finish(
        _ request: PendingCover,
        result: Result<HTTPResponse, Error>
    ) {
        activeClients.removeValue(forKey: request.key)
        var image: UIImage?

        if case .success(let response) = result,
           (200..<300).contains(response.statusCode) {
            image = decodeCover(response.data)
            if let image = image, request.generation == cacheGeneration {
                remember(image, for: request.key)
                if let diskURL = cacheURL(for: request.key) {
                    try? response.data.write(to: diskURL, options: .atomic)
                }
            }
        }

        if let completions = waiting.removeValue(forKey: request.key) {
            deliver(image, completions: completions)
        }
        startPendingTransfers()
    }

    // Draw only a thumbnail. A single full-size cover image can otherwise
    // consume substantial RAM after decompression on older devices.
    private func decodeCover(_ data: Data) -> UIImage? {
        // Bounded WebP decode; do not force iOS 12 ImageIO to parse WebP.
        if WebPImageDecoder.isWebP(data) {
            guard let image = WebPImageDecoder.image(
                from: data, maxPixels: WebPImageDecoder.maximumCoverPixels
            ) else { return nil }
            let fullPixels = image.size.width * image.size.height
            if fullPixels <= 420 * 420 { return image }
            // Downscale the already bounded image for the list's memory cache.
            let ratio = min(420 / image.size.width, 420 / image.size.height)
            let target = CGSize(width: max(1, image.size.width * ratio),
                                height: max(1, image.size.height * ratio))
            UIGraphicsBeginImageContextWithOptions(target, false, 1)
            image.draw(in: CGRect(origin: .zero, size: target))
            let thumbnail = UIGraphicsGetImageFromCurrentImageContext()
            UIGraphicsEndImageContext()
            return thumbnail ?? image
        }
        guard let source = CGImageSourceCreateWithData(data as CFData, nil) else {
            return UIImage(data: data)
        }
        let options: [CFString: Any] = [
            kCGImageSourceCreateThumbnailFromImageAlways: true,
            kCGImageSourceCreateThumbnailWithTransform: true,
            kCGImageSourceShouldCacheImmediately: true,
            kCGImageSourceThumbnailMaxPixelSize: 420
        ]
        if let cgImage = CGImageSourceCreateThumbnailAtIndex(
            source, 0, options as CFDictionary
        ) {
            return UIImage(cgImage: cgImage)
        }
        return UIImage(data: data)
    }

    private func remember(_ image: UIImage, for key: String) {
        let width = min(5000, max(1, Int(image.size.width * image.scale)))
        let height = min(5000, max(1, Int(image.size.height * image.scale)))
        memoryCache.setObject(
            image,
            forKey: key as NSString,
            cost: width * height * 4
        )
    }

    private func deliver(
        _ image: UIImage?,
        completions: [(UIImage?) -> Void]
    ) {
        DispatchQueue.main.async {
            for completion in completions {
                completion(image)
            }
        }
    }

    func clearDiskCache() {
        workQueue.async {
            // Prevent a request that predates cache clearing from repopulating
            // it after the user explicitly cleared all covers.
            self.cacheGeneration &+= 1
            self.memoryCache.removeAllObjects()
            guard let directory = self.cacheDirectory else { return }
            if let files = try? self.fileManager.contentsOfDirectory(
                at: directory,
                includingPropertiesForKeys: nil,
                options: [.skipsHiddenFiles]
            ) {
                for file in files {
                    try? self.fileManager.removeItem(at: file)
                }
            }
        }
    }

    private func cacheURL(for value: String) -> URL? {
        guard let directory = cacheDirectory else { return nil }
        return directory.appendingPathComponent(stableKey(value) + ".bin")
    }

    private func cacheKey(for url: String, domains: [String]) -> String {
        let scope = domains.map { $0.lowercased() }.sorted().joined(separator: ",")
        return url + "\u{0}" + scope
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
