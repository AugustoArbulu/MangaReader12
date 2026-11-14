// WebReader Phase EV: disposable, native Swift file-descriptor probe ONLY.
// Does not import the app, touch iPad files, delete pages or purge quarantine.
// Must be invoked on an explicitly marked synthetic lab directory.
// POSIX rename cannot pin the source inode: post-rename mismatch => REVIEW.
import Foundation
#if canImport(Darwin)
import Darwin
#elseif canImport(Glibc)
import Glibc
#endif

#if os(Linux)
@_silgen_name("renameat2")
private func ev_renameat2(_ oldfd: Int32, _ oldname: UnsafePointer<CChar>,
                          _ newfd: Int32, _ newname: UnsafePointer<CChar>,
                          _ flags: UInt32) -> Int32
#endif

private enum EVError: Error, CustomStringConvertible {
    case unsafe(String)
    case system(String, Int32)
    var description: String {
        switch self {
        case .unsafe(let reason): return "UNSAFE: " + reason
        case .system(let operation, let code): return "OS_ERROR: \(operation): errno=\(code)"
        }
    }
}

private struct Identity: Equatable {
    let device: UInt64
    let inode: UInt64
    init(_ item: stat) {
        device = UInt64(item.st_dev)
        inode = UInt64(item.st_ino)
    }
    init?(device: String, inode: String) {
        guard let d = UInt64(device), let i = UInt64(inode), d > 0, i > 0 else { return nil }
        self.device = d
        self.inode = i
    }
    func json(_ status: String) -> String {
        return "{\"status\":\"\(status)\",\"device\":\"\(device)\",\"inode\":\"\(inode)\"}"
    }
}

private func component(_ name: String, max: Int = 80) throws -> String {
    guard !name.isEmpty, name.utf8.count <= max, name != ".", name != "..",
          name.utf8.allSatisfy({ ($0 >= 65 && $0 <= 90) || ($0 >= 97 && $0 <= 122) ||
                                 ($0 >= 48 && $0 <= 57) || $0 == 45 || $0 == 95 || $0 == 46 })
    else { throw EVError.unsafe("invalid path component") }
    return name
}

private func openDirectory(_ path: String) throws -> Int32 {
    let fd = path.withCString { open($0, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC) }
    guard fd >= 0 else { throw EVError.system("open-directory", errno) }
    return fd
}

private func openChild(_ parent: Int32, _ name: String) throws -> Int32 {
    let n = try component(name)
    let fd = n.withCString { openat(parent, $0, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC) }
    guard fd >= 0 else { throw EVError.system("openat-directory", errno) }
    return fd
}

private func lstatChild(_ parent: Int32, _ name: String) throws -> stat? {
    var item = stat()
    let rc = name.withCString { fstatat(parent, $0, &item, AT_SYMLINK_NOFOLLOW) }
    if rc == 0 { return item }
    if errno == ENOENT { return nil }
    throw EVError.system("fstatat", errno)
}

private func isDirectory(_ item: stat) -> Bool {
    return (item.st_mode & mode_t(S_IFMT)) == mode_t(S_IFDIR)
}

private func same(_ a: stat, _ b: stat) -> Bool {
    return Identity(a) == Identity(b) && a.st_mode == b.st_mode
}

private func verifyMarker(_ rootFD: Int32) throws {
    let name = ".webreader_ev_disposable_marker"
    let fd = name.withCString { openat(rootFD, $0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC) }
    guard fd >= 0 else { throw EVError.unsafe("synthetic-only marker missing") }
    defer { _ = close(fd) }
    var st = stat()
    guard fstat(fd, &st) == 0,
          (st.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG),
          st.st_nlink == 1, st.st_size == 18 else {
        throw EVError.unsafe("invalid marker metadata")
    }
    var bytes = [UInt8](repeating: 0, count: 19)
    let got = bytes.withUnsafeMutableBytes { read(fd, $0.baseAddress, $0.count) }
    guard got == 18, String(bytes: bytes.prefix(18), encoding: .utf8) == "EV_SYNTHETIC_ONLY\n" else {
        throw EVError.unsafe("synthetic-only marker mismatch")
    }
}

private func directoryEntries(_ fd: Int32) throws -> [String] {
    let duplicate = dup(fd)
    guard duplicate >= 0 else { throw EVError.system("dup", errno) }
    guard let stream = fdopendir(duplicate) else {
        let err = errno
        _ = close(duplicate)
        throw EVError.system("fdopendir", err)
    }
    defer { _ = closedir(stream) }
    rewinddir(stream) // dup shares directory offset; ensure repeated admission sees all entries.
    var result = [String]()
    errno = 0
    while let entry = readdir(stream) {
        let name = withUnsafePointer(to: entry.pointee.d_name) {
            $0.withMemoryRebound(to: CChar.self, capacity: 256) { String(cString: $0) }
        }
        if name == "." || name == ".." { continue }
        result.append(name)
        guard result.count <= 100_001 else { throw EVError.unsafe("too many entries") }
        errno = 0
    }
    if errno != 0 { throw EVError.system("readdir", errno) }
    return result
}

private func verifyPages(_ leafFD: Int32) throws {
    let names = try directoryEntries(leafFD)
    guard !names.isEmpty else { throw EVError.unsafe("empty chapter folder") }
    for name in names {
        // This native probe deliberately supports only page-#####.bin.
        // Real app manifests/receipts require a separate proven adapter.
        let utf = Array(name.utf8)
        guard utf.count == 14, name.hasPrefix("page-"), name.hasSuffix(".bin"),
              utf[5...9].allSatisfy({ $0 >= 48 && $0 <= 57 }) else {
            throw EVError.unsafe("unrecognized chapter entry")
        }
        guard let st = try lstatChild(leafFD, name),
              (st.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG), st.st_nlink == 1,
              st.st_size > 0, st.st_size <= 20 * 1024 * 1024 else {
            throw EVError.unsafe("unsafe page file")
        }
    }
}

private func inspectChapter(_ parent: Int32, _ leaf: String,
                            owner: (String,String,String)? = nil,
                            sealedOnly: Bool = false) throws -> Identity {
    guard let before = try lstatChild(parent, leaf), isDirectory(before) else {
        throw EVError.unsafe("leaf absent or not a real directory")
    }
    let leafFD = try openChild(parent, leaf)
    defer { _ = close(leafFD) }
    var opened = stat()
    guard fstat(leafFD, &opened) == 0, same(before, opened) else {
        throw EVError.unsafe("leaf changed during open")
    }
    if let owner = owner {
        _ = try fbInventory(leafFD, owner.0, owner.1, owner.2,
                            allowRecoveryPlan: !sealedOnly)
    } else {
        try verifyPages(leafFD)
    }
    guard let after = try lstatChild(parent, leaf), same(before, after) else {
        throw EVError.unsafe("leaf changed during inspection")
    }
    return Identity(before)
}

// Detect reparented directory handles before/after an operation. This is
// observation, NOT an atomic lock on path resolution or the source basename.
private func verifyPinnedEdge(_ parent: Int32, _ name: String,
                              _ pinned: Int32) throws {
    guard let entry = try lstatChild(parent, name), isDirectory(entry) else {
        throw EVError.unsafe("opened directory was reparented")
    }
    var opened = stat()
    guard fstat(pinned, &opened) == 0, same(entry, opened) else {
        throw EVError.unsafe("opened directory inode no longer matches canonical path")
    }
}

private func withContext<T>(root: String, source: String, manga: String,
                            _ body: (Int32, Int32, Int32) throws -> T) throws -> T {
    let s = try component(source)
    let m = try component(manga)
    // Local temp dirs are created by tests; no other filesystem roots allowed.
    var opened = [Int32]()
    defer { for fd in opened.reversed() { _ = close(fd) } }
    func capture(_ value: Int32) -> Int32 { opened.append(value); return value }
    let rootFD = capture(try openDirectory(root))
    try verifyMarker(rootFD)
    let app = capture(try openChild(rootFD, "synthetic_app"))
    let downloads = capture(try openChild(app, "Downloads"))
    let sourceFD = capture(try openChild(downloads, s))
    let mangaFD = capture(try openChild(sourceFD, m))
    let quarantineFD = capture(try openChild(app, "Quarantine"))
    var a = stat(), b = stat()
    guard fstat(mangaFD, &a) == 0, fstat(quarantineFD, &b) == 0,
          a.st_dev == b.st_dev else { throw EVError.unsafe("cross-filesystem quarantine") }
    let edges: [(Int32, String, Int32)] = [
        (rootFD, "synthetic_app", app),
        (app, "Downloads", downloads),
        (downloads, s, sourceFD),
        (sourceFD, m, mangaFD),
        (app, "Quarantine", quarantineFD)
    ]
    for (parent, name, pinned) in edges {
        try verifyPinnedEdge(parent, name, pinned)
    }
    let result = try body(mangaFD, quarantineFD, rootFD)
    for (parent, name, pinned) in edges {
        try verifyPinnedEdge(parent, name, pinned)
    }
    return result
}

private func moveExclusively(_ sourceFD: Int32, _ source: String,
                             _ destFD: Int32, _ dest: String) throws {
    let result: Int32 = source.withCString { s in
        dest.withCString { d in
            #if os(Linux)
            return ev_renameat2(sourceFD, s, destFD, d, 1) // RENAME_NOREPLACE
            #else
            // Darwin's RENAME_EXCL is destination-exclusive, NOT source-inode conditional.
            return renameatx_np(sourceFD, s, destFD, d, UInt32(RENAME_EXCL))
            #endif
        }
    }
    guard result == 0 else { throw EVError.system("exclusive-rename", errno) }
    // These calls reduce but do not prove durable ordering across APFS/SQLite.
    guard fsync(sourceFD) == 0, fsync(destFD) == 0 else {
        throw EVError.system("fsync-parents", errno)
    }
}

// EY adversarial test-only gate. The actual application MUST NOT import this
// standalone binary. When explicitly enabled inside a marked synthetic root,
// pause after inspecting the source (and before rename) so a test can replace
// the source basename. This proves that destination exclusivity does not pin
// the source inode. The gate never deletes, restores or purges any content.
private func eySyntheticPreRenameGate(_ rootFD: Int32) throws {
    guard ProcessInfo.processInfo.environment["WEBREADER_EY_RACE_GATE"] == "1" else { return }
    let ready = ".ey_pre_rename_ready"
    let go = ".ey_pre_rename_go"
    let fd = ready.withCString {
        openat(rootFD, $0, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
    }
    guard fd >= 0 else { throw EVError.system("race-test-ready", errno) }
    var marker = [UInt8]("READY\n".utf8)
    let written = marker.withUnsafeMutableBytes { write(fd, $0.baseAddress, $0.count) }
    _ = fsync(fd)
    _ = close(fd)
    guard written == 6 else { throw EVError.unsafe("race gate marker write failed") }
    for _ in 0..<400 {
        let signalFD = go.withCString { openat(rootFD, $0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC) }
        if signalFD >= 0 {
            var info = stat()
            let valid = fstat(signalFD, &info) == 0 &&
                (info.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) && info.st_nlink == 1
            _ = close(signalFD)
            guard valid else { throw EVError.unsafe("invalid race gate release") }
            return
        }
        guard errno == ENOENT else { throw EVError.system("race-test-wait", errno) }
        usleep(15_000)
    }
    throw EVError.unsafe("race gate timeout (no rename performed)")
}


// BEGIN BUILD70_FB_METADATA_SNAPSHOT_LAB
// FB laboratory-compatible decoding subset: mirrors all *required* Codable
// fields of ChapterDownloadManager.DownloadRecoveryPlan and nested models.
// Optional fields intentionally remain optional. No network access.
private struct FBPlanEnvelope: Decodable {
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

private func fbAdmittedFile(_ s: stat, _ name: String, metadata: Bool) -> Bool {
    if ezPageName(name) { return ezRegularPage(s) }
    guard metadata else { return false }
    let maximum: Int64
    if name == "_download-plan.json" { maximum = 16 * 1024 * 1024 }
    else if name == ".webreader-completion-v1" { maximum = 64 }
    else { return false }
    return (s.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) &&
        s.st_nlink == 1 && s.st_size > 0 && s.st_size <= maximum
}
// This synthetic-only adapter mirrors the strict naming/ownership contract
// of the app's ER preflight. The independent app Codable decoder is NOT
// invoked here. Admission deliberately rejects ambiguous/foreign metadata.
private func fbInventory(_ directoryFD: Int32, _ source: String,
                         _ manga: String, _ chapter: String,
                         allowRecoveryPlan: Bool = true) throws -> (names: [String], pages: Int) {
    let names = try directoryEntries(directoryFD).sorted()
    guard !names.isEmpty, names.count <= 100_001 else {
        throw EVError.unsafe("metadata fixture count outside bounds")
    }
    let pages = names.filter(ezPageName)
    guard !pages.isEmpty, pages.count <= 99_999 else {
        throw EVError.unsafe("metadata fixture requires bounded pages")
    }
    for (index, name) in pages.enumerated() {
        guard name == String(format: "page-%05d.bin", index) else {
            throw EVError.unsafe("non-contiguous page sequence")
        }
    }
    let receiptName = ".webreader-completion-v1", planName = "_download-plan.json"
    // FD: A recovery plan may contain credentials in headers *and* URLs,
    // including query/path segments. A completed-only snapshot must never
    // read or duplicate that entire file; preserve it in place for review.
    guard allowRecoveryPlan || !names.contains(planName) else {
        throw EVError.unsafe("recovery plan present; review required")
    }
    guard names.allSatisfy({ ezPageName($0) || $0 == receiptName || $0 == planName }),
          !(names.contains(receiptName) && names.contains(planName)) else {
        throw EVError.unsafe("foreign or ambiguous metadata")
    }
    for name in names {
        guard let st = try lstatChild(directoryFD, name),
              (st.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG), st.st_nlink == 1,
              st.st_size > 0, st.st_size <= (name == planName ? 16 * 1024 * 1024 :
                  name == receiptName ? 64 : 20 * 1024 * 1024) else {
            throw EVError.unsafe("metadata/page is linked, empty, oversized or unsafe")
        }
    }
    func bounded(_ name: String, _ maxLength: Int) throws -> Data {
        let fileFD = name.withCString { openat(directoryFD, $0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC) }
        guard fileFD >= 0 else { throw EVError.system("open-metadata", errno) }
        defer { _ = close(fileFD) }
        var before = stat()
        guard fstat(fileFD, &before) == 0,
              (before.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG), before.st_nlink == 1,
              before.st_size > 0, before.st_size <= maxLength else {
            throw EVError.unsafe("metadata size invalid")
        }
        var result = Data()
        result.reserveCapacity(Int(before.st_size))
        var remaining = Int(before.st_size)
        while remaining > 0 {
            var bytes = [UInt8](repeating: 0, count: min(remaining, 65536))
            let count = try ezRead(fileFD, &bytes)
            guard count > 0 else { throw EVError.unsafe("short metadata read") }
            result.append(contentsOf: bytes.prefix(count))
            remaining -= count
        }
        var after = stat()
        guard fstat(fileFD, &after) == 0, ezStableFile(before, after),
              let attached = try lstatChild(directoryFD, name),
              ezStableFile(before, attached) else {
            throw EVError.unsafe("metadata changed during read")
        }
        return result
    }
    if names.contains(receiptName) {
        let raw = try bounded(receiptName, 64)
        guard raw == Data("WR-OFFLINE-COMPLETE-V1:\(pages.count)\n".utf8) else {
            throw EVError.unsafe("completion receipt count/text mismatch")
        }
    }
    if names.contains(planName) {
        let raw = try bounded(planName, 16 * 1024 * 1024)
        guard let plan = try? JSONDecoder().decode(FBPlanEnvelope.self, from: raw),
              plan.schemaVersion == 1,
              plan.sourceID == source,
              plan.manifest.id == source,
              plan.manga.id == manga,
              plan.chapter.id == chapter,
              !plan.manga.title.isEmpty, !plan.chapter.name.isEmpty,
              // Match the real MangaStatus: Codable String enum; accepting
              // arbitrary text here would certify plans the app cannot load.
              ["unknown", "ongoing", "completed", "hiatus", "cancelled"].contains(plan.manga.status),
              // Plans may persist Authorization/Cookie and other private
              // HTTP request headers. Never duplicate such credentials into
              // another folder in this copy-only synthetic laboratory.
              // A future production implementation needs an explicit
              // encrypted/scrubbed metadata design, not a blanket copy.
              plan.pages.allSatisfy({ $0.headers.isEmpty }),
              !plan.pages.isEmpty, plan.pages.count <= 99_999,
              plan.pages.count >= pages.count,
              plan.queueOrder >= 0,
              plan.pages.enumerated().allSatisfy({ i, p in
                  p.index == i && !p.imageUrl.isEmpty
              }),
              !plan.manifest.name.isEmpty,
              plan.manifest.apiVersion == 1,
              !plan.manifest.domains.isEmpty else {
            throw EVError.unsafe("foreign or malformed recovery plan")
        }
    }
    return (names, pages.count)
}
// END BUILD70_FB_METADATA_SNAPSHOT_LAB

// BEGIN BUILD70_EZ_DESCRIPTOR_PINNED_COPY_LAB
// Synthetic-only, deliberately non-destructive archival proof. Unlike
// renameat(x), a source-path swap cannot redirect reads from this pinned
// chapter fd into a foreign directory. Files are not deleted or restored.
// The app must not call this lab executable; no production authorization.
private func ezStableFile(_ a: stat, _ b: stat) -> Bool {
    guard same(a, b), a.st_nlink == b.st_nlink,
          a.st_size == b.st_size else { return false }
    #if canImport(Darwin)
    return a.st_mtimespec.tv_sec == b.st_mtimespec.tv_sec &&
           a.st_mtimespec.tv_nsec == b.st_mtimespec.tv_nsec &&
           a.st_ctimespec.tv_sec == b.st_ctimespec.tv_sec &&
           a.st_ctimespec.tv_nsec == b.st_ctimespec.tv_nsec
    #else
    return a.st_mtim.tv_sec == b.st_mtim.tv_sec &&
           a.st_mtim.tv_nsec == b.st_mtim.tv_nsec &&
           a.st_ctim.tv_sec == b.st_ctim.tv_sec &&
           a.st_ctim.tv_nsec == b.st_ctim.tv_nsec
    #endif
}

private func ezRegularPage(_ s: stat) -> Bool {
    return (s.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) &&
        s.st_nlink == 1 && s.st_size > 0 && s.st_size <= 20 * 1024 * 1024
}

private func ezPageName(_ name: String) -> Bool {
    let bytes = Array(name.utf8)
    return bytes.count == 14 && name.hasPrefix("page-") && name.hasSuffix(".bin") &&
        bytes[5...9].allSatisfy { $0 >= 48 && $0 <= 57 }
}

private func ezRead(_ fd: Int32, _ bytes: inout [UInt8]) throws -> Int {
    while true {
        let result = bytes.withUnsafeMutableBytes { read(fd, $0.baseAddress, $0.count) }
        if result >= 0 { return result }
        if errno != EINTR { throw EVError.system("read-page", errno) }
    }
}

private func ezWrite(_ fd: Int32, _ bytes: [UInt8], _ count: Int) throws {
    var offset = 0
    while offset < count {
        let written = bytes.withUnsafeBytes { ptr in
            write(fd, ptr.baseAddress!.advanced(by: offset), count - offset)
        }
        if written > 0 { offset += written; continue }
        if written == -1 && errno == EINTR { continue }
        throw EVError.system("write-page", errno)
    }
}

private func ezCompareExact(_ lhs: Int32, _ rhs: Int32, _ expectedSize: Int64) throws {
    guard lseek(lhs, 0, SEEK_SET) == 0, lseek(rhs, 0, SEEK_SET) == 0 else {
        throw EVError.system("seek-for-verify", errno)
    }
    var remaining = expectedSize
    while remaining > 0 {
        var left = [UInt8](repeating: 0, count: Int(min(remaining, 64 * 1024)))
        var right = [UInt8](repeating: 0, count: left.count)
        let a = try ezRead(lhs, &left), b = try ezRead(rhs, &right)
        guard a == left.count, b == right.count, left == right else {
            throw EVError.unsafe("copy differs from pinned original")
        }
        remaining -= Int64(a)
    }
    var one = [UInt8](repeating: 0, count: 1)
    guard try ezRead(lhs, &one) == 0, try ezRead(rhs, &one) == 0 else {
        throw EVError.unsafe("copy size drift")
    }
}

private func ezPauseForAdversary(_ rootFD: Int32) throws {
    guard ProcessInfo.processInfo.environment["WEBREADER_EZ_RACE_GATE"] == "1" else { return }
    let readyName = ".ez_before_copy_ready", goName = ".ez_before_copy_go"
    let markerFD = readyName.withCString {
        openat(rootFD, $0, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
    }
    guard markerFD >= 0 else { throw EVError.system("snapshot-race-ready", errno) }
    let token = [UInt8]("READY\n".utf8)
    do { try ezWrite(markerFD, token, token.count) } catch {
        _ = close(markerFD); throw error
    }
    let synced = fsync(markerFD)
    _ = close(markerFD)
    guard synced == 0 else { throw EVError.system("snapshot-race-sync", errno) }
    for _ in 0..<400 {
        let signalFD = goName.withCString { openat(rootFD, $0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC) }
        if signalFD >= 0 {
            defer { _ = close(signalFD) }
            var s = stat()
            guard fstat(signalFD, &s) == 0, ezRegularPageSignal(s) else {
                throw EVError.unsafe("bad race-release marker")
            }
            return
        }
        guard errno == ENOENT else { throw EVError.system("snapshot-race-wait", errno) }
        usleep(15_000)
    }
    throw EVError.unsafe("snapshot race gate timed out")
}

private func ezRegularPageSignal(_ s: stat) -> Bool {
    return (s.st_mode & mode_t(S_IFMT)) == mode_t(S_IFREG) && s.st_nlink == 1
}

private func ezCopySnapshot(_ sourceParent: Int32, _ sourceName: String,
                            _ quarantineParent: Int32, _ destName: String,
                            _ rootFD: Int32, _ expected: Identity,
                            owner: (String,String,String)? = nil,
                            sealedOnly: Bool = false) throws -> String {
    let pinnedFD = try openChild(sourceParent, sourceName)
    defer { _ = close(pinnedFD) }
    var initial = stat()
    guard fstat(pinnedFD, &initial) == 0, Identity(initial) == expected,
          let leaf = try lstatChild(sourceParent, sourceName),
          same(leaf, initial), isDirectory(initial) else {
        throw EVError.unsafe("pinned source mismatch")
    }
    // Enumerating by descriptor, not by re-resolving the source pathname.
    let inventory = try owner.map { try fbInventory(pinnedFD, $0.0, $0.1, $0.2,
                                                    allowRecoveryPlan: !sealedOnly) }
    let entries = try inventory?.names ?? directoryEntries(pinnedFD).sorted()
    guard !entries.isEmpty, entries.count <= 100_000,
          (owner != nil || entries.allSatisfy(ezPageName)) else {
        throw EVError.unsafe("snapshot supports only validated synthetic files")
    }
    // Pin every page's metadata BEFORE the deliberate test race gate.
    // If the source basename or any page file changes, never certify the copy.
    var initialPages: [String: stat] = [:]
    for name in entries {
        guard let page = try lstatChild(pinnedFD, name),
              fbAdmittedFile(page, name, metadata: owner != nil) else {
            throw EVError.unsafe("unsafe file before pinned snapshot")
        }
        initialPages[name] = page
    }
    try ezPauseForAdversary(rootFD)
    guard destName.withCString({ mkdirat(quarantineParent, $0, 0o700) }) == 0 else {
        throw EVError.system("mkdirat-exclusive-snapshot", errno)
    }
    let destFD = try openChild(quarantineParent, destName)
    defer { _ = close(destFD) }
    var total: Int64 = 0
    for (index, name) in entries.enumerated() {
        guard let before = try lstatChild(pinnedFD, name),
              let admitted = initialPages[name],
              fbAdmittedFile(before, name, metadata: owner != nil),
              ezStableFile(admitted, before) else {
            throw EVError.unsafe("page changed before opening")
        }
        // FL: file-scoped defer. A defer directly inside the for-loop body
        // runs at function exit, leaking 2 FDs per page for long chapters.
        // The lexical do scope closes both descriptors before the next page.
        do {
        let srcFD = name.withCString { openat(pinnedFD, $0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC) }
        guard srcFD >= 0 else { throw EVError.system("openat-source-file", errno) }
        defer { _ = close(srcFD) }
        var opened = stat()
        guard fstat(srcFD, &opened) == 0, ezStableFile(before, opened) else {
            throw EVError.unsafe("page identity drift before copy")
        }
        let dstFD = name.withCString {
            openat(destFD, $0, O_RDWR | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        }
        guard dstFD >= 0 else { throw EVError.system("create-exclusive-page", errno) }
        defer { _ = close(dstFD) }
        var left = Int64(opened.st_size)
        while left > 0 {
            var bytes = [UInt8](repeating: 0, count: Int(min(left, 64 * 1024)))
            let count = try ezRead(srcFD, &bytes)
            guard count > 0 else { throw EVError.unsafe("page truncated mid-copy") }
            try ezWrite(dstFD, bytes, count)
            left -= Int64(count)
        }
        guard fsync(dstFD) == 0 else { throw EVError.system("fsync-copy-file", errno) }
        try ezCompareExact(srcFD, dstFD, Int64(opened.st_size))
        var after = stat(), copied = stat()
        guard fstat(srcFD, &after) == 0, ezStableFile(opened, after),
              fstat(dstFD, &copied) == 0,
              fbAdmittedFile(copied, name, metadata: owner != nil),
              copied.st_size == opened.st_size,
              let attached = try lstatChild(pinnedFD, name),
              ezStableFile(opened, attached) else {
            throw EVError.unsafe("source page changed while copying")
        }
        total += Int64(opened.st_size)
        // Synthetic crash point: partial quarantine must be left untouched.
        if index == 0 && ProcessInfo.processInfo.environment["WEBREADER_EZ_CRASH_AFTER_FIRST_PAGE"] == "1" {
            _ = fsync(destFD)
            _ = fsync(quarantineParent)
            exit(86)
        }
        } // FL: close this page's pinned source and destination FDs.
    }
    // Re-list to detect extra or swapped names; validate exact source binding.
    if let owner = owner {
        guard try fbInventory(pinnedFD, owner.0, owner.1, owner.2,
                              allowRecoveryPlan: !sealedOnly).names == entries else {
            throw EVError.unsafe("snapshot metadata drift")
        }
    }
    guard try directoryEntries(pinnedFD).sorted() == entries,
          let bound = try lstatChild(sourceParent, sourceName),
          same(initial, bound),
          let copiedDir = try lstatChild(quarantineParent, destName),
          isDirectory(copiedDir) else {
        throw EVError.unsafe("snapshot source path changed; preserve staged copy")
    }
    var destStat = stat()
    guard fstat(destFD, &destStat) == 0, same(copiedDir, destStat) else {
        throw EVError.unsafe("snapshot destination changed; preserve and review")
    }
    guard fsync(destFD) == 0, fsync(quarantineParent) == 0 else {
        throw EVError.system("fsync-snapshot-parents", errno)
    }
    return "{\"status\":\"copy_verified\",\"device\":\"\(expected.device)\",\"inode\":\"\(expected.inode)\",\"pages\":\(inventory?.pages ?? entries.count),\"bytes\":\(total)}"
}

// Read-only verification across two pinned directory descriptors. Required
// after restart because "file exists" does not imply a valid completed copy.
// Never infers permission to delete either directory or retire SQLite rows.
private func ezVerifySnapshot(_ sourceParent: Int32, _ sourceName: String,
                              _ quarantineParent: Int32, _ destName: String,
                              _ expected: Identity,
                              owner: (String,String,String)? = nil,
                              sealedOnly: Bool = false,
                              byteBudget: Int64? = nil,
                              rootForRace: Int32? = nil) throws -> String {
    let sourceFD = try openChild(sourceParent, sourceName)
    defer { _ = close(sourceFD) }
    let snapshotFD = try openChild(quarantineParent, destName)
    defer { _ = close(snapshotFD) }
    var original = stat(), snapshot = stat()
    guard fstat(sourceFD, &original) == 0,
          fstat(snapshotFD, &snapshot) == 0,
          Identity(original) == expected, isDirectory(snapshot),
          let originalPath = try lstatChild(sourceParent, sourceName),
          let snapshotPath = try lstatChild(quarantineParent, destName),
          same(original, originalPath), same(snapshot, snapshotPath) else {
        throw EVError.unsafe("snapshot verification directory binding mismatch")
    }
    // FM: both directory descriptors are already open; the test gate can
    // swap path names, but it cannot redirect a read through either FD.
    if let raceRoot = rootForRace { try ezPauseForAdversary(raceRoot) }
    let inventory = try owner.map { try fbInventory(sourceFD, $0.0, $0.1, $0.2,
                                                    allowRecoveryPlan: !sealedOnly) }
    let originalNames = try inventory?.names ?? directoryEntries(sourceFD).sorted()
    let copiedNames = try directoryEntries(snapshotFD).sorted()
    if let owner = owner {
        guard try fbInventory(snapshotFD, owner.0, owner.1, owner.2,
                              allowRecoveryPlan: !sealedOnly).names == copiedNames else {
            throw EVError.unsafe("copied metadata invalid")
        }
    }
    guard !originalNames.isEmpty, originalNames.count <= 100_000,
          originalNames == copiedNames,
          (owner != nil || originalNames.allSatisfy(ezPageName)) else {
        throw EVError.unsafe("snapshot inventory mismatch")
    }
    var bytes: Int64 = 0
    for name in originalNames {
        guard let srcBefore = try lstatChild(sourceFD, name),
              let dstBefore = try lstatChild(snapshotFD, name),
              fbAdmittedFile(srcBefore, name, metadata: owner != nil),
              fbAdmittedFile(dstBefore, name, metadata: owner != nil),
              srcBefore.st_size == dstBefore.st_size else {
            throw EVError.unsafe("snapshot page metadata mismatch")
        }
        // FM: enforce budget before opening/reading the next file. This is a
        // bound on verification work, not a reservation of future disk space.
        if let ceiling = byteBudget {
            guard srcBefore.st_size <= ceiling - bytes else {
                throw EVError.unsafe("snapshot verified bytes exceed FM quota")
            }
        }
        // FL: scope the pair of verification FDs to one page only.
        do {
        let src = name.withCString { openat(sourceFD, $0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC) }
        guard src >= 0 else { throw EVError.system("verify-open-source", errno) }
        defer { _ = close(src) }
        let dst = name.withCString { openat(snapshotFD, $0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC) }
        guard dst >= 0 else { throw EVError.system("verify-open-snapshot", errno) }
        defer { _ = close(dst) }
        var srcOpen = stat(), dstOpen = stat()
        guard fstat(src, &srcOpen) == 0, fstat(dst, &dstOpen) == 0,
              ezStableFile(srcBefore, srcOpen), ezStableFile(dstBefore, dstOpen) else {
            throw EVError.unsafe("snapshot pages changed during open")
        }
        try ezCompareExact(src, dst, Int64(srcBefore.st_size))
        var srcAfter = stat(), dstAfter = stat()
        guard fstat(src, &srcAfter) == 0, fstat(dst, &dstAfter) == 0,
              ezStableFile(srcOpen, srcAfter), ezStableFile(dstOpen, dstAfter),
              let srcAttached = try lstatChild(sourceFD, name),
              let dstAttached = try lstatChild(snapshotFD, name),
              ezStableFile(srcOpen, srcAttached),
              ezStableFile(dstOpen, dstAttached) else {
            throw EVError.unsafe("snapshot file drift after comparison")
        }
        bytes += Int64(srcBefore.st_size)
        } // FL: both verify FDs close before the next file.
    }
    guard try directoryEntries(sourceFD).sorted() == originalNames,
          try directoryEntries(snapshotFD).sorted() == copiedNames,
          let currentSource = try lstatChild(sourceParent, sourceName),
          let currentSnapshot = try lstatChild(quarantineParent, destName),
          same(original, currentSource), same(snapshot, currentSnapshot) else {
        throw EVError.unsafe("snapshot changed after verification")
    }
    return "{\"status\":\"copy_verified\",\"device\":\"\(expected.device)\",\"inode\":\"\(expected.inode)\",\"pages\":\(inventory?.pages ?? originalNames.count),\"bytes\":\(bytes)}"
}
// END BUILD70_EZ_DESCRIPTOR_PINNED_COPY_LAB

// BEGIN BUILD70_FM_PINNED_READONLY_QUOTA
// New checks NEVER create snapshots or mutate the SQLite/production library.
// All operations are confined to the EV-marked synthetic test root.
private let fmChapterBudget: Int64 = 512 * 1024 * 1024
private let fmMaximumPages = 5_000

private func fmBudgetPinned(_ parent: Int32, _ leaf: String,
                            _ quarantine: Int32,
                            _ owner: (String,String,String)) throws -> String {
    let directory = try openChild(parent, leaf)
    defer { _ = close(directory) }
    var original = stat()
    guard fstat(directory, &original) == 0,
          let attached = try lstatChild(parent, leaf),
          same(original, attached), isDirectory(original) else {
        throw EVError.unsafe("FM budget original is not pinned to canonical source")
    }
    let inventory = try fbInventory(directory, owner.0, owner.1, owner.2,
                                    allowRecoveryPlan: false)
    guard inventory.pages >= 1 && inventory.pages <= fmMaximumPages else {
        throw EVError.unsafe("FM page limit exceeded")
    }
    var total: Int64 = 0
    for name in inventory.names {
        guard let before = try lstatChild(directory, name),
              fbAdmittedFile(before, name, metadata: true),
              Int64(before.st_size) <= fmChapterBudget - total else {
            throw EVError.unsafe("FM chapter snapshot byte budget exceeded")
        }
        do {
            let fd = name.withCString {
                openat(directory, $0, O_RDONLY | O_NOFOLLOW | O_CLOEXEC)
            }
            guard fd >= 0 else { throw EVError.system("fm-open-page", errno) }
            defer { _ = close(fd) }
            var opened = stat()
            guard fstat(fd, &opened) == 0, ezStableFile(before, opened) else {
                throw EVError.unsafe("FM file changed before budget measurement")
            }
            total += Int64(before.st_size)
            var after = stat()
            guard fstat(fd, &after) == 0, ezStableFile(opened, after),
                  let current = try lstatChild(directory, name),
                  ezStableFile(opened, current) else {
                throw EVError.unsafe("FM file changed during budget measurement")
            }
        } // descriptor closed on each entry
    }
    guard try directoryEntries(directory).sorted() == inventory.names,
          let after = try lstatChild(parent, leaf), same(original, after) else {
        throw EVError.unsafe("FM directory rebound during quota check")
    }
    var statv = statvfs()
    guard fstatvfs(quarantine, &statv) == 0 else {
        throw EVError.system("fm-statvfs", errno)
    }
    let (free, overflow) = UInt64(statv.f_bavail).multipliedReportingOverflow(
        by: UInt64(statv.f_frsize))
    guard !overflow else { throw EVError.unsafe("FM free-space overflow") }
    // FM does not reserve free bytes; this figure is advisory and can age.
    return "{\"status\":\"observed\",\"device\":\"\(Identity(original).device)\",\"inode\":\"\(Identity(original).inode)\",\"pages\":\(inventory.pages),\"bytes\":\(total),\"free_bytes\":\(free)}"
}
// END BUILD70_FM_PINNED_READONLY_QUOTA

private func run(_ arguments: [String]) throws -> String {
    guard arguments.count == 6 || arguments.count == 8 else {
        throw EVError.unsafe("usage: inspect|classify|stage root source manga chapter ev_name [device inode]")
    }
    let action = arguments[0]
    let root = arguments[1]
    let source = arguments[2], manga = arguments[3]
    let leaf = try component(arguments[4])
    let dest = arguments[5]
    guard dest.hasPrefix("ev_"), dest.utf8.count == 35,
          dest.dropFirst(3).utf8.allSatisfy({ ($0 >= 48 && $0 <= 57) || ($0 >= 97 && $0 <= 102) }) else {
        throw EVError.unsafe("quarantine name must be ev_ + 32 lowercase hex")
    }
    let expected: Identity?
    if arguments.count == 8 {
        expected = Identity(device: arguments[6], inode: arguments[7])
        if expected == nil { throw EVError.unsafe("invalid expected identity") }
    } else { expected = nil }
    return try withContext(root: root, source: source, manga: manga) { parent, quarantine, rootFD in
        switch action {
        case "inspect":
            guard expected == nil else { throw EVError.unsafe("inspect takes no identity") }
            return try inspectChapter(parent, leaf).json("observed")
        case "classify":
            guard let expected = expected else { throw EVError.unsafe("classification requires expected identity") }
            let src = try lstatChild(parent, leaf)
            let dst = try lstatChild(quarantine, dest)
            if let src = src, Identity(src) == expected, isDirectory(src), dst == nil {
                return expected.json("at_source")
            }
            if src == nil, let dst = dst, Identity(dst) == expected, isDirectory(dst) {
                return expected.json("in_quarantine")
            }
            return expected.json("needs_review")
        // FD strict completed-only path: do not open/copy recovery-plan
        // JSON under any circumstances, even if its headers are empty.
        case "budgetsealed":
            guard expected == nil else { throw EVError.unsafe("budgetsealed takes no identity") }
            return try fmBudgetPinned(parent, leaf, quarantine, (source,manga,leaf))
        case "holdverifysealed":
            guard let expected = expected else {
                throw EVError.unsafe("holdverifysealed requires persisted directory identity")
            }
            // Descriptor-held byte-for-byte comparison, bounded by 512 MiB.
            // Its success NEVER authorizes any unlink or rename operation.
            return try ezVerifySnapshot(parent, leaf, quarantine, dest, expected,
                                        owner: (source,manga,leaf), sealedOnly: true,
                                        byteBudget: fmChapterBudget,
                                        rootForRace: rootFD)
        case "inspectsealed":
            guard expected == nil else { throw EVError.unsafe("inspectsealed takes no identity") }
            return try inspectChapter(parent, leaf, owner: (source,manga,leaf),
                                      sealedOnly: true).json("observed")
        case "verifycopysealed":
            guard let expected = expected else { throw EVError.unsafe("verifycopysealed requires identity") }
            return try ezVerifySnapshot(parent, leaf, quarantine, dest, expected,
                                        owner: (source,manga,leaf), sealedOnly: true)
        case "snapshotsealed":
            guard let expected = expected else { throw EVError.unsafe("snapshotsealed requires identity") }
            guard try inspectChapter(parent, leaf, owner: (source,manga,leaf),
                                     sealedOnly: true) == expected else {
                throw EVError.unsafe("snapshotsealed identity drift")
            }
            guard try lstatChild(quarantine, dest) == nil else {
                throw EVError.unsafe("snapshotsealed destination exists")
            }
            return try ezCopySnapshot(parent, leaf, quarantine, dest, rootFD, expected,
                                      owner: (source,manga,leaf), sealedOnly: true)
        case "inspectmeta":
            guard expected == nil else { throw EVError.unsafe("inspectmeta takes no identity") }
            return try inspectChapter(parent, leaf, owner: (source,manga,leaf)).json("observed")
        case "verifycopymeta":
            guard let expected = expected else { throw EVError.unsafe("verifycopymeta requires identity") }
            return try ezVerifySnapshot(parent, leaf, quarantine, dest, expected,
                                        owner: (source,manga,leaf))
        case "snapshotmeta":
            guard let expected = expected else { throw EVError.unsafe("snapshotmeta requires identity") }
            guard try inspectChapter(parent, leaf, owner: (source,manga,leaf)) == expected else {
                throw EVError.unsafe("snapshotmeta identity drift")
            }
            guard try lstatChild(quarantine, dest) == nil else {
                throw EVError.unsafe("snapshotmeta destination exists")
            }
            return try ezCopySnapshot(parent, leaf, quarantine, dest, rootFD, expected,
                                      owner: (source,manga,leaf))
        case "verifycopy":
            guard let expected = expected else { throw EVError.unsafe("verifycopy requires expected identity") }
            return try ezVerifySnapshot(parent, leaf, quarantine, dest, expected)
        case "snapshot":
            guard let expected = expected else { throw EVError.unsafe("snapshot requires expected identity") }
            guard try inspectChapter(parent, leaf) == expected else {
                throw EVError.unsafe("snapshot source identity differs")
            }
            guard try lstatChild(quarantine, dest) == nil else {
                throw EVError.unsafe("snapshot destination already occupied")
            }
            return try ezCopySnapshot(parent, leaf, quarantine, dest, rootFD, expected)
        case "stage":
            guard let expected = expected else { throw EVError.unsafe("stage requires persisted identity") }
            guard try inspectChapter(parent, leaf) == expected else {
                throw EVError.unsafe("persisted source identity differs")
            }
            guard try lstatChild(quarantine, dest) == nil else {
                throw EVError.unsafe("quarantine destination occupied")
            }
            // Keep a descriptor to the verified source directory across the
            // rename. This detects more races, but cannot make rename name-based
            // lookup conditional on this fd's inode identity.
            let pinned = try openChild(parent, leaf)
            defer { _ = close(pinned) }
            var pinnedStat = stat()
            guard fstat(pinned, &pinnedStat) == 0,
                  Identity(pinnedStat) == expected else {
                throw EVError.unsafe("source inode changed before rename")
            }
            try eySyntheticPreRenameGate(rootFD)
            try moveExclusively(parent, leaf, quarantine, dest)
            var afterPinned = stat()
            guard let after = try lstatChild(quarantine, dest),
                  fstat(pinned, &afterPinned) == 0,
                  Identity(afterPinned) == expected,
                  isDirectory(after), Identity(after) == expected,
                  try lstatChild(parent, leaf) == nil else {
                throw EVError.unsafe("post-rename mismatch: preserve and review quarantine")
            }
            return expected.json("in_quarantine")
        default: throw EVError.unsafe("unknown action")
        }
    }
}

do {
    print(try run(Array(CommandLine.arguments.dropFirst())))
} catch {
    // No user-controlled filename is echoed; errors never trigger deletion.
    fputs("\(error)\n", stderr)
    exit(2)
}
