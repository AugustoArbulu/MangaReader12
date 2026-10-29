import UIKit

final class ReaderSettingsViewController: UITableViewController {
    private let preferences = ReaderPreferences.shared

    init() {
        super.init(style: .grouped)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Leitor"
        tableView.tableFooterView = UIView()
        applyTheme()
    }

    override func numberOfSections(in tableView: UITableView) -> Int {
        return 2
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return 1
    }

    override func tableView(
        _ tableView: UITableView,
        titleForHeaderInSection section: Int
    ) -> String? {
        return section == 0 ? "Modo padrão" : "Direção das páginas"
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "ReaderSettingCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)
        cell.accessoryType = .disclosureIndicator

        if indexPath.section == 0 {
            cell.textLabel?.text = preferences.displayMode == .pages
                ? "Páginas"
                : "Webtoon"
            cell.detailTextLabel?.text = "Também pode ser alterado dentro do leitor."
        } else {
            cell.textLabel?.text = preferences.pageDirection.title
            cell.detailTextLabel?.text = preferences.displayMode == .webtoon
                ? "Usada quando o modo Páginas estiver ativo."
                : "Direção horizontal do modo Páginas."
        }

        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        if indexPath.section == 0 {
            showModePicker()
        } else {
            showDirectionPicker()
        }
    }

    private func showModePicker() {
        let sheet = UIAlertController(
            title: "Modo padrão do leitor",
            message: nil,
            preferredStyle: .actionSheet
        )

        sheet.addAction(UIAlertAction(title: "Páginas", style: .default) { [weak self] _ in
            self?.preferences.displayMode = .pages
            self?.tableView.reloadData()
        })

        sheet.addAction(UIAlertAction(title: "Webtoon", style: .default) { [weak self] _ in
            self?.preferences.displayMode = .webtoon
            self?.tableView.reloadData()
        })

        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))

        if let popover = sheet.popoverPresentationController {
            popover.sourceView = view
            popover.sourceRect = CGRect(
                x: view.bounds.midX,
                y: view.bounds.midY,
                width: 1,
                height: 1
            )
        }

        present(sheet, animated: true)
    }

    private func showDirectionPicker() {
        let sheet = UIAlertController(
            title: "Direção das páginas",
            message: nil,
            preferredStyle: .actionSheet
        )

        sheet.addAction(UIAlertAction(
            title: ReaderPageDirection.leftToRight.title,
            style: .default
        ) { [weak self] _ in
            self?.preferences.pageDirection = .leftToRight
            self?.tableView.reloadData()
        })

        sheet.addAction(UIAlertAction(
            title: ReaderPageDirection.rightToLeft.title,
            style: .default
        ) { [weak self] _ in
            self?.preferences.pageDirection = .rightToLeft
            self?.tableView.reloadData()
        })

        sheet.addAction(UIAlertAction(title: "Cancelar", style: .cancel))

        if let popover = sheet.popoverPresentationController {
            popover.sourceView = view
            popover.sourceRect = CGRect(
                x: view.bounds.midX,
                y: view.bounds.midY,
                width: 1,
                height: 1
            )
        }

        present(sheet, animated: true)
    }
}

extension ReaderSettingsViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
