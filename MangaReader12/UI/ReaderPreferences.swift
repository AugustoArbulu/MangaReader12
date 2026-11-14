import Foundation

enum ReaderPageDirection: Int {
    case leftToRight = 0
    case rightToLeft = 1

    var title: String {
        switch self {
        case .leftToRight:
            return "Esquerda → Direita"
        case .rightToLeft:
            return "Direita → Esquerda"
        }
    }
}

enum ReaderBackgroundStyle: Int {
    case black = 0
    case gray = 1
    case white = 2

    var title: String {
        switch self {
        case .black:
            return "Preto"
        case .gray:
            return "Cinza"
        case .white:
            return "Branco"
        }
    }
}

enum ReaderScaleMode: Int {
    case fitScreen = 0
    case fitWidth = 1
    case fitHeight = 2
    case original = 3

    var title: String {
        switch self {
        case .fitScreen: return "Ajustar à tela"
        case .fitWidth: return "Ajustar à largura"
        case .fitHeight: return "Ajustar à altura"
        case .original: return "Tamanho original"
        }
    }
}

// Width of the continuous Webtoon strip, independent of paged-reader zoom.
// Fraction is based on the actual reader viewport, not the full device screen.
enum ReaderWebtoonWidth: Int {
    case adaptive = 0
    case full = 1
    case wide = 2
    case comfortable = 3
    case narrow = 4

    var title: String {
        switch self {
        case .adaptive: return "Adaptável (100% em pé, 75% deitado)"
        case .full: return "100% (largura total)"
        case .wide: return "85%"
        case .comfortable: return "75%"
        case .narrow: return "60%"
        }
    }

    var shortTitle: String {
        switch self {
        case .adaptive: return "Adaptável"
        case .full: return "100%"
        case .wide: return "85%"
        case .comfortable: return "75%"
        case .narrow: return "60%"
        }
    }

    func fraction(for viewport: CGSize) -> CGFloat {
        switch self {
        case .adaptive:
            // Portrait retains the exact Build69 rendering width. Landscape
            // narrows the tall-strip art instead of stretching it to the iPad.
            return viewport.width > viewport.height ? 0.75 : 1.0
        case .full: return 1.0
        case .wide: return 0.85
        case .comfortable: return 0.75
        case .narrow: return 0.60
        }
    }
}

final class ReaderPreferences {
    static let shared = ReaderPreferences()

    private let defaults: UserDefaults
    private let modeKey = "reader.mode"
    private let directionKey = "reader.pageDirection"
    private let backgroundKey = "reader.background"
    private let showPageNumberKey = "reader.showPageNumber"
    private let keepScreenOnKey = "reader.keepScreenOn"
    private let tapZonesKey = "reader.tapZones"
    private let webtoonGapKey = "reader.webtoonGap"
    private let webtoonWidthKey = "reader.webtoon.widthMode"
    private let doubleTapZoomKey = "reader.doubleTapZoom"
    private let scaleModeKey = "reader.scaleMode"
    private let trimMarginsKey = "reader.trimMargins"
    private let preloadNextChapterKey = "reader.preloadNextChapter"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    var displayMode: ReaderDisplayMode {
        get {
            return ReaderDisplayMode(
                rawValue: defaults.integer(forKey: modeKey)
            ) ?? .pages
        }
        set {
            defaults.set(newValue.rawValue, forKey: modeKey)
        }
    }

    var pageDirection: ReaderPageDirection {
        get {
            return ReaderPageDirection(
                rawValue: defaults.integer(forKey: directionKey)
            ) ?? .leftToRight
        }
        set {
            defaults.set(newValue.rawValue, forKey: directionKey)
        }
    }

    var backgroundStyle: ReaderBackgroundStyle {
        get {
            return ReaderBackgroundStyle(
                rawValue: defaults.integer(forKey: backgroundKey)
            ) ?? .black
        }
        set {
            defaults.set(newValue.rawValue, forKey: backgroundKey)
        }
    }

    var showPageNumber: Bool {
        get { return bool(forKey: showPageNumberKey, defaultValue: true) }
        set { defaults.set(newValue, forKey: showPageNumberKey) }
    }

    var keepScreenOn: Bool {
        get { return bool(forKey: keepScreenOnKey, defaultValue: true) }
        set { defaults.set(newValue, forKey: keepScreenOnKey) }
    }

    var tapZonesEnabled: Bool {
        get { return bool(forKey: tapZonesKey, defaultValue: true) }
        set { defaults.set(newValue, forKey: tapZonesKey) }
    }

    var webtoonGapEnabled: Bool {
        get { return bool(forKey: webtoonGapKey, defaultValue: false) }
        set { defaults.set(newValue, forKey: webtoonGapKey) }
    }

    var webtoonWidth: ReaderWebtoonWidth {
        get {
            return ReaderWebtoonWidth(rawValue: defaults.integer(forKey: webtoonWidthKey))
                ?? .adaptive
        }
        set { defaults.set(newValue.rawValue, forKey: webtoonWidthKey) }
    }

    var doubleTapZoomEnabled: Bool {
        get { return bool(forKey: doubleTapZoomKey, defaultValue: true) }
        set { defaults.set(newValue, forKey: doubleTapZoomKey) }
    }

    var scaleMode: ReaderScaleMode {
        get {
            return ReaderScaleMode(rawValue: defaults.integer(forKey: scaleModeKey))
                ?? .fitScreen
        }
        set { defaults.set(newValue.rawValue, forKey: scaleModeKey) }
    }

    // Opt-in 3% border trim; original image files remain untouched.
    var trimMargins: Bool {
        get { return bool(forKey: trimMarginsKey, defaultValue: false) }
        set { defaults.set(newValue, forKey: trimMarginsKey) }
    }

    var preloadNextChapter: Bool {
        get { return bool(forKey: preloadNextChapterKey, defaultValue: true) }
        set { defaults.set(newValue, forKey: preloadNextChapterKey) }
    }

    private func bool(forKey key: String, defaultValue: Bool) -> Bool {
        guard defaults.object(forKey: key) != nil else {
            return defaultValue
        }
        return defaults.bool(forKey: key)
    }
}
