# WebReader Build 67 — Manual QA checklist (iOS 12.5.8 + Chimera)

**Date:** 2026-11-08 UTC
**Goal:** test a new optional **local IPA import/review** workflow and preserve the owner-approved Build 66 Library.
**Environment:** iPad, iOS 12.5.8, Chimera, app com.example.MangaReader12.

## Reference and safety

Build 66 was approved on-device for Library persistence and offline chapters.
Its approved package is retained in private GitHub Actions run
https://github.com/AugustoArbulu/MangaReader12/actions/runs/42351270670
Artifact WebReader-Build66-Private-ManualQA-Filza-iOS12,
SHA-256 49ce402e6efba0aaad891d811e3b76bb78d02b627b5b8ad4fb2e8563aed51afd.

**Do not delete the existing WebReader application or its Documents.**
Export a fresh WebReader Library backup, transfer the backup outside the
iPad and verify it exists before any manual Build67 upgrade.

A matching bundle/entitlement and ad-hoc signature do NOT prove that a
downgrade is safe if a future build migrates a database. On failure,
stop, preserve data and report the error before trying a rollback.

## Candidate package and verification

The private Build67 Actions QA package is expected to contain:

- WebReader-Build67-iOS12-adhoc.ipa
- WebReader-Build67-iOS12-adhoc.ipa.sha256
- WebReader-Build67-private-rehearsal-audit.json
- WebReader-Build67-private-manual-qa-delivery.json
- This checklist.

Do not use old Build66 hashes for new files; verify SHA-256 against the
Build67 sidecar and delivery/audit JSON from the SAME Actions run,
then recheck after transferring to the iPad when possible.

Expected bundle com.example.MangaReader12; version 67;
minimum iOS 12.0; thin ARM64; stable entitlement application-identifier
AR5SFJC432.com.example.MangaReader12.AR5SFJC432.

## Optional device QA after owner-approved manual installation

1. Open WebReader after updating ON TOP of the installed Build66 through
   Filza. Never choose uninstall/delete user data.
2. Confirm Settings displays Build67, not stale Build56/66.
3. Check Library count, titles, progress, favorites and downloaded chapters.
4. Turn Wi-Fi OFF. Open two previously saved chapters and confirm pages
   display without network or error -1009.
5. With Wi-Fi ON, verify known-good sources and reader navigation.
6. In Settings > Atualizações do WebReader, locate the new section
   **IPA LOCAL (ARQUIVOS OU FILZA)**.
7. For a LATER, newer test package only, choose Importar IPA local,
   enter its actual newer Build number and SHA-256 from GitHub Actions,
   select the IPA via iOS Files picker; verify expected success/failure.
   The user does not need to invent a Build68 IPA to test Build67.
8. Check Copy SHA-256 and Share local IPA (manual only). Delete only
   the local QA staging copy through Descartar cópia local.
9. Verify original Library/offline chapters remain unchanged after import
   and discard.
10. Verify the UI still says **Instalação pelo Chimera bloqueada** and
    cannot trigger appinst or install automatically.

## Expected behavior and limitations

- The local import verifies user-supplied SHA-256 and native ZIP/Info.plist
  structure, but **does not authenticate a publisher**.
- A local hash from an untrusted source is only a byte integrity reference.
- There is no real signed production update channel: production key is nil.
- GitHub Releases may return HTTP 404 for a private repository. Actions QA
  artifacts cannot be fetched anonymously through this app.
- Filza/Files availability depends on providers configured on the iPad.
- The new feature is not a privileged installer and cannot replace the
  requirement for independent helper authorization and user consent.
- Build67 can be considered APPROVED only after the owner actually tests it.

## Short report to return

- Filza update Build66 -> Build67: success / exact failure.
- Installed build shown: ...
- Library and reader: ...
- Offline chapters without Wi-Fi: ...
- Local import UI visible: yes/no.
- Local IPA SHA/ZIP check and Copy/Share/Discard: outcome or not tested.
- Any unexpected loss of data or root/appinst action: ...

**No installation occurs as part of GitHub Actions.**
