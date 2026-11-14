// FC: exact field/type contract extracted from WebReader Build70 source.
// Sources: MangaReader12/Core/Models.swift,
// MangaReader12/Sources/SourceManifest.swift,
// MangaReader12/Downloads/ChapterDownloadManager.swift (private DownloadRecoveryPlan).
// Verifies actual Swift Codable semantics; lab fixture, not app code.
import Foundation

enum MangaStatus: String, Codable {
    case unknown
    case ongoing
    case completed
    case hiatus
    case cancelled
}

struct Manga: Codable, Equatable {
    let id: String
    var title: String
    var altTitles: [String]
    var cover: String?
    var author: String?
    var artist: String?
    var description: String?
    var status: MangaStatus
    var genres: [String]
    var url: String?
}

struct Chapter: Codable, Equatable {
    let id: String
    var name: String
    var number: Double?
    var volume: Double?
    var date: String?
    var scanlator: String?
    var language: String?
    var url: String?
}

struct Page: Codable, Equatable {
    let index: Int
    let imageUrl: String
    var headers: [String: String]
}

struct SourceManifest: Codable, Equatable {
    let id: String
    let name: String
    let version: String
    let lang: String
    let author: String
    let script: String
    let icon: String?
    let apiVersion: Int
    let minAppVersion: String
    let domains: [String]
    let nsfw: Bool
    let sha256: String?
}

struct DownloadRecoveryPlan: Codable {
    let schemaVersion: Int
    let sourceID: String
    let manga: Manga
    let chapter: Chapter
    let pages: [Page]
    let manifest: SourceManifest
    let queueOrder: Int
    let requiresFullReplay: Bool?
}

// The comparable laboratory envelope below is compiled directly from the
// production-like native copy source in the FC test harness.

struct FBPlanEnvelope: Decodable {
    struct Work: Decodable {
        let id: String
        let title: String
        let altTitles: [String]
        let status: String
        let genres: [String]
    }
    struct Part: Decodable { let id: String; let name: String }
    struct Picture: Decodable {
        let index: Int
        let imageUrl: String
        let headers: [String: String]
    }
    struct Manifest: Decodable {
        let id: String
        let name: String
        let version: String
        let lang: String
        let author: String
        let script: String
        let apiVersion: Int
        let minAppVersion: String
        let domains: [String]
        let nsfw: Bool
    }
    let schemaVersion: Int
    let sourceID: String
    let manga: Work
    let chapter: Part
    let pages: [Picture]
    let manifest: Manifest
    let queueOrder: Int
    let requiresFullReplay: Bool?
}
