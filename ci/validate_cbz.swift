import Foundation

@main
struct SafeCBZHarness {
    static func main() {
        guard CommandLine.arguments.count == 3 else {
            fputs("Uso: validate_cbz <zip> <destination>\n", stderr)
            exit(2)
        }
        do {
            let output = URL(fileURLWithPath: CommandLine.arguments[2])
            try FileManager.default.createDirectory(
                at: output, withIntermediateDirectories: true, attributes: nil
            )
            let result = try SafeCBZArchive.extract(
                archiveURL: URL(fileURLWithPath: CommandLine.arguments[1]),
                into: output
            )
            print("OK:" + String(result.count))
            for entry in result { print(entry) }
        } catch {
            fputs("ERRO: \(error.localizedDescription)\n", stderr)
            exit(3)
        }
    }
}
