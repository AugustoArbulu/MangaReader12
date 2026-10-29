import UIKit

final class DataStorageViewController: UITableViewController {
    private var storageManager: StorageManager?
    private var snapshot = StorageSnapshot(
        databaseBytes: 0,
        downloadsBytes: 0,
        readerCacheBytes: 0,
        coverCacheBytes: 0
    )
    private let formatter: ByteCountFormatter = {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        formatter.allowedUnits = [.useKB, .useMB, .useGB]
        return formatter
    }()

    init() {
        super.init(style: .grouped)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Dados e armazenamento"
        tableView.tableFooterView = UIView()
        applyTheme()

        do {
            storageManager = try StorageManager.defaultManager()
        } catch {
            showError(error)
        }

        refreshSnapshot()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        refreshSnapshot()
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
        case 1: return 4
        case 2: return 3
        default: return 2
        }
    }

    override func tableView(
        _ tableView: UITableView,
        titleForHeaderInSection section: Int
    ) -> String? {
        switch section {
        case 0: return "Backup"
        case 1: return "Uso de armazenamento"
        case 2: return "Manutenção"
        default: return "Downloads"
        }
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "DataStorageCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)
        cell.accessoryType = .none
        cell.selectionStyle = .default

        switch (indexPath.section, indexPath.row) {
        case (0, 0):
            cell.textLabel?.text = "Backup e restauração"
            cell.detailTextLabel?.text = "Exportar ou importar biblioteca, progresso, histórico, categorias e ajustes."
            cell.accessoryType = .disclosureIndicator

        case (0, 1):
            cell.textLabel?.text = "Formato do backup"
            cell.detailTextLabel?.text = ".mr12backup • downloads e scripts de sources não incluídos"
            cell.selectionStyle = .none

        case (1, 0):
            cell.textLabel?.text = "Banco de dados"
            cell.detailTextLabel?.text = format(snapshot.databaseBytes)
            cell.selectionStyle = .none

        case (1, 1):
            cell.textLabel?.text = "Downloads offline"
            cell.detailTextLabel?.text = format(snapshot.downloadsBytes)
            cell.selectionStyle = .none

        case (1, 2):
            cell.textLabel?.text = "Cache do leitor"
            cell.detailTextLabel?.text = format(snapshot.readerCacheBytes)
            cell.selectionStyle = .none

        case (1, 3):
            cell.textLabel?.text = "Cache de capas"
            cell.detailTextLabel?.text = format(snapshot.coverCacheBytes)
            cell.selectionStyle = .none

        case (2, 0):
            cell.textLabel?.text = "Limpar cache do leitor"
            cell.detailTextLabel?.text = "Remove imagens temporárias; downloads offline não são afetados."

        case (2, 1):
            cell.textLabel?.text = "Limpar cache de capas"
            cell.detailTextLabel?.text = "As capas serão baixadas novamente quando necessárias."

        case (2, 2):
            cell.textLabel?.text = "Reindexar downloads"
            cell.detailTextLabel?.text = "Remove do banco registros cujos arquivos offline não existem mais."

        case (3, 0):
            cell.textLabel?.text = "Gerenciar downloads"
            cell.detailTextLabel?.text = "Ver capítulos offline, progresso e remover itens individualmente."
            cell.accessoryType = .disclosureIndicator

        default:
            cell.textLabel?.text = "Apagar todos os downloads"
            cell.detailTextLabel?.text = "Remove todos os capítulos salvos offline."
            cell.textLabel?.textColor = .red
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
            navigationController?.pushViewController(
                BackupViewController(),
                animated: true
            )

        case (2, 0):
            performMaintenance(
                title: "Cache do leitor limpo"
            ) { manager in
                try manager.clearReaderCache()
                return nil
            }

        case (2, 1):
            performMaintenance(
                title: "Cache de capas limpo"
            ) { manager in
                try manager.clearCoverCache()
                return nil
            }

        case (2, 2):
            performMaintenance(
                title: "Downloads reindexados"
            ) { manager in
                let removed = try manager.reindexDownloads()
                return "\(removed) registro(s) sem arquivo foram removidos."
            }

        case (3, 0):
            navigationController?.pushViewController(
                DownloadsViewController(),
                animated: true
            )

        case (3, 1):
            confirmClearDownloads()

        default:
            break
        }
    }

    private func performMaintenance(
        title: String,
        operation: (StorageManager) throws -> String?
    ) {
        guard let storageManager = storageManager else { return }

        do {
            let message = try operation(storageManager)
            refreshSnapshot()
            showMessage(
                title: title,
                message: message
            )
        } catch {
            showError(error)
        }
    }

    private func confirmClearDownloads() {
        let alert = UIAlertController(
            title: "Apagar todos os downloads?",
            message: "Os capítulos offline serão removidos. Biblioteca, progresso e histórico não serão apagados.",
            preferredStyle: .alert
        )

        alert.addAction(UIAlertAction(title: "Cancelar", style: .cancel))
        alert.addAction(UIAlertAction(
            title: "Apagar",
            style: .destructive
        ) { [weak self] _ in
            self?.performMaintenance(
                title: "Downloads apagados"
            ) { manager in
                try manager.clearAllDownloads()
                return nil
            }
        })

        present(alert, animated: true)
    }

    private func refreshSnapshot() {
        if let storageManager = storageManager {
            snapshot = storageManager.snapshot()
        }
        tableView.reloadData()
    }

    private func format(_ value: Int64) -> String {
        guard value > 0 else { return "0 KB" }
        return formatter.string(fromByteCount: value)
    }

    private func showError(_ error: Error) {
        showMessage(title: "Erro", message: error.localizedDescription)
    }

    private func showMessage(title: String, message: String?) {
        let alert = UIAlertController(
            title: title,
            message: message,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

extension DataStorageViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
