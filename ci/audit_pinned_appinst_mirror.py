#!/usr/bin/env python3
"""Read-only verification of the pinned Legacy-Me appinst rootful mirror package.

Runs in a HOST CI runner, not on a jailbroken phone. The mirror is NOT an
official publisher; its published digest must never be interpreted as a
publisher signature. Nothing downloaded is extracted or executed.
"""
from dataclasses import dataclass
import bz2
import gzip
import hashlib
import zlib
import json
from pathlib import Path
import sys
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from audit_appinst_deb import audit_bytes, PackageRejected

MIRROR_URL = (
    "https://raw.githubusercontent.com/Legacy-Me/repo/main/debs/"
    "ai.akemi.appinst_2.1.1_iphoneos-arm%7Eakemi-git-"
    "235aca6cddfbdc9fa87fcb5b2aec2df37ed6d65a.deb"
)
MIRROR_SHA256 = "5997771183c39eb8b5e13fc2bb511b1dfcb7eb39d3f10c9092ab088ec34aae09"
OFFICIAL_BASE = "https://cydia.akemi.ai/"
OFFICIAL_INDICES = ("Packages.bz2", "Packages.gz", "Packages")
MAX_ARCHIVE_RESPONSE = 128 * 1024
MAX_COMPRESSED_INDEX = 8 * 1024 * 1024
MAX_DECOMPRESSED_INDEX = 24 * 1024 * 1024

class VerificationError(RuntimeError):
    pass

def fetch_limited(url, limit, allowed_host):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != allowed_host or parts.username or parts.password:
        raise VerificationError("unapproved HTTPS origin")
    request = Request(url, headers={"User-Agent": "WebReaderProvenanceAudit/1.0"})
    with urlopen(request, timeout=15) as response:
        effective = urlsplit(response.geturl())
        if effective.scheme != "https" or effective.hostname != allowed_host:
            raise VerificationError("unapproved redirected host")
        data = response.read(limit + 1)
        if not data or len(data) > limit:
            raise VerificationError("empty or oversized response")
        return data

def unpack_index(raw: bytes, name: str) -> str:
    try:
        if name.endswith(".bz2"):
            dc = bz2.BZ2Decompressor()
            data = dc.decompress(raw, max_length=MAX_DECOMPRESSED_INDEX + 1)
            if not dc.eof:
                raise VerificationError("incomplete or oversized BZ2 index")
        elif name.endswith(".gz"):
            # gzip.decompress has no length guard; use streaming inflate.
            dc = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
            data = dc.decompress(raw, MAX_DECOMPRESSED_INDEX + 1)
            if not dc.eof:
                raise VerificationError("incomplete or oversized gzip index")
        else:
            data = raw
        if len(data) > MAX_DECOMPRESSED_INDEX:
            raise VerificationError("APT index oversized")
        return data.decode("utf-8")
    except (OSError, ValueError, EOFError, UnicodeError, zlib.error) as e:
        if isinstance(e, VerificationError):
            raise
        raise VerificationError("invalid APT index") from e

def package_stanzas(index: str):
    for paragraph in index.split("\n\n"):
        fields = {}
        for line in paragraph.splitlines():
            if line.startswith((" ", "\t")):
                continue
            if ": " not in line:
                continue
            key, value = line.split(": ", 1)
            if key not in fields:
                fields[key] = value.strip()
        if fields:
            yield fields

def matching_official_entry(index: str):
    for fields in package_stanzas(index):
        if (fields.get("Package") == "ai.akemi.appinst"
            and fields.get("Version") == "2.1.1"
            and fields.get("Architecture") == "iphoneos-arm"):
            return {
                "filename": fields.get("Filename"),
                "size": fields.get("Size"),
                "sha256": fields.get("SHA256"),
            }
    return None

def main():
    deb = fetch_limited(MIRROR_URL, MAX_ARCHIVE_RESPONSE, "raw.githubusercontent.com")
    digest = hashlib.sha256(deb).hexdigest()
    if digest != MIRROR_SHA256:
        raise VerificationError("mirror byte digest does not match pinned listing")
    audit = audit_bytes(deb)
    if audit["architecture"] != "iphoneos-arm" or audit["version"] != "2.1.1":
        raise VerificationError("wrong package contents")
    official = {"status": "unavailable", "entry": None, "digest_matches": None}
    errors = []
    for suffix in OFFICIAL_INDICES:
        try:
            compressed = fetch_limited(
                OFFICIAL_BASE + suffix,
                MAX_COMPRESSED_INDEX, "cydia.akemi.ai"
            )
            source = unpack_index(compressed, suffix)
            entry = matching_official_entry(source)
            if entry is None:
                official = {"status": "package-not-in-index", "entry": None,
                            "digest_matches": None}
                continue
            official = {
                "status": "entry-found-on-publisher-https-host",
                "entry": entry,
                "digest_matches": entry["sha256"] == digest,
            }
            break
        except (URLError, TimeoutError, OSError, VerificationError) as error:
            errors.append(suffix + ": " + str(error)[:160])
    result = {
        "mirror_digest_verified": True,
        "mirror_sha256": digest,
        "package": audit["package"],
        "version": audit["version"],
        "architecture": audit["architecture"],
        "package_bytes": len(deb),
        "installed_executable_path": audit["installed_appinst_path"],
        "appinst_executable_sha256_from_mirror": audit["appinst_executable_sha256"],
        "appinst_executable_size_from_mirror": audit["appinst_executable_bytes"],
        "maintainer_script_names": audit["maintainer_scripts"],
        "publisher_index": official,
        "publisher_index_errors": errors,
        "iphone_installed_file_compared": False,
        "official_origin_verified": False,
        "permission_to_install_granted": False,
        "execution_performed": False,
    }
    print(json.dumps(result, indent=2))
    if official["digest_matches"] is False:
        raise VerificationError("publisher index digest differs from mirror file")
    # A matching index is NOT a signature of the package, and we have not
    # compared the version installed on the user's iPhone.
    print("PASS: mirror DEB structurally inspected; publisher authenticity NOT established.")

if __name__ == "__main__":
    main()
