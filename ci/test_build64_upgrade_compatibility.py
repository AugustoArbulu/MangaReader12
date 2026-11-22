#!/usr/bin/env python3
"""Offline negative and positive cases for the Build64 installed-ID gate."""
from check_build64_upgrade_compatibility import evaluate, INSTALLED_APPLICATION_IDENTIFIER
base = {
    "applicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
    "adHocSignatureVerified": True,
    "bundleID": "com.example.MangaReader12",
    "build": 64,
}
assert evaluate(base)["upgradeIdentityMatch"] is True
for altered in [
    {"applicationIdentifier":"WRQA000001.com.example.MangaReader12"},
    {"applicationIdentifier":"AR5SFJC432.com.example.MangaReader12"},
    {"applicationIdentifier":""},
    {"adHocSignatureVerified":False},
    {"bundleID":"com.example.MangaReader12.ipcprobe"},
    {"build":56},
]:
    params={**base,**altered}
    try:
        assert evaluate(params)["upgradeIdentityMatch"] is False
    except ValueError:
        pass
print("PASS: installed-ID gate rejects mismatched or unverified candidate")
