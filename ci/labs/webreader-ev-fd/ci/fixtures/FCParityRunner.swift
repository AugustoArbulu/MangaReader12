import Foundation

@main
struct FCParityRunner {
    static func main() {
        let input = FileHandle.standardInput.readDataToEndOfFile()
        let realOK = (try? JSONDecoder().decode(DownloadRecoveryPlan.self, from: input)) != nil
        let mirror = try? JSONDecoder().decode(FBPlanEnvelope.self, from: input)
        let mirrorOK: Bool
        if let plan = mirror {
            mirrorOK = plan.schemaVersion == 1 &&
                ["unknown", "ongoing", "completed", "hiatus", "cancelled"].contains(plan.manga.status) &&
                !plan.pages.isEmpty && plan.pages.count <= 99_999 &&
                plan.pages.allSatisfy { $0.headers.isEmpty } &&
                plan.pages.enumerated().allSatisfy { i, page in page.index == i }
        } else {
            mirrorOK = false
        }
        print("real=\(realOK ? 1 : 0) mirror=\(mirrorOK ? 1 : 0)")
    }
}
