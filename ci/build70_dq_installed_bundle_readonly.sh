#!/bin/sh
# Optional WebReader DQ installed-app BUNDLE observation, READ ONLY.
# Explicit Filza-selected path only; no filesystem scan, root, install,
# file writes, package transfer or networking. ldid -e is NOT validation.

fail() {
    printf '%s\n' 'DQ_STATUS=DENIED_INVALID_OR_UNREADABLE_BUNDLE'
    printf '%s\n' 'INSTALLATION_AUTHORIZED=NO'
    printf '%s\n' 'INSTALLATION_ATTEMPTED=NO'
    exit 2
}
[ "$#" -eq 1 ] || fail
app=$1
case "$app" in
    /*/MangaReader12.app) ;;
    *) fail ;;
esac
parent=${app%/*}
uuid=${parent##*/}
base=${parent%/*}
case "$base" in
    /var/containers/Bundle/Application|\
    /private/var/containers/Bundle/Application|\
    /var/mobile/Containers/Bundle/Application|\
    /private/var/mobile/Containers/Bundle/Application) ;;
    *) fail ;;
esac
case "$uuid" in
    ????????-????-????-????-????????????) ;;
    *) fail ;;
esac
case "$uuid" in *[!0123456789abcdefABCDEF-]*) fail ;; esac
if [ ! -d "$app" ] || [ -L "$app" ] ||
   [ ! -f "$app/Info.plist" ] || [ -L "$app/Info.plist" ] ||
   [ ! -f "$app/MangaReader12" ] || [ -L "$app/MangaReader12" ]; then
    fail
fi

# Discover only existing, non-symlinked tools in fixed known paths.
plutil=
for tool in /usr/bin/plutil /bin/plutil /usr/local/bin/plutil; do
    if [ -x "$tool" ] && [ ! -L "$tool" ]; then plutil=$tool; break; fi
done
ldid=
for tool in /usr/bin/ldid /bin/ldid /usr/local/bin/ldid; do
    if [ -x "$tool" ] && [ ! -L "$tool" ]; then ldid=$tool; break; fi
done
awkbin=
for tool in /usr/bin/awk /bin/awk; do
    if [ -x "$tool" ] && [ ! -L "$tool" ]; then awkbin=$tool; break; fi
done

bundle=UNAVAILABLE
build=UNAVAILABLE
entitlement=UNAVAILABLE
if [ -n "$plutil" ] && [ -n "$awkbin" ]; then
    info=$("$plutil" -p "$app/Info.plist" 2>/dev/null) || info=
    if [ -n "$info" ]; then
        bundle=$(printf '%s\n' "$info" | "$awkbin" '
            $1 == "\"CFBundleIdentifier\"" && $2 == "=>" {
                gsub(/"/, "", $3); print $3; exit
            }')
        build=$(printf '%s\n' "$info" | "$awkbin" '
            $1 == "\"CFBundleVersion\"" && $2 == "=>" {
                gsub(/"/, "", $3); print $3; exit
            }')
    fi
fi
if [ -n "$ldid" ] && [ -n "$awkbin" ]; then
    # Only the selected entitlement is printed, never a full entitlement XML.
    entxml=$("$ldid" -e "$app/MangaReader12" 2>/dev/null) || entxml=
    if [ -n "$entxml" ]; then
        entitlement=$(printf '%s\n' "$entxml" | "$awkbin" '
            /<key>application-identifier<\/key>/ {
                if (getline > 0 && $0 ~ /<string>[^<]*<\/string>/) {
                    sub(/^.*<string>/, "")
                    sub(/<\/string>.*$/, "")
                    print
                }
                exit
            }')
    fi
fi

# Restrict any parsed value before exposing it. Never evaluate input.
safe_string() {
    value=$1
    if [ -z "$value" ] || [ "${#value}" -gt 256 ]; then
        printf '%s' UNAVAILABLE
        return
    fi
    case "$value" in
        *[!0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz._-]*)
            printf '%s' UNAVAILABLE ;;
        *) printf '%s' "$value" ;;
    esac
}
bundle=$(safe_string "$bundle")
build=$(safe_string "$build")
entitlement=$(safe_string "$entitlement")

printf '%s\n' 'WebReader Build70 DQ • Observação local somente leitura'
printf 'BUNDLE_IDENTIFIER_TEXT=%s\n' "$bundle"
printf 'BUNDLE_VERSION_TEXT=%s\n' "$build"
printf 'APPLICATION_IDENTIFIER_ENTITLEMENT_TEXT=%s\n' "$entitlement"
printf '%s\n' 'SOURCE=USER_SELECTED_INSTALLED_APP_BUNDLE_NOT_ATTESTED'
printf '%s\n' 'CODE_SIGNATURE_CRYPTOGRAPHIC_VALIDITY_PROVEN=NO'
printf '%s\n' 'PUBLISHER_IDENTITY_AUTHENTICATED=NO'
printf '%s\n' 'CURRENT_DEVICE_PROVEN_BY_SHELL_TEXT=NO'
printf '%s\n' 'DATA_CONTAINER_RETENTION_PROVEN=NO'
printf '%s\n' 'LIBRARY_AND_OFFLINE_PRESERVATION_PROVEN=NO'
printf '%s\n' 'HELPER_IPC_AUTHENTICATED=NO'
printf '%s\n' 'READY_TO_DISTRIBUTE_IPA=NO'
printf '%s\n' 'INSTALLATION_AUTHORIZED=NO'
printf '%s\n' 'INSTALLATION_ATTEMPTED=NO'
