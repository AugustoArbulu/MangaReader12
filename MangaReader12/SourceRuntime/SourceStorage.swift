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

    // Clears only this installed source's JS storage namespace. Never
    // removes library entries, chapter downloads, app settings or cookies.
    @discardableResult
    func clearAll() -> Int {
        let prefix = "sources.\(sourceID).storage."
        let keys = defaults.dictionaryRepresentation().keys.filter {
            $0.hasPrefix(prefix)
        }
        for key in keys {
            defaults.removeObject(forKey: key)
        }
        return keys.count
    }

    func entryCount() -> Int {
        let prefix = "sources.\(sourceID).storage."
        return defaults.dictionaryRepresentation().keys.filter {
            $0.hasPrefix(prefix)
        }.count
    }

    private func namespaced(_ key: String) -> String {
        return "sources.\(sourceID).storage.\(key)"
    }
}
