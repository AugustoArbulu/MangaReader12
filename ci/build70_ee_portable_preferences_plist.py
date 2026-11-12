#!/usr/bin/env python3
"""EE: compare backed-up UserDefaults preferences with an extracted iOS plist.
Read-only on a host computer. Neither input is authenticated as iPad evidence.
"""
import argparse
import base64
import binascii
import json
import math
import os
from pathlib import Path
import plistlib
import sys

from build70_ea_external_copy_audit import AuditRejected, audit_snapshot
from build69_bf_portable_backup_baseline import (
    PortableBaselineRejected, read_build68_portable_baseline, MAX_BACKUP_BYTES,
)
from build69_bc_copied_ipa_recheck import _unique_json_object
from build69_production_release_preflight import _read_external_regular

KEYS = (
    "app.theme", "reader.mode", "reader.pageDirection", "reader.background",
    "reader.showPageNumber", "reader.keepScreenOn", "reader.tapZones",
    "reader.webtoonGap", "reader.doubleTapZoom", "reader.scaleMode",
    "reader.preloadNextChapter", "updates.feed.v1",
    "backgroundUpdates.enabled", "library.pinned.sources.v1",
)
BUNDLE_ID = "com.example.MangaReader12"
MAX_PLIST_BYTES = 4 * 1024 * 1024
MAX_ARRAY = 10000
MAX_DATA = 1024 * 1024

class EERejected(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__(code)

def stop(code):
    raise EERejected(code)

def normalized_export(encoded):
    if not isinstance(encoded, dict) or "kind" not in encoded:
        stop("EE_STOP_INVALID_PREFERENCE_VALUE")
    allowed_fields = ("kind", "stringValue", "integerValue", "doubleValue",
                      "boolValue", "dataBase64", "stringArrayValue")
    if any(key not in allowed_fields for key in encoded):
        stop("EE_STOP_INVALID_PREFERENCE_VALUE")
    kind = encoded["kind"]
    names = {"string":"stringValue", "int":"integerValue",
             "double":"doubleValue", "bool":"boolValue",
             "data":"dataBase64", "stringArray":"stringArrayValue"}
    if kind not in names:
        stop("EE_STOP_UNSUPPORTED_PREFERENCE_KIND")
    name = names[kind]
    if name not in encoded or encoded[name] is None:
        stop("EE_STOP_MISSING_PREFERENCE_VALUE")
    if any(key != name and key != "kind" and value is not None
           for key, value in encoded.items()):
        stop("EE_STOP_AMBIGUOUS_PREFERENCE_VALUE")
    raw = encoded[name]
    if kind == "string":
        if type(raw) is not str:
            stop("EE_STOP_INVALID_PREFERENCE_VALUE")
    elif kind == "int":
        if type(raw) is not int or not -(2**63) <= raw < 2**63:
            stop("EE_STOP_INVALID_PREFERENCE_VALUE")
    elif kind == "double":
        if type(raw) not in (float, int) or not math.isfinite(raw):
            stop("EE_STOP_INVALID_PREFERENCE_VALUE")
        raw = float(raw)
    elif kind == "bool":
        if type(raw) is not bool:
            stop("EE_STOP_INVALID_PREFERENCE_VALUE")
    elif kind == "data":
        if type(raw) is not str or len(raw) > 2 * MAX_DATA:
            stop("EE_STOP_INVALID_PREFERENCE_VALUE")
        try:
            raw = base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError):
            stop("EE_STOP_INVALID_PREFERENCE_VALUE")
        if len(raw) > MAX_DATA:
            stop("EE_STOP_INVALID_PREFERENCE_VALUE")
    elif kind == "stringArray":
        if (type(raw) is not list or len(raw) > MAX_ARRAY
                or any(type(item) is not str or not item
                       or len(item.encode("utf-8")) > 2048 for item in raw)):
            stop("EE_STOP_INVALID_PREFERENCE_VALUE")
    return kind, raw

def compare_preferences(portable: bytes, plist_bytes: bytes):
    try:
        read_build68_portable_baseline(portable)
        data = json.loads(portable.decode("utf-8"),
                          object_pairs_hook=_unique_json_object)
        exported = data["preferences"]
        if type(exported) is not dict or any(k not in KEYS for k in exported):
            stop("EE_STOP_UNKNOWN_EXPORTED_PREFERENCE")
        actual = plistlib.loads(plist_bytes)
        if type(actual) is not dict:
            stop("EE_STOP_INVALID_PLIST")
    except (PortableBaselineRejected, ValueError, UnicodeError, TypeError,
            plistlib.InvalidFileException, KeyError):
        stop("EE_STOP_INVALID_BACKUP_OR_PLIST")
    different = []
    for key in KEYS:
        found_backup = key in exported
        found_plist = key in actual
        if found_backup != found_plist:
            different.append(key)
            continue
        if not found_backup:
            continue
        kind, expected = normalized_export(exported[key])
        recorded = actual[key]
        if kind == "double":
            matched = (type(recorded) is float and math.isfinite(recorded)
                       and recorded == expected)
        elif kind == "stringArray":
            matched = (type(recorded) is list and recorded == expected)
        else:
            matched = type(recorded) is type(expected) and recorded == expected
        if not matched:
            different.append(key)
    return {
        "status": ("EE_EXPORTED_PREFERENCES_EQUAL_NOT_ATTESTED"
                   if not different else "EE_STOP_EXPORTED_PREFERENCES_DIFFER"),
        "preferenceKeysInPortable": len(exported),
        "preferenceKeysOnExternalPlist": sum(k in actual for k in KEYS),
        "differingKnownPreferenceKeys": different,
        "unbackedUpOtherUserDefaultsKeysNotCompared": True,
        "plistsMayBeStaleDueToCFPreferencesCache": True,
        "bothInputsProvenToComeFromSameDevice": False,
        "inputsCapturedAtSameMomentProven": False,
        "physicalUserDefaultsValuesAttested": False,
        "offlineChapterImagesVerified": False,
        "completeDataContainerBackupProven": False,
        "readyToDistributeIPA": False,
        "readyToInstallIPA": False,
        "installationAuthorized": False,
        "restorationAuthorized": False,
        "automaticUpdaterEnabled": False,
    }

def review_external_preferences(snapshot, portable_bytes):
    try:
        audit_snapshot(snapshot)
    except AuditRejected:
        stop("EE_STOP_EXTERNAL_COPY_INVALID")
    prefs = (Path(os.path.abspath(snapshot)) / "Library" / "Preferences"
             / (BUNDLE_ID + ".plist"))
    try:
        data = _read_external_regular(prefs, MAX_PLIST_BYTES)
    except (OSError, ValueError):
        stop("EE_STOP_EXTRACTED_PREFERENCES_UNAVAILABLE")
    return compare_preferences(portable_bytes, data)

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--backup", type=Path, required=True)
    a = ap.parse_args(argv)
    try:
        result = review_external_preferences(
            a.snapshot, _read_external_regular(a.backup, MAX_BACKUP_BYTES))
    except (EERejected, OSError, ValueError) as exc:
        result = {
            "status": exc.code if isinstance(exc, EERejected) else "EE_STOP_BAD_INPUT",
            "installationAuthorized": False,
            "restorationAuthorized": False,
            "readyToDistributeIPA": False,
            "readyToInstallIPA": False,
            "automaticUpdaterEnabled": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0

if __name__ == "__main__":
    sys.exit(main())
