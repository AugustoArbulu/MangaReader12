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
    private let doubleTapZoomKey = "reader.doubleTapZoom"

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

    var doubleTapZoomEnabled: Bool {
        get { return bool(forKey: doubleTapZoomKey, defaultValue: true) }
        set { defaults.set(newValue, forKey: doubleTapZoomKey) }
    }

    private func bool(forKey key: String, defaultValue: Bool) -> Bool {
        guard defaults.object(forKey: key) != nil else {
            return defaultValue
        }
        return defaults.bool(forKey: key)
    }
}
