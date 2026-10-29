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
        return 4
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        switch section {
        case 0: return 2
        case 1: return 3
        case 2: return 2
        default: return 1
        }
    }

    override func tableView(
        _ tableView: UITableView,
        titleForHeaderInSection section: Int
    ) -> String? {
        switch section {
        case 0: return "Navegação"
        case 1: return "Exibição"
        case 2: return "Interação"
        default: return "Webtoon"
        }
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "ReaderSettingCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)
        cell.accessoryView = nil
        cell.accessoryType = .none
        cell.selectionStyle = .default

        switch (indexPath.section, indexPath.row) {
        case (0, 0):
            cell.textLabel?.text = "Modo padrão"
            cell.detailTextLabel?.text = preferences.displayMode == .pages
                ? "Páginas"
                : "Webtoon"
            cell.accessoryType = .disclosureIndicator

        case (0, 1):
            cell.textLabel?.text = "Direção das páginas"
            cell.detailTextLabel?.text = preferences.pageDirection.title
            cell.accessoryType = .disclosureIndicator

        case (1, 0):
            cell.textLabel?.text = "Cor de fundo"
            cell.detailTextLabel?.text = preferences.backgroundStyle.title
            cell.accessoryType = .disclosureIndicator

        case (1, 1):
            configureSwitch(
                cell,
                title: "Mostrar número da página",
                subtitle: "Exibe a página atual no leitor.",
                isOn: preferences.showPageNumber,
                action: #selector(showPageNumberChanged(_:))
            )

        case (1, 2):
            configureSwitch(
                cell,
                title: "Manter tela ligada",
                subtitle: "Evita que o aparelho durma durante a leitura.",
                isOn: preferences.keepScreenOn,
                action: #selector(keepScreenOnChanged(_:))
            )

        case (2, 0):
            configureSwitch(
                cell,
                title: "Áreas de toque",
                subtitle: "Toque nas laterais para avançar/voltar e no centro para esconder controles.",
                isOn: preferences.tapZonesEnabled,
                action: #selector(tapZonesChanged(_:))
            )

        case (2, 1):
            configureSwitch(
                cell,
                title: "Duplo toque para zoom",
                subtitle: "Alterna rapidamente entre 1x e 2,5x.",
                isOn: preferences.doubleTapZoomEnabled,
                action: #selector(doubleTapZoomChanged(_:))
            )

        default:
            configureSwitch(
                cell,
                title: "Espaço entre páginas",
                subtitle: "Adiciona uma pequena separação no modo Webtoon.",
                isOn: preferences.webtoonGapEnabled,
                action: #selector(webtoonGapChanged(_:))
            )
        }

        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)

        switch (indexPath.section, indexPath.row) {
        case (0, 0):
            showModePicker()
        case (0, 1):
            showDirectionPicker()
        case (1, 0):
            showBackgroundPicker()
        default:
            break
        }
    }

    private func configureSwitch(
        _ cell: UITableViewCell,
        title: String,
        subtitle: String,
        isOn: Bool,
        action: Selector
    ) {
        cell.textLabel?.text = title
        cell.detailTextLabel?.text = subtitle
        cell.selectionStyle = .none

        let toggle = UISwitch()
        toggle.isOn = isOn
        toggle.addTarget(self, action: action, for: .valueChanged)
        cell.accessoryView = toggle
    }

    @objc private func showPageNumberChanged(_ sender: UISwitch) {
        preferences.showPageNumber = sender.isOn
    }

    @objc private func keepScreenOnChanged(_ sender: UISwitch) {
        preferences.keepScreenOn = sender.isOn
    }

    @objc private func tapZonesChanged(_ sender: UISwitch) {
        preferences.tapZonesEnabled = sender.isOn
    }

    @objc private func doubleTapZoomChanged(_ sender: UISwitch) {
        preferences.doubleTapZoomEnabled = sender.isOn
    }

    @objc private func webtoonGapChanged(_ sender: UISwitch) {
        preferences.webtoonGapEnabled = sender.isOn
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

        presentActionSheet(sheet)
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

        presentActionSheet(sheet)
    }

    private func showBackgroundPicker() {
        let sheet = UIAlertController(
            title: "Cor de fundo",
            message: nil,
            preferredStyle: .actionSheet
        )

        for style in [ReaderBackgroundStyle.black, .gray, .white] {
            sheet.addAction(UIAlertAction(
                title: style.title,
                style: .default
            ) { [weak self] _ in
                self?.preferences.backgroundStyle = style
                self?.tableView.reloadData()
            })
        }

        presentActionSheet(sheet)
    }

    private func presentActionSheet(_ sheet: UIAlertController) {
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
