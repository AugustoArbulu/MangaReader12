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

final class ReaderPreferences {
    static let shared = ReaderPreferences()

    private let defaults: UserDefaults
    private let modeKey = "reader.mode"
    private let directionKey = "reader.pageDirection"

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
}
