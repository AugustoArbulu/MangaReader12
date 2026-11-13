#!/usr/bin/env python3
"""EK: read-only recovery-page prefix consistency on a COPIED data container.

Never writes, repairs, downloads, resumes or accesses the user's iPad.
A contiguous prefix is metadata only; it DOES NOT prove valid image decoding.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys

from build70_ea_external_copy_audit import (
    audit_snapshot, AuditRejected, safe_child, swift_component,
    digest_file, MAX_DATABASE_BYTES,
)
from build70_ed_portable_vs_external_library import copied_database, EDRejected
from build70_ei_all_downloads_inventory import (
    audit_noncompleted_and_orphans, EIRejected,
)
from build70_ej_recovery_plan_metadata import (
    plausible_plan, EJRejected, MAX_PAGES, MAX_PLAN_BYTES, ACTIVE_STATES,
)
from build69_production_release_preflight import (
    _read_external_regular, ProductionPreflightRejected,
)

PAGE = re.compile(r"page-([0-9]{5})\.bin\Z", re.ASCII)
MAX_PAGE_BYTES = 20 * 1024 * 1024  # WebReaderOfflineResumePrefix.maximumPageBytes
MAX_CHAPTER_ENTRIES = 6000
MAX_ROWS = 300_000
FLAGS = (os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) |
         getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))


class EKRejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def stop(code):
    raise EKRejected(code)


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size,
            st.st_nlink, st.st_mtime_ns, st.st_ctime_ns)


def inspect_partial_directory(folder, expected_pages=None):
    """Count page metadata and strictly contiguous resume prefix.

    A safe plan is optional for failed jobs; unknown expected_pages must
    NEVER be represented as confirmed resume eligibility.
    """
    before = folder.lstat()
    if not stat.S_ISDIR(before.st_mode):
        stop("EK_STOP_UNSAFE_CHAPTER_FOLDER")
    fd = None
    try:
        fd = os.open(folder, FLAGS)
        if _identity(os.fstat(fd)) != _identity(before):
            stop("EK_STOP_CHAPTER_DIRECTORY_CHANGED")
        names = []
        with os.scandir(fd) as entries:
            for entry in entries:
                names.append(entry.name)
                if len(names) > MAX_CHAPTER_ENTRIES:
                    stop("EK_STOP_TOO_MANY_CHAPTER_ENTRIES")
        names.sort(key=os.fsencode)
        valid = set()
        bad = unexpected = page_files = out_of_plan = 0
        for name in names:
            if name == "_download-plan.json":
                continue  # EJ checks this separately.
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                stop("EK_STOP_UNSAFE_CHAPTER_ENTRY")
            match = PAGE.fullmatch(name)
            if match is None:
                unexpected += 1
                continue
            page_files += 1
            index = int(match.group(1))
            if not 0 < info.st_size <= MAX_PAGE_BYTES:
                bad += 1
            elif expected_pages is not None and index >= expected_pages:
                out_of_plan += 1
            else:
                valid.add(index)
        prefix = 0
        if expected_pages is not None:
            while prefix < expected_pages and prefix in valid:
                prefix += 1
        if (_identity(os.fstat(fd)) != _identity(before)
                or _identity(folder.lstat()) != _identity(before)):
            stop("EK_STOP_CHAPTER_DIRECTORY_CHANGED")
        # Crucial: a zero prefix with page-00002 present is anomalous,
        # even though native resume would restart at page 0.
        sparse_or_extra = (max(0, page_files - bad - out_of_plan - prefix)
                           if expected_pages is not None else 0)
        return {
            "totalPageFiles": page_files, "validPrefixFilesMetadataOnly": prefix,
            "badSizePageFiles": bad, "outOfPlanPageFiles": out_of_plan,
            "nonPrefixPageFiles": sparse_or_extra,
            "unverifiedPageFilesWithoutPlan": (
                page_files - bad if expected_pages is None else 0
            ),
            "unexpectedLeafFiles": unexpected,
            "planPageLimitKnown": expected_pages is not None,
        }
    except OSError:
        stop("EK_STOP_CHAPTER_DIRECTORY_UNREADABLE")
    finally:
        if fd is not None:
            os.close(fd)


def audit_partial_prefixes(snapshot):
    try:
        inventory = audit_noncompleted_and_orphans(snapshot)
        if inventory["status"] == "EI_STOP_UNREFERENCED_OR_UNCLASSIFIED_DOWNLOAD_FILES":
            stop("EK_STOP_UNACCOUNTED_DOWNLOADS")
        ea = audit_snapshot(snapshot)
        db, path, fingerprint = copied_database(snapshot, ea["sqliteSHA256"])
    except (EIRejected, AuditRejected, EDRejected, OSError, sqlite3.Error, ValueError):
        stop("EK_STOP_EXTERNAL_COPY_INVALID")
    rows = partial_rows = pages = prefix_files = 0
    bad_size = out_of_plan = nonprefix = unexpected = 0
    absent_folders = missing_plans = invalid_plans = 0
    without_planned_count = with_planned_count = 0
    unverified_no_plan = 0
    try:
        root = Path(os.path.abspath(snapshot))
        lib = safe_child(root, "Library", directory=True)
        support = safe_child(lib, "Application Support", directory=True)
        app = safe_child(support, "MangaReader12", directory=True)
        downloads = safe_child(app, "Downloads", directory=True, required=False)
        sql = """
            SELECT d.state, m.source_id, m.source_manga_id, c.source_chapter_id
            FROM downloads d
            LEFT JOIN chapters c ON c.internal_id=d.chapter_id
            LEFT JOIN manga m ON m.internal_id=c.manga_id
            ORDER BY d.internal_id
        """
        for state, source, manga, chapter in db.execute(sql):
            rows += 1
            if rows > MAX_ROWS:
                stop("EK_STOP_TOO_MANY_ROWS")
            if any(type(v) is not str for v in (state, source, manga, chapter)):
                stop("EK_STOP_INVALID_ROW_ID")
            if state == "completed":
                continue
            partial_rows += 1
            folder = downloads
            if folder is not None:
                for raw in (source, manga, chapter):
                    folder = safe_child(folder, swift_component(raw),
                                        directory=True, required=False)
                    if folder is None:
                        break
            if folder is None:
                absent_folders += 1
                continue
            plan = safe_child(folder, "_download-plan.json", required=False)
            expected = None
            if plan is None:
                if state in ACTIVE_STATES:
                    missing_plans += 1
            else:
                try:
                    blob = _read_external_regular(plan, MAX_PLAN_BYTES)
                    expected = plausible_plan(blob, source, manga, chapter)
                except (ProductionPreflightRejected, EJRejected):
                    invalid_plans += 1
            if expected is None:
                without_planned_count += 1
            else:
                with_planned_count += 1
            observation = inspect_partial_directory(folder, expected)
            pages += observation["totalPageFiles"]
            prefix_files += observation["validPrefixFilesMetadataOnly"]
            bad_size += observation["badSizePageFiles"]
            out_of_plan += observation["outOfPlanPageFiles"]
            nonprefix += observation["nonPrefixPageFiles"]
            unexpected += observation["unexpectedLeafFiles"]
            unverified_no_plan += observation["unverifiedPageFilesWithoutPlan"]
        if digest_file(path, MAX_DATABASE_BYTES) != fingerprint:
            stop("EK_STOP_DATABASE_CHANGED")
    except (AuditRejected, sqlite3.Error, OSError, ValueError, UnicodeError):
        stop("EK_STOP_SNAPSHOT_UNREADABLE_OR_CHANGED")
    finally:
        db.close()
    anomalous = (bad_size or out_of_plan or nonprefix or unexpected
                 or invalid_plans or missing_plans or absent_folders)
    if anomalous:
        status = "EK_STOP_PARTIAL_PAGES_OR_PLANS_REQUIRE_REVIEW"
    elif partial_rows:
        status = "EK_STOP_PARTIAL_PREFIX_NEEDS_IOS12_READING"
    else:
        status = "EK_NO_INCOMPLETE_DOWNLOAD_ROWS_NOT_DEVICE_PROOF"
    return {
        "status": status,
        "noncompletedChapterRows": partial_rows,
        "rowsWithPlausiblePlanPageCount": with_planned_count,
        "rowsWithoutValidatedPlanPageCount": without_planned_count,
        "missingNoncompletedFolders": absent_folders,
        "missingPlans": missing_plans,
        "invalidPlans": invalid_plans,
        "noncompletedPageFilesObserved": pages,
        "metadataOnlyContiguousPrefixFiles": prefix_files,
        "zeroOrOversizePageFiles": bad_size,
        "pageFilesBeyondPlan": out_of_plan,
        "nonPrefixPageFiles": nonprefix,
        "unverifiedPageFilesWithoutPlan": unverified_no_plan,
        "unexpectedChapterLeafFiles": unexpected,
        "byteContentsOfPagesVerifiedHere": False,
        "validImageDecodingProven": False,
        "resumeOnIOS12Proven": False,
        "sourceDeviceAttested": False,
        "allUserDataRetainedProven": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--snapshot", type=Path, required=True)
    args = p.parse_args(argv)
    try:
        result = audit_partial_prefixes(args.snapshot)
    except (EKRejected, OSError, ValueError) as exc:
        result = {
            "status": exc.code if isinstance(exc, EKRejected)
                      else "EK_STOP_INVALID_INPUT",
            "readyToDistributeIPA": False,
            "readyToInstallIPA": False,
            "installationAuthorized": False,
            "restorationAuthorized": False,
            "automaticUpdaterEnabled": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 2 if result["status"].startswith("EK_STOP_") else 0


if __name__ == "__main__":
    sys.exit(main())
