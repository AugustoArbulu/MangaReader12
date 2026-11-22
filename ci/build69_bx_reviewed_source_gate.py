#!/usr/bin/env python3
"""Build69 BX: bind a future private QA packager to an owner-reviewed Git commit.

READ-ONLY. This gate does not build, sign, package, distribute, install, prove
binary provenance, authenticate the owner, or authorize a production update.
The operator must independently select the exact reviewed 40-hex commit.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

BRANCH = "feat/chimera-updater-phase1-protocol-audit"


class ReviewedSourceRejected(ValueError):
    pass


def _git(checkout: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(checkout), *args],
            check=True, capture_output=True, text=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReviewedSourceRejected("could not inspect local Git checkout") from exc
    return result.stdout.strip()


def inspect_reviewed_source(checkout: Path, reviewed_commit: str) -> dict:
    if type(reviewed_commit) is not str or not re.fullmatch(
        r"[0-9a-f]{40}", reviewed_commit
    ):
        raise ReviewedSourceRejected("independently supplied full lowercase Git SHA required")
    try:
        root = Path(checkout).resolve(strict=True)
    except OSError as exc:
        raise ReviewedSourceRejected("checkout directory missing") from exc
    if not root.is_dir():
        raise ReviewedSourceRejected("checkout is not a directory")
    top = _git(root, "rev-parse", "--show-toplevel")
    if Path(top).resolve() != root:
        raise ReviewedSourceRejected("must audit the repository root")
    if _git(root, "symbolic-ref", "--quiet", "--short", "HEAD") != BRANCH:
        raise ReviewedSourceRejected("wrong branch or detached HEAD")
    head = _git(root, "rev-parse", "--verify", "HEAD")
    if not re.fullmatch(r"[0-9a-f]{40}", head) or head != reviewed_commit:
        raise ReviewedSourceRejected("checkout HEAD differs from reviewed commit")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ReviewedSourceRejected("checkout has tracked or untracked changes")
    return {
        "status": "REVIEWED_CLEAN_SOURCE_ONLY_NOT_BINARY_PROVENANCE",
        "branch": BRANCH,
        "reviewedCommit": reviewed_commit,
        "checkoutHeadMatchesReview": True,
        "checkoutClean": True,
        "appBuiltFromThisCommitProven": False,
        "adHocSignatureVerified": False,
        "ipaCreated": False,
        "ownerPackagingConsentGrantedByTool": False,
        "productionPublisherAuthenticated": False,
        "distributionAuthorized": False,
        "installationAuthorized": False,
        "installationPerformed": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkout", required=True, type=Path)
    p.add_argument("--reviewed-commit", required=True)
    args = p.parse_args()
    print(json.dumps(inspect_reviewed_source(
        args.checkout, args.reviewed_commit
    ), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
