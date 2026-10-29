import UIKit

final class BackgroundLibraryUpdateManager {
    static let shared = BackgroundLibraryUpdateManager()

    private let defaults: UserDefaults
    private let enabledKey = "backgroundUpdates.enabled"

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    var isEnabled: Bool {
        get {
            guard defaults.object(forKey: enabledKey) != nil else {
                return false
            }
            return defaults.bool(forKey: enabledKey)
        }
        set {
            defaults.set(newValue, forKey: enabledKey)
            applyScheduling()
        }
    }

    func applyScheduling() {
        let interval: TimeInterval = isEnabled
            ? 6 * 60 * 60
            : UIApplicationBackgroundFetchIntervalNever

        UIApplication.shared.setMinimumBackgroundFetchInterval(interval)
    }

    func performFetch(
        completion: @escaping (UIBackgroundFetchResult) -> Void
    ) {
        guard isEnabled else {
            completion(.noData)
            return
        }

        let manager: LibraryUpdateManager

        do {
            manager = try LibraryUpdateManager.defaultManager()
        } catch {
            completion(.failed)
            return
        }

        let lock = NSLock()
        var finished = false

        func finish(_ result: UIBackgroundFetchResult) {
            lock.lock()
            defer { lock.unlock() }

            guard !finished else { return }
            finished = true

            DispatchQueue.main.async {
                completion(result)
            }
        }

        DispatchQueue.main.asyncAfter(deadline: .now() + 25) {
            finish(.failed)
        }

        manager.checkAll(
            progress: { _, _ in },
            completion: { result in
                switch result {
                case .success(let value):
                    finish(value.newChapters.isEmpty ? .noData : .newData)

                case .failure:
                    finish(.failed)
                }
            }
        )
    }
}
