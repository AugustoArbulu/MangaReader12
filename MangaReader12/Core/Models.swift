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

struct SourceErrorPayload: Codable, Equatable {
    let code: String
    let message: String
}
