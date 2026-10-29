import UIKit

@UIApplicationMain
final class AppDelegate: UIResponder, UIApplicationDelegate {
    var window: UIWindow?

    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        ThemeManager.shared.applyGlobalAppearance()

        let window = UIWindow(frame: UIScreen.main.bounds)
        window.backgroundColor = ThemeManager.shared.palette.background
        window.rootViewController = MainTabBarController()
        window.makeKeyAndVisible()
        self.window = window

        ThemeManager.shared.apply(to: window.rootViewController)
        return true
    }

    func resetRootViewController() {
        guard let window = window else { return }

        let root = MainTabBarController()
        window.rootViewController = root
        window.backgroundColor = ThemeManager.shared.palette.background
        ThemeManager.shared.applyGlobalAppearance()
        ThemeManager.shared.apply(to: root)
        window.makeKeyAndVisible()
    }
}
