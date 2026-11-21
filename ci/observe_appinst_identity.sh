#!/bin/sh
# Read-only observation for a user-run NewTerm session. Never invokes appinst.
set -eu
export LC_ALL=C
path=/usr/bin/appinst

if command -v sha256sum >/dev/null 2>&1; then
    digest_line=$(sha256sum "$path")
elif command -v shasum >/dev/null 2>&1; then
    digest_line=$(shasum -a 256 "$path")
else
    printf '%s\n' 'No SHA-256 utility available.' >&2
    exit 1
fi

digest=${digest_line%% *}
case "$digest" in
    ''|*[!0123456789abcdef]*)
        printf '%s\n' 'Invalid SHA-256 utility output.' >&2
        exit 1
        ;;
esac
if [ "${#digest}" -ne 64 ]; then
    printf '%s\n' 'Invalid SHA-256 length.' >&2
    exit 1
fi

owner=$(dpkg-query -S "$path" 2>/dev/null) || owner=UNAVAILABLE
package=$(dpkg-query -W -f='${Status}|${Version}|${Architecture}' ai.akemi.appinst 2>/dev/null) ||
    package=UNAVAILABLE

printf 'APPINST_PATH=%s\nAPPINST_SHA256=%s\n' "$path" "$digest"
printf 'APPINST_DPKG_OWNER=%s\nAPPINST_DPKG_STATUS_VERSION_ARCH=%s\n' "$owner" "$package"
