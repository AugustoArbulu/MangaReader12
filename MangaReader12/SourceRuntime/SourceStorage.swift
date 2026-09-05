import Foundation

final class SourceStorage {
    private let sourceID: String
    private let defaults: UserDefaults

    init(sourceID: String, defaults: UserDefaults = .standard) {
        self.sourceID = sourceID
        self.defaults = defaults
    }

    func string(forKey key: String) -> String? {
        return defaults.string(forKey: namespaced(key))
    }

    func set(_ value: String, forKey key: String) {
        defaults.set(value, forKey: namespaced(key))
    }

    func removeValue(forKey key: String) {
        defaults.removeObject(forKey: namespaced(key))
    }

    private func namespaced(_ key: String) -> String {
        return "sources.\(sourceID).storage.\(key)"
    }
}
