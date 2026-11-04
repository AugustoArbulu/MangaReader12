#!/usr/bin/env python3
"""Offline test fixtures for read-only appinst .deb audit. No jailbreak needed."""
import gzip
import io
import lzma
import tarfile
import unittest

from audit_appinst_deb import PackageRejected, audit_bytes


def tar_archive(entries):
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as f:
        for path, contents, kind in entries:
            info = tarfile.TarInfo(path)
            if kind == "file":
                info.size = len(contents)
                f.addfile(info, io.BytesIO(contents))
            elif kind == "link":
                info.type = tarfile.SYMTYPE
                info.linkname = "/etc/passwd"
                f.addfile(info)
            elif kind == "setuid":
                info.size = len(contents)
                info.mode = 0o4755
                f.addfile(info, io.BytesIO(contents))
    return gzip.compress(raw.getvalue())


def ar_member(name, content):
    assert len(name) <= 15
    header = (
        f"{name+'/':<16}{0:<12}{0:<6}{0:<6}{100644:<8}{len(content):<10}"
    ).encode("ascii") + b"\x60\n"
    assert len(header) == 60
    return header + content + (b"\n" if len(content) % 2 else b"")


def package(control_extra=(), data_extra=(), changes=None):
    metadata = (
        b"Package: ai.akemi.appinst\nVersion: 2.1.1\n"
        b"Architecture: iphoneos-arm\nDescription: Fixture only\n"
    )
    controls = [("control", metadata, "file")] + list(control_extra)
    binaries = [("./usr/bin/appinst", b"FAKE-MACHO-NO-EXECUTION", "file")]
    binaries += list(data_extra)
    members = [
        ("debian-binary", b"2.0\n"),
        ("control.tar.gz", tar_archive(controls)),
        ("data.tar.gz", tar_archive(binaries))
    ]
    if changes:
        members = changes(members)
    return b"!<arch>\n" + b"".join(ar_member(k, v) for k, v in members)


class DebianAuditTests(unittest.TestCase):
    def test_synthetic_package_is_reported_not_trusted(self):
        result = audit_bytes(package())
        self.assertEqual(result["version"], "2.1.1")
        self.assertEqual(result["installed_appinst_path"], "usr/bin/appinst")
        self.assertFalse(result["official_origin_verified"])
        self.assertFalse(result["eligible_for_privileged_installation"])
        self.assertFalse(result["matches_observed_mirror_sha256"])

    def test_postinst_script_flagged_not_executed(self):
        result = audit_bytes(package(control_extra=[(
            "./postinst", b"#!/bin/sh\nexit 0\n", "file"
        )]))
        self.assertEqual(result["maintainer_scripts"], ["postinst"])

    def test_legacy_lzma_payload_is_inspected_without_execution(self):
        def legacy_payload(members):
            compressed_gzip_tar = members[2][1]
            raw_tar = gzip.decompress(compressed_gzip_tar)
            members[2] = (
                "data.tar.lzma",
                lzma.compress(raw_tar, format=lzma.FORMAT_ALONE),
            )
            return members

        result = audit_bytes(package(changes=legacy_payload))
        self.assertEqual(result["architecture"], "iphoneos-arm")
        self.assertFalse(result["eligible_for_privileged_installation"])

    def test_truncated_legacy_lzma_is_rejected(self):
        def truncated(members):
            raw_tar = gzip.decompress(members[2][1])
            payload = lzma.compress(raw_tar, format=lzma.FORMAT_ALONE)
            members[2] = ("data.tar.lzma", payload[:-9])
            return members

        with self.assertRaises(PackageRejected):
            audit_bytes(package(changes=truncated))

    def test_wrong_architecture_rejected(self):
        def wrong(members):
            metadata = (
                b"Package: ai.akemi.appinst\nVersion: 2.1.1\n"
                b"Architecture: iphoneos-arm64\nDescription: Fixture\n"
            )
            members[1] = ("control.tar.gz", tar_archive([(
                "control", metadata, "file"
            )]))
            return members
        with self.assertRaises(PackageRejected):
            audit_bytes(package(changes=wrong))

    def test_path_traversal_rejected(self):
        with self.assertRaises(PackageRejected):
            audit_bytes(package(data_extra=[(
                "../../evil", b"bad", "file"
            )]))

    def test_absolute_symlink_rejected(self):
        with self.assertRaises(PackageRejected):
            audit_bytes(package(data_extra=[(
                "usr/bin/other", b"", "link"
            )]))

    def test_setuid_file_rejected(self):
        with self.assertRaises(PackageRejected):
            audit_bytes(package(data_extra=[(
                "usr/bin/helper", b"bad", "setuid"
            )]))

    def test_duplicate_control_rejected(self):
        with self.assertRaises(PackageRejected):
            audit_bytes(package(control_extra=[(
                "./control", b"fake", "file"
            )]))

    def test_non_ar_rejected(self):
        with self.assertRaises(PackageRejected):
            audit_bytes(b"not-a-deb")

    def test_duplicate_ar_member_rejected(self):
        def duplicate(members):
            members.append(("data.tar.gz", b"duplicate"))
            return members
        with self.assertRaises(PackageRejected):
            audit_bytes(package(changes=duplicate))


if __name__ == "__main__":
    unittest.main()
