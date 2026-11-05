import UIKit

@UIApplicationMain
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    // The separate IPA is a connectivity diagnostic, not a second reader.
    // It must never instantiate the Library/Explore tabs or schedule updates.
    private var isIPCProbe: Bool {
        return Bundle.main.bundleIdentifier == "com.example.MangaReader12.ipcprobe"
    }

    private func makeRootController() -> UIViewController {
        if isIPCProbe {
            return UINavigationController(
                rootViewController: WebReaderAppUpdatesViewController()
            )
        }
        return MainTabBarController()
    }

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        ThemeManager.shared.applyGlobalAppearance()

        let window = UIWindow(frame: UIScreen.main.bounds)
        window.backgroundColor = ThemeManager.shared.palette.background
        window.rootViewController = makeRootController()
        window.makeKeyAndVisible()
        self.window = window

        ThemeManager.shared.apply(to: window.rootViewController)
        if !isIPCProbe {
            BackgroundLibraryUpdateManager.shared.applyScheduling()
        }
        return true
    }

    func application(
        _ application: UIApplication,
        performFetchWithCompletionHandler completionHandler: @escaping (UIBackgroundFetchResult) -> Void
    ) {
        guard !isIPCProbe else {
            completionHandler(.noData)
            return
        }
        BackgroundLibraryUpdateManager.shared.performFetch(
            completion: completionHandler
        )
    }

    func resetRootViewController() {
        guard let window = window else { return }

        let root = makeRootController()
        window.rootViewController = root
        window.backgroundColor = ThemeManager.shared.palette.background
        ThemeManager.shared.applyGlobalAppearance()
        ThemeManager.shared.apply(to: root)
        window.makeKeyAndVisible()
    }
}
