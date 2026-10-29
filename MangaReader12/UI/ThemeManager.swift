import UIKit

enum AppTheme: Int {
    case light = 0
    case dark = 1
}

struct AppPalette {
    let background: UIColor
    let secondaryBackground: UIColor
    let cellBackground: UIColor
    let primaryText: UIColor
    let secondaryText: UIColor
    let separator: UIColor
    let barBackground: UIColor
    let accent: UIColor
}

protocol ThemeApplicable: AnyObject {
    func applyTheme()
}

extension Notification.Name {
    static let appThemeDidChange = Notification.Name("MangaReader12.appThemeDidChange")
}

final class ThemeManager {
    static let shared = ThemeManager()

    private let defaultsKey = "app.theme"
    private let defaults: UserDefaults

    private init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    var currentTheme: AppTheme {
        return AppTheme(rawValue: defaults.integer(forKey: defaultsKey)) ?? .light
    }

    var isDark: Bool {
        return currentTheme == .dark
    }

    var palette: AppPalette {
        if isDark {
            return AppPalette(
                background: UIColor(red: 0.07, green: 0.07, blue: 0.08, alpha: 1),
                secondaryBackground: UIColor(red: 0.10, green: 0.10, blue: 0.11, alpha: 1),
                cellBackground: UIColor(red: 0.12, green: 0.12, blue: 0.13, alpha: 1),
                primaryText: .white,
                secondaryText: UIColor(red: 0.68, green: 0.68, blue: 0.71, alpha: 1),
                separator: UIColor(red: 0.23, green: 0.23, blue: 0.25, alpha: 1),
                barBackground: UIColor(red: 0.09, green: 0.09, blue: 0.10, alpha: 1),
                accent: UIColor(red: 0.25, green: 0.56, blue: 1.00, alpha: 1)
            )
        }

        return AppPalette(
            background: .white,
            secondaryBackground: UIColor(white: 0.96, alpha: 1),
            cellBackground: .white,
            primaryText: .black,
            secondaryText: .darkGray,
            separator: UIColor(white: 0.85, alpha: 1),
            barBackground: .white,
            accent: UIColor(red: 0.00, green: 0.48, blue: 1.00, alpha: 1)
        )
    }

    func setTheme(_ theme: AppTheme) {
        guard theme != currentTheme else { return }

        defaults.set(theme.rawValue, forKey: defaultsKey)
        defaults.synchronize()
        applyGlobalAppearance()

        NotificationCenter.default.post(
            name: .appThemeDidChange,
            object: self
        )
    }

    func applyGlobalAppearance() {
        let colors = palette

        let navigationBar = UINavigationBar.appearance()
        navigationBar.barTintColor = colors.barBackground
        navigationBar.tintColor = colors.accent
        navigationBar.isTranslucent = false
        navigationBar.barStyle = isDark ? .black : .default
        navigationBar.titleTextAttributes = [
            .foregroundColor: colors.primaryText
        ]

        let tabBar = UITabBar.appearance()
        tabBar.barTintColor = colors.barBackground
        tabBar.tintColor = colors.accent
        tabBar.isTranslucent = false

        UITableView.appearance().separatorColor = colors.separator
        UISwitch.appearance().onTintColor = colors.accent
    }

    func apply(to rootViewController: UIViewController?) {
        guard let controller = rootViewController else { return }

        styleBars(for: controller)

        if let applicable = controller as? ThemeApplicable {
            applicable.applyTheme()
        } else if let tableController = controller as? UITableViewController {
            style(tableView: tableController.tableView)
        } else if !(controller is ReaderViewController) {
            controller.view.backgroundColor = palette.background
        }

        if let navigation = controller as? UINavigationController {
            for child in navigation.viewControllers {
                apply(to: child)
            }
        }

        if let tab = controller as? UITabBarController {
            for child in tab.viewControllers ?? [] {
                apply(to: child)
            }
        }

        for child in controller.children
            where !(controller is UINavigationController)
                && !(controller is UITabBarController) {
            apply(to: child)
        }

        if let presented = controller.presentedViewController {
            apply(to: presented)
        }
    }

    func styleBars(for controller: UIViewController) {
        let colors = palette

        if let navigation = controller as? UINavigationController {
            navigation.navigationBar.barTintColor = colors.barBackground
            navigation.navigationBar.tintColor = colors.accent
            navigation.navigationBar.barStyle = isDark ? .black : .default
            navigation.navigationBar.titleTextAttributes = [
                .foregroundColor: colors.primaryText
            ]
        }

        if let tab = controller as? UITabBarController {
            tab.tabBar.barTintColor = colors.barBackground
            tab.tabBar.tintColor = colors.accent
        }
    }

    func style(tableView: UITableView) {
        let colors = palette
        tableView.backgroundColor = colors.background
        tableView.separatorColor = colors.separator
    }

    func style(cell: UITableViewCell) {
        let colors = palette
        cell.backgroundColor = colors.cellBackground
        cell.contentView.backgroundColor = colors.cellBackground
        cell.textLabel?.textColor = colors.primaryText
        cell.detailTextLabel?.textColor = colors.secondaryText
        cell.tintColor = colors.accent

        let selected = UIView()
        selected.backgroundColor = isDark
            ? UIColor(white: 0.20, alpha: 1)
            : UIColor(white: 0.90, alpha: 1)
        cell.selectedBackgroundView = selected
    }

    func style(searchBar: UISearchBar) {
        searchBar.barStyle = isDark ? .black : .default
        searchBar.tintColor = palette.accent
        searchBar.barTintColor = palette.barBackground
    }
}
