#!/usr/bin/env python3
"""Read-only Keiyoushi path change report. Never changes source scripts."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen

UPSTREAM = "keiyoushi/extensions-source"
API = "https://api.github.com/repos/" + UPSTREAM
PATH_OK = re.compile(r"^[a-zA-Z0-9._/-]{2,120}$")
SHA_OK = re.compile(r"^[a-f0-9]{40}$")


def read_baseline(filename):
    doc = json.loads(Path(filename).read_text(encoding="utf-8"))
    if doc.get("upstream") != UPSTREAM or doc.get("base_branch") != "main":
        raise ValueError("Invalid upstream repository/branch")
    entries = doc.get("entries")
    if not isinstance(entries, list) or not (1 <= len(entries) <= 25):
        raise ValueError("Expected 1-25 explicit upstream paths")
    seen = set()
    for entry in entries:
        name, path, sha = entry["name"], entry["path"], entry["sha"]
        if not isinstance(name, str) or not name or len(name) > 80:
            raise ValueError("Invalid source name")
        if not PATH_OK.fullmatch(path) or ".." in path or path in seen:
            raise ValueError("Unsafe/duplicate upstream path")
        if not SHA_OK.fullmatch(sha):
            raise ValueError("Invalid pinned upstream SHA")
        seen.add(path)
    return doc


def latest_commit(item, token=None, opener=urlopen):
    query = urlencode({"sha": "main", "path": item["path"], "per_page": 1})
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "MangaReader12-upstream-monitor",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    request = Request(API + "/commits?" + query, headers=headers, method="GET")
    with opener(request, timeout=20) as response:
        data = json.loads(response.read(524288).decode("utf-8"))
    if not isinstance(data, list) or not data:
        raise ValueError("Upstream path has no commits")
    commit = data[0]
    sha = commit.get("sha")
    if not isinstance(sha, str) or not SHA_OK.fullmatch(sha):
        raise ValueError("Invalid upstream commit SHA")
    return {"sha": sha, "date": commit.get("commit", {}).get("committer", {}).get("date")}


def compare(doc, latest):
    rows = []
    for entry in doc["entries"]:
        item = latest.get(entry["path"])
        rows.append({
            "name": entry["name"], "path": entry["path"],
            "baseline_sha": entry["sha"],
            "latest_sha": item["sha"] if item else None,
            "date": item.get("date") if item else None,
            "status": "error" if item is None else (
                "unchanged" if item["sha"] == entry["sha"] else "review"
            ),
        })
    return rows


def markdown(doc, rows, errors, now):
    changed = sum(row["status"] == "review" for row in rows)
    lines = [
        "# Keiyoushi upstream: change report",
        "",
        "- Generated UTC: " + now,
        "- Repository: https://github.com/" + UPSTREAM,
        "- Baseline snapshot: " + doc["snapshot_date"],
        "- Tracked paths: " + str(len(rows)),
        "- Needs review: " + str(changed),
        "- Fetch errors: " + str(len(errors)),
        "",
        "> Read-only report. It does NOT import Kotlin/APKs, publish scripts,",
        "> bypass site protections, or claim iOS12 compatibility.",
        "",
        "| Source / engine path | State | Baseline | Upstream | Changed at |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        sha = row["latest_sha"]
        link = ("[%s](https://github.com/%s/commit/%s)" %
                (sha[:10], UPSTREAM, sha)) if sha else "unavailable"
        lines.append("| %s (%s) | %s | %s | %s | %s |" % (
            row["name"], row["path"], row["status"],
            row["baseline_sha"][:10], link, row["date"] or "unknown"
        ))
    if errors:
        lines += ["", "## Lookup errors"]
        for path in sorted(errors):
            lines.append("- %s: %s" % (path, errors[path]))
    lines += [
        "", "## Human review workflow", "",
        "Inspect changed Kotlin files, identify implications for JS adapters,",
        "port only permitted behavior, update the source version and SHA256,",
        "run offline/iOS12 tests, then review and merge a separate PR.",
        "No changes to installed sources are made by this workflow.", "",
    ]
    return "\n".join(lines)


def run(baseline, md_file, json_file):
    doc = read_baseline(baseline)
    token = os.environ.get("GITHUB_TOKEN")
    current = {}
    errors = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(latest_commit, entry, token): entry["path"]
            for entry in doc["entries"]
        }
        for future in as_completed(futures):
            path = futures[future]
            try:
                current[path] = future.result()
            except Exception as error:
                # No token, request headers, URL query or server response.
                errors[path] = type(error).__name__
    rows = compare(doc, current)
    now = datetime.now(timezone.utc).isoformat()
    Path(md_file).write_text(markdown(doc, rows, errors, now), encoding="utf-8")
    Path(json_file).write_text(json.dumps({
        "timestamp": now, "upstream": UPSTREAM,
        "baseline_date": doc["snapshot_date"],
        "changed_count": sum(row["status"] == "review" for row in rows),
        "error_count": len(errors), "results": rows
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Updated paths:", sum(row["status"] == "review" for row in rows),
          "Errors:", len(errors), "Report:", md_file)
    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", default="ci/keiyoushi-upstream-baseline.json")
    parser.add_argument("--markdown", default="keiyoushi-upstream-report.md")
    parser.add_argument("--json", default="keiyoushi-upstream-report.json")
    opts = parser.parse_args()
    return run(opts.baseline, opts.markdown, opts.json)


if __name__ == "__main__":
    sys.exit(main())
