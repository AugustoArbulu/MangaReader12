import UIKit

final class RootViewController: UIViewController {
    private let titleLabel = UILabel()
    private let detailLabel = UILabel()

    override func viewDidLoad() {
        super.viewDidLoad()

        title = "MangaReader12"
        view.backgroundColor = .white

        titleLabel.translatesAutoresizingMaskIntoConstraints = false
        titleLabel.text = "Milestone 0"
        titleLabel.font = UIFont.boldSystemFont(ofSize: 28)
        titleLabel.textAlignment = .center
        titleLabel.textColor = .black

        detailLabel.translatesAutoresizingMaskIntoConstraints = false
        detailLabel.numberOfLines = 0
        detailLabel.textAlignment = .center
        detailLabel.textColor = .darkGray
        detailLabel.font = UIFont.systemFont(ofSize: 16)
        detailLabel.text = "UIKit bootstrap\niOS 12.0 deployment target\nNo SwiftUI • No Combine • No async/await"

        view.addSubview(titleLabel)
        view.addSubview(detailLabel)

        NSLayoutConstraint.activate([
            titleLabel.centerXAnchor.constraint(equalTo: view.centerXAnchor),
            titleLabel.centerYAnchor.constraint(equalTo: view.centerYAnchor, constant: -40),
            titleLabel.leadingAnchor.constraint(greaterThanOrEqualTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            titleLabel.trailingAnchor.constraint(lessThanOrEqualTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24),

            detailLabel.topAnchor.constraint(equalTo: titleLabel.bottomAnchor, constant: 18),
            detailLabel.leadingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.leadingAnchor, constant: 24),
            detailLabel.trailingAnchor.constraint(equalTo: view.safeAreaLayoutGuide.trailingAnchor, constant: -24)
        ])
    }
}
