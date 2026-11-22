#!/usr/bin/env python3
"""Read-only Build64 QA release gate.

Prevents shipping a test IPA that iOS will reject when upgrading the
already-installed Sideloadly-signed WebReader. No signing or installation.
"""
import argparse
import json
from pathlib import Path

# Exactly as shown by Filza's installed-app rejection screenshot on iOS12.
INSTALLED_APPLICATION_IDENTIFIER = (
    "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
)

def evaluate(audit):
    actual = audit.get("applicationIdentifier")
    if not isinstance(actual, str):
        raise ValueError("candidate IPA has no verified application identifier")
    if audit.get("adHocSignatureVerified") is not True:
        raise ValueError("candidate IPA signature was not validated")
    if audit.get("bundleID") != "com.example.MangaReader12" or audit.get("build") != 64:
        raise ValueError("wrong IPA bundle or build")
    return {
        "installedApplicationIdentifier": INSTALLED_APPLICATION_IDENTIFIER,
        "candidateApplicationIdentifier": actual,
        "upgradeIdentityMatch": actual == INSTALLED_APPLICATION_IDENTIFIER,
        "reason": (
            "IDENTITY_MATCH_ONLY_NOT_DEVICE_INSTALL_TESTED"
            if actual == INSTALLED_APPLICATION_IDENTIFIER
            else "BLOCKED_UPGRADE_APPLICATION_IDENTIFIER_MISMATCH"
        )
    }

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("audit_json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(json.loads(args.audit_json.read_text("utf-8")))
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(result["reason"])
    if not result["upgradeIdentityMatch"]:
        print("No IPA must be distributed for an in-place update.")
