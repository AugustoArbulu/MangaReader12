#!/usr/bin/env python3
"""Compile real iOS12 IPA auditor on macOS; test adversarial ZIP fixtures.

The code examines metadata and SHA-256 without extraction or installation.
Optional --real-ipa verifies the CI packaged WebReader Build56 as well.
No networking, root privileges, appinst or production signing keys.
"""
import argparse
import hashlib
import io
from pathlib import Path
import plistlib
import stat
import subprocess
import tempfile
import warnings
import zipfile

ROOT = Path(__file__).resolve().parent.parent
SOURCES = [
    ROOT / "MangaReader12/Core/WebReaderStrictJSON.swift",
    ROOT / "MangaReader12/Core/WebReaderUpdateManifestVerifier.swift",
    ROOT / "MangaReader12/Core/WebReaderNativeIPAAuditor.swift",
]
PREFIX = "Payload/MangaReader12.app/"

HARNESS = r'''
import Foundation

func fail(_ reason: String) -> Never { fatalError(reason) }
let a = CommandLine.arguments
if a.count != 8 { fail("usage: file sha size build minimum installedBuild validFlag") }
let file = URL(fileURLWithPath: a[1])
let size = Int64(a[3])!
let build = Int(a[4])!
let minimum = a[5]
let installed = Int(a[6])!
let shouldPass = a[7] == "pass"
let metadata = WebReaderVerifiedUpdate(
    build: build, minimumIOS: minimum,
    ipaURL: URL(string:
        "https://github.com/AugustoArbulu/MangaReader12/releases/download/build" +
        String(build) + "/WebReader-iOS12-unsigned.ipa"
    )!,
    ipaSize: size, sha256: a[2],
    publishedAt: "2026-11-05T03:00:00Z", releaseNotes: []
)
do {
    let result = try WebReaderNativeIPAAuditor.inspect(
        ipaURL: file, signedUpdate: metadata,
        installedBuild: installed,
        installedIOS: OperatingSystemVersion(majorVersion: 12, minorVersion: 5, patchVersion: 8)
    )
    if !shouldPass { fail("malicious IPA was accepted: " + a[1]) }
    if result.bundleID != "com.example.MangaReader12" ||
        result.build != build || result.verifiedSHA256 != a[2] ||
        result.minimumIOS != minimum || result.zipEntries < 2 {
        fail("wrong native IPA result")
    }
    print("PASS valid IPA: " + file.lastPathComponent)
} catch {
    if shouldPass { fail("valid IPA rejected: " + String(describing: error)) }
    print("PASS rejected malicious IPA: " + file.lastPathComponent)
}
'''

def make_plist(*, build="57", bundle="com.example.MangaReader12",
               display="WebReader", minimum="12.0"):
    return plistlib.dumps({
        "CFBundleIdentifier": bundle,
        "CFBundleExecutable": "MangaReader12",
        "CFBundleDisplayName": display,
        "CFBundleVersion": build,
        "MinimumOSVersion": minimum,
    }, fmt=plistlib.FMT_BINARY)

def make_ipa(path: Path, *, plist=None, info_compression=zipfile.ZIP_DEFLATED,
             extras=(), include_binary=True):
    if plist is None:
        plist = make_plist()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("Payload/", b"", compress_type=zipfile.ZIP_STORED)
            z.writestr("Payload/MangaReader12.app/", b"", compress_type=zipfile.ZIP_STORED)
            z.writestr(PREFIX + "Info.plist", plist, compress_type=info_compression)
            if include_binary:
                z.writestr(PREFIX + "MangaReader12", b"MACHO-FIXTURE",
                           compress_type=zipfile.ZIP_STORED)
            z.writestr(PREFIX + "Assets.car", b"placeholder" * 15,
                       compress_type=zipfile.ZIP_DEFLATED)
            for name, content in extras:
                if isinstance(content, zipfile.ZipInfo):
                    z.writestr(content, b"/etc/passwd")
                else:
                    z.writestr(name, content)

def mutate_crc(path: Path):
    raw = bytearray(path.read_bytes())
    # Mutate ONLY Info.plist's central-directory CRC, not the root directory.
    target = (PREFIX + "Info.plist").encode("utf-8")
    off = 0
    found = False
    while True:
        off = raw.find(b"PK\x01\x02", off)
        if off < 0:
            break
        name_len = int.from_bytes(raw[off + 28:off + 30], "little")
        extra_len = int.from_bytes(raw[off + 30:off + 32], "little")
        comment_len = int.from_bytes(raw[off + 32:off + 34], "little")
        name = raw[off + 46:off + 46 + name_len]
        if name == target:
            raw[off + 16] ^= 1
            found = True
            break
        off += 46 + name_len + extra_len + comment_len
    assert found, "missing central Info.plist"
    path.write_bytes(raw)

def mutate_local_name(path: Path):
    raw = bytearray(path.read_bytes())
    needle = b"Payload/MangaReader12.app/Info.plist"
    pos = raw.index(needle)
    raw[pos + len(needle) - 1] = ord("X")
    path.write_bytes(raw)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--real-ipa", type=Path, default=None)
    opts = p.parse_args()

    with tempfile.TemporaryDirectory(prefix="webreader-ipa-auditor-") as temp:
        temp = Path(temp)
        main = temp / "main.swift"
        binary = temp / "auditor"
        main.write_text(HARNESS, encoding="utf-8")
        subprocess.run(
            ["swiftc", "-swift-version", "5", *map(str, SOURCES),
             str(main), "-framework", "Security", "-o", str(binary)],
            check=True
        )
        cases = []

        def case(name, *, should_pass, build=57, minimum="12.0",
                 installed=56, builder=None):
            path = temp / (name + ".ipa")
            if builder:
                builder(path)
            else:
                make_ipa(path)
            cases.append((path, should_pass, build, minimum, installed))

        case("valid-deflate", should_pass=True)
        case("valid-stored", should_pass=True,
             builder=lambda f: make_ipa(f, info_compression=zipfile.ZIP_STORED))
        case("wrong-bundle", should_pass=False,
             builder=lambda f: make_ipa(f, plist=make_plist(bundle="com.example.Malware")))
        case("wrong-display", should_pass=False,
             builder=lambda f: make_ipa(f, plist=make_plist(display="NotWebReader")))
        case("old-build", should_pass=False, installed=57)
        case("signed-build-mismatch", should_pass=False, build=58)
        case("minimum-ios13", should_pass=False, minimum="13.0",
             builder=lambda f: make_ipa(f, plist=make_plist(minimum="13.0")))
        case("signed-ios-mismatch", should_pass=False, minimum="13.0")
        case("missing-executable", should_pass=False,
             builder=lambda f: make_ipa(f, include_binary=False))
        case("extra-bundle", should_pass=False,
             builder=lambda f: make_ipa(f, extras=[
                 ("Payload/Other.app/Info.plist", b"other"),
             ]))
        case("traversal", should_pass=False,
             builder=lambda f: make_ipa(f, extras=[
                 (PREFIX + "../../escape", b"bad"),
             ]))
        case("duplicate-filename", should_pass=False,
             builder=lambda f: make_ipa(f, extras=[
                 (PREFIX + "Info.plist", b"duplicate"),
             ]))
        link = zipfile.ZipInfo(PREFIX + "link")
        link.create_system = 3
        link.external_attr = ((stat.S_IFLNK | 0o777) << 16)
        case("symlink", should_pass=False,
             builder=lambda f: make_ipa(f, extras=[("symlink", link)]))
        case("bad-crc", should_pass=False, builder=lambda f: (
            make_ipa(f), mutate_crc(f)))
        case("bad-local-header", should_pass=False, builder=lambda f: (
            make_ipa(f), mutate_local_name(f)))
        case("truncated-zip", should_pass=False, builder=lambda f: (
            make_ipa(f), f.write_bytes(f.read_bytes()[:-9])))
        case("other-compression", should_pass=False,
             builder=lambda f: make_ipa(f, info_compression=zipfile.ZIP_BZIP2))

        for path, should_pass, build, minimum, installed in cases:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            subprocess.run([
                str(binary), str(path), digest, str(path.stat().st_size),
                str(build), minimum, str(installed),
                "pass" if should_pass else "reject"
            ], check=True)

        # Tested separately from fixtures: the actual unsigned Build56 IPA
        # compiled by CI must match signed metadata for build 56.
        if opts.real_ipa:
            f = opts.real_ipa.resolve(strict=True)
            digest = hashlib.sha256(f.read_bytes()).hexdigest()
            subprocess.run([
                str(binary), str(f), digest, str(f.stat().st_size),
                "56", "12.0", "55", "pass"
            ], check=True)

    print("PASS native iOS12 read-only IPA identity/ZIP/SHA256 preflight")

if __name__ == "__main__":
    main()
