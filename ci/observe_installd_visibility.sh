#!/bin/sh
# Preflight for an idle NewTerm session. No installer or tracing is started.
set -eu
export LC_ALL=C

if ! command -v lsof >/dev/null 2>&1; then
    printf '%s\n' 'WR_INSTALLD_VISIBILITY=LSOF_UNAVAILABLE'
    exit 0
fi

# Request only process IDs and command names. Keep the raw output local.
if rows=$(lsof -a -c installd -Fpc 2>/dev/null) &&
    printf '%s\n' "$rows" | grep -qx 'cinstalld'; then
    printf '%s\n' 'WR_INSTALLD_VISIBILITY=PROCESS_LISTED'
else
    printf '%s\n' 'WR_INSTALLD_VISIBILITY=NOT_OBSERVED'
fi
