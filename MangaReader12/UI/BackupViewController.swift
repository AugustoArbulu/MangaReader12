import UIKit

final class BackupViewController: UITableViewController, UIDocumentPickerDelegate {
    private let manager = BackupManager()
    private var restoring = false
    private var restoreConfirmationPending = false

    init() {
        super.init(style: .grouped)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        title = "Backup e restauração"
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
        return section == 0 ? 2 : 1
    }

    override func tableView(
        _ tableView: UITableView,
        titleForHeaderInSection section: Int
    ) -> String? {
        return section == 0 ? "Dados" : "Importante"
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "BackupCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)

        if indexPath.section == 0 {
            if indexPath.row == 0 {
                cell.textLabel?.text = "Criar backup"
                cell.detailTextLabel?.text = "Biblioteca, capítulos, histórico, obras fixadas, categorias e ajustes."
            } else {
                cell.textLabel?.text = "Restaurar backup"
                cell.detailTextLabel?.text = "Restaura biblioteca e ajustes; remove capítulos baixados offline."
            }
            cell.accessoryType = .disclosureIndicator
            cell.selectionStyle = .default
        } else {
            cell.textLabel?.text = "Backup não inclui páginas offline; restaurar remove downloads existentes."
            cell.detailTextLabel?.text = "Após restaurar em outro aparelho, reinstale as sources necessárias. O progresso e a Biblioteca permanecem no banco."
            cell.textLabel?.numberOfLines = 0
            cell.detailTextLabel?.numberOfLines = 0
            cell.accessoryType = .none
            cell.selectionStyle = .none
        }

        return cell
    }

    override func tableView(
        _ tableView: UITableView,
        didSelectRowAt indexPath: IndexPath
    ) {
        tableView.deselectRow(at: indexPath, animated: true)
        guard indexPath.section == 0 else { return }

        if indexPath.row == 0 {
            createBackup()
        } else {
            chooseBackup()
        }
    }

    private func createBackup() {
        do {
            let url = try manager.createBackupFile()
            let picker = UIDocumentPickerViewController(
                url: url,
                in: .exportToService
            )
            picker.delegate = self
            present(picker, animated: true)
        } catch {
            showError(error)
        }
    }

    private func chooseBackup() {
        guard !restoring, !restoreConfirmationPending else { return }
        restoring = true
        let picker = UIDocumentPickerViewController(
            documentTypes: ["public.data"],
            in: .import
        )
        picker.delegate = self
        picker.allowsMultipleSelection = false
        present(picker, animated: true)
    }

    func documentPicker(
        _ controller: UIDocumentPickerViewController,
        didPickDocumentsAt urls: [URL]
    ) {
        guard restoring, let url = urls.first else {
            restoring = false
            return
        }

        restoring = false
        guard !restoreConfirmationPending else { return }
        restoreConfirmationPending = true
        let warning = UIAlertController(
            title: "Restaurar backup e remover downloads?",
            message: "A restauração substitui os dados da biblioteca pelo " +
                "conteúdo do arquivo selecionado e APAGA os capítulos " +
                "baixados offline. O backup .mr12backup não contém páginas. " +
                "Para atualizar o WebReader sem perder downloads, instale " +
                "a nova IPA por cima da existente; não restaure o backup " +
                "sem necessidade. Continuar?",
            preferredStyle: .alert
        )
        warning.addAction(UIAlertAction(
            title: "Cancelar", style: .cancel
        ) { [weak self] _ in
            self?.restoreConfirmationPending = false
        })
        warning.addAction(UIAlertAction(
            title: "Restaurar e apagar downloads", style: .destructive
        ) { [weak self] _ in
            guard let self = self else { return }
            self.restoreConfirmationPending = false
            self.performSelectedBackupRestore(from: url)
        })
        present(warning, animated: true)
    }

    private func performSelectedBackupRestore(from url: URL) {
        // The document picker imports a local copy. Open its security scope
        // only for the owner-confirmed restore operation.
        let accessed = url.startAccessingSecurityScopedResource()
        defer {
            if accessed {
                url.stopAccessingSecurityScopedResource()
            }
        }

        do {
            let report = try manager.restoreBackup(from: url)
            let formatter = DateFormatter()
            formatter.dateStyle = .medium
            formatter.timeStyle = .short

            let alert = UIAlertController(
                title: "Backup restaurado",
                message: "Backup de \(formatter.string(from: Date(timeIntervalSince1970: report.createdAt))) restaurado.\n\nA interface será recarregada agora.",
                preferredStyle: .alert
            )

            alert.addAction(UIAlertAction(
                title: "Continuar",
                style: .default
            ) { _ in
                (UIApplication.shared.delegate as? AppDelegate)?
                    .resetRootViewController()
            })

            present(alert, animated: true)
        } catch {
            showError(error)
        }
    }

    func documentPickerWasCancelled(_ controller: UIDocumentPickerViewController) {
        restoring = false
    }

    private func showError(_ error: Error) {
        let alert = UIAlertController(
            title: "Erro",
            message: error.localizedDescription,
            preferredStyle: .alert
        )
        alert.addAction(UIAlertAction(title: "OK", style: .default))
        present(alert, animated: true)
    }
}

extension BackupViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
