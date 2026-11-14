#!/usr/bin/env python3
"""CV: strict parser of *untrusted* read-only iOS12 method lookup transcript.

A runtime class/method observation is not publisher authenticity, process
identity, caller entitlement, file ownership, installation capability or
user consent. The parser NEVER produces install authority; it has no IO.
"""
from dataclasses import dataclass
import re

_KEYS = (
    "CV_CLASS", "CV_SELECTOR", "CV_ARG_COUNT", "CV_BOOL_RETURN",
    "CV_CALL", "CV_AUTHORIZATION", "CV_INSTALLATION"
)


class CVProbeRejected(ValueError):
    pass


@dataclass(frozen=True)
class CVMethodObservation:
    class_present: bool
    selector_present: bool
    argument_count: int
    bool_return_compatible: bool
    signature_looks_plausible_only: bool
    # Never promote observed methods into authority.
    binary_is_real_ios12_runtime: bool = False
    process_entitled_to_use_selector: bool = False
    appinst_secondary_copy_avoided: bool = False
    exact_verified_ipa_consumed_by_installer: bool = False
    owner_editor_trust_verified: bool = False
    owner_install_consent_verified: bool = False
    installation_authorized: bool = False
    installation_performed: bool = False


def parse_readonly_probe(raw: bytes) -> CVMethodObservation:
    if type(raw) is not bytes or not 1 <= len(raw) <= 320:
        raise CVProbeRejected("invalid report size or type")
    try:
        lines = raw.decode("ascii", errors="strict").splitlines(keepends=True)
    except UnicodeDecodeError as exc:
        raise CVProbeRejected("non-ascii report") from exc
    if len(lines) != len(_KEYS) or not all(line.endswith("\n") for line in lines):
        raise CVProbeRejected("missing or extra report lines")
    fields = {}
    for key, line in zip(_KEYS, lines):
        if not line.startswith(key + "="):
            raise CVProbeRejected("unexpected field ordering")
        value = line[len(key)+1:-1]
        if not value or "\r" in value or "=" in value:
            raise CVProbeRejected("malformed field value")
        fields[key] = value
    if (fields["CV_CLASS"] not in ("PRESENT", "ABSENT")
        or fields["CV_SELECTOR"] not in ("PRESENT", "ABSENT")
        or fields["CV_BOOL_RETURN"] not in ("YES", "NO", "UNKNOWN")
        or re.fullmatch(r"(0|[1-9][0-9]?)", fields["CV_ARG_COUNT"]) is None
        or fields["CV_CALL"] != "NOT_ATTEMPTED"
        or fields["CV_AUTHORIZATION"] != "DENIED"
        or fields["CV_INSTALLATION"] != "NOT_ATTEMPTED"):
        raise CVProbeRejected("invalid readonly probe contract")
    cls = fields["CV_CLASS"] == "PRESENT"
    selector = fields["CV_SELECTOR"] == "PRESENT"
    argc = int(fields["CV_ARG_COUNT"])
    boolret = fields["CV_BOOL_RETURN"] == "YES"
    if selector and not cls:
        raise CVProbeRejected("method without class impossible")
    if not selector and (argc != 0 or fields["CV_BOOL_RETURN"] != "UNKNOWN"):
        raise CVProbeRejected("absent selector must not have signature")
    if selector and fields["CV_BOOL_RETURN"] == "UNKNOWN":
        raise CVProbeRejected("present selector missing return info")
    return CVMethodObservation(cls, selector, argc, boolret,
                               cls and selector and argc == 5 and boolret)


def main() -> int:
    # This example is synthetic and does NOT use a device or declare runtime support.
    synthetic = (
        b"CV_CLASS=PRESENT\nCV_SELECTOR=PRESENT\nCV_ARG_COUNT=5\n"
        b"CV_BOOL_RETURN=YES\nCV_CALL=NOT_ATTEMPTED\n"
        b"CV_AUTHORIZATION=DENIED\nCV_INSTALLATION=NOT_ATTEMPTED\n"
    )
    finding = parse_readonly_probe(synthetic)
    assert finding.signature_looks_plausible_only
    assert not finding.binary_is_real_ios12_runtime
    assert not finding.installation_authorized
    print("PASS CV synthetic parser: hypothetical 5-argument method, NO iOS runtime proof")
    print("NO file, NO installation, NO installer permission")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
