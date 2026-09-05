import UIKit

final class RootViewController: UIViewController {
    private let titleLabel = UILabel()
    private let subtitleLabel = UILabel()
    private let statusLabel = UILabel()
    private let diagnosticsStack = UIStackView()
    private let activityIndicator = UIActivityIndicatorView(style: .gray)

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "MangaReader12"
        view.backgroundColor = .white

        configureViews()
        configureLayout()
        runDiagnostics()
    }

    private func configureViews() {
        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.text = "Milestone 1A"
        titleLabel.font = UIFont.boldSystemFont(ofSize: 28)
        titleLabel.textAlignment = .center
        titleLabel.textColor = .black

        subtitleLabel.translatesAutoresizingMaskIntoConstraints = false
        subtitleLabel.text = "Core foundation — iOS 12.0"
        subtitleLabel.font = UIFont.systemFont(ofSize: 16)
        subtitleLabel.textAlignment = .center
        subtitleLabel.textColor = .darkGray
        subtitleLabel.numberOfLines = 0

        statusLabel.translatesAutoresizingMaskIntoConstraints = false
        statusLabel.text = "Running on-device core diagnostics…"
        statusLabel.font = UIFont.systemFont(ofSize: 15)
        statusLabel.textAlignment = .center
        statusLabel.textColor = .darkGray
        statusLabel.numberOfLines = 0

        diagnosticsStack.translatesAutoresizingMaskIntoConstraints = false
        diagnosticsStack.axis = .vertical
        diagnosticsStack.alignment = .fill
        diagnosticsStack.distribution = .fill
        diagnosticsStack.spacing = 10

        activityIndicator.translatesAutoresizingMaskIntoConstraints = false
        activityIndicator.hidesWhenStopped = true
        activityIndicator.startAnimating()

        view.addSubview(titleLabel)
        view.addSubview(subtitleLabel)
        view.addSubview(activityIndicator)
        view.addSubview(statusLabel)
        view.addSubview(diagnosticsStack)
    }

    private func configureLayout() {
        NSLayoutConstraint.activate([
            titleLabel.topAnchor.constraint(equalTo: view.safeAreaLayoutGuide.topAnchor, constant: 32),
            titleLabel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            titleLabel.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24),

            subtitleLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 10),
            subtitleLabel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            subtitleLabel.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24),

            activityIndicator.topAnchor.constraint(equalTo: subtitleLabel.bottomAnchor, constant: 24),
            activityIndicator.centerXAnchor.constraint(equalTo: view.centerXAnchor),

            statusLabel.topAnchor.constraint(equalTo: activityIndicator.bottomAnchor, constant: 12),
            statusLabel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            statusLabel.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24),

            diagnosticsStack.topAnchor.constraint(equalTo: statusLabel.bottomAnchor, constant: 22),
            diagnosticsStack.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 32),
            diagnosticsStack.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -32),
            diagnosticsStack.bottomAnchor.constraint(lessThanOrEqualTo: view.safeAreaLayoutGuide.bottomAnchor, constant: -24)
        ])
    }

    private func runDiagnostics() {
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            let results = CoreDiagnostics.run()
            DispatchQueue.main.async {
                self?.display(results: results)
            }
        }
    }

    private func display(results: [CoreDiagnosticItem]) {
        activityIndicator.stopAnimating()

        diagnosticsStack.arrangedSubviews.forEach { view in
            diagnosticsStack.removeArrangedSubview(view)
            view.removeFromSuperview()
        }

        for result in results {
            let label = UILabel()
            label.numberOfLines = 0
            label.font = UIFont.systemFont(ofSize: 15)
            label.textColor = result.passed ? UIColor(red: 0.08, green: 0.45, blue: 0.18, alpha: 1) : .red
            label.text = "\(result.passed ? "✓" : "✗") \(result.name): \(result.detail)"
            diagnosticsStack.addArrangedSubview(label)
        }

        let passedCount = results.filter { $0.passed }.count
        let allPassed = passedCount == results.count
        statusLabel.text = allPassed
            ? "Core diagnostics passed (\(passedCount)/\(results.count))."
            : "Core diagnostics failed (\(passedCount)/\(results.count))."
        statusLabel.textColor = allPassed
            ? UIColor(red: 0.08, green: 0.45, blue: 0.18, alpha: 1)
            : .red
    }
}
