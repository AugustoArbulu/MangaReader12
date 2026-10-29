import UIKit

final class RootViewController: UITableViewController {
    private var results: [CoreDiagnosticItem] = []
    private var running = false

    init() {
        super.init(style: .plain)
    }

    required init?(coder: NSCoder) {
        super.init(coder: coder)
    }

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "Diagnósticos"
        tableView.tableFooterView = UIView()
        tableView.rowHeight = UITableView.automaticDimension
        tableView.estimatedRowHeight = 64
        applyTheme()

        navigationItem.rightBarButtonItem = UIBarButtonItem(
            barButtonSystemItem: .refresh,
            target: self,
            action: #selector(refreshTapped)
        )

        runDiagnostics()
    }

    @objc private func refreshTapped() {
        runDiagnostics()
    }

    private func runDiagnostics() {
        guard !running else { return }
        running = true
        navigationItem.rightBarButtonItem?.isEnabled = false
        navigationItem.prompt = "Executando diagnósticos…"

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let results = CoreDiagnostics.run()
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.results = results
                self.running = false
                self.navigationItem.rightBarButtonItem?.isEnabled = true

                let passed = results.filter { $0.passed }.count
                self.navigationItem.prompt = passed == results.count
                    ? "Core diagnostics passed (\(passed)/\(results.count))"
                    : "Core diagnostics failed (\(passed)/\(results.count))"

                self.tableView.reloadData()
            }
        }
    }

    override func tableView(
        _ tableView: UITableView,
        numberOfRowsInSection section: Int
    ) -> Int {
        return results.count
    }

    override func tableView(
        _ tableView: UITableView,
        cellForRowAt indexPath: IndexPath
    ) -> UITableViewCell {
        let identifier = "DiagnosticCell"
        let cell = tableView.dequeueReusableCell(withIdentifier: identifier)
            ?? UITableViewCell(style: .subtitle, reuseIdentifier: identifier)
        ThemeManager.shared.style(cell: cell)

        let result = results[indexPath.row]
        cell.textLabel?.text = "\(result.passed ? "✓" : "✗") \(result.name)"
        cell.textLabel?.textColor = result.passed
            ? UIColor(red: 0.08, green: 0.45, blue: 0.18, alpha: 1)
            : .red
        cell.detailTextLabel?.text = result.detail
        cell.detailTextLabel?.numberOfLines = 0
        cell.selectionStyle = .none
        return cell
    }
}


extension RootViewController: ThemeApplicable {
    func applyTheme() {
        ThemeManager.shared.style(tableView: tableView)
        tableView.reloadData()
    }
}
