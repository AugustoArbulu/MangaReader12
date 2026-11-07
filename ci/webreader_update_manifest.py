#!/usr/bin/env python3
"""Offline reference validator for versioned WebReader update manifests v1/v2.

This is HOST-ONLY protocol research, not an iOS installer or an app feature.
Production iOS12 code must implement the same signature/policy checks using
Security.framework with a release public key pinned into the application.
"""
import base64
import binascii
from datetime import datetime
import json
from pathlib import Path
import re
import subprocess
import tempfile
from urllib.parse import urlsplit

APP_BUNDLE_ID = "com.example.MangaReader12"
INSTALLED_APPLICATION_IDENTIFIER = (
    "AR5SFJC432.com.example.MangaReader12.AR5SFJC432"
)
MAX_ENVELOPE_BYTES = 64 * 1024
MAX_PAYLOAD_BYTES = 32 * 1024
MAX_IPA_BYTES = 512 * 1024 * 1024
ALGORITHM = "ecdsa-p256-sha256"
ALLOWED_FIELDS = {
    "schemaVersion", "application", "bundleId", "channel", "build",
    "minimumIOS", "ipaUrl", "ipaSize", "sha256", "releaseNotes", "publishedAt"
}
V2_FIELDS = ALLOWED_FIELDS | {"applicationIdentifier"}

class ManifestRejected(ValueError):
    pass

def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestRejected("duplicate JSON key")
        result[key] = value
    return result

def _json_object(raw, limit):
    if not raw or len(raw) > limit:
        raise ManifestRejected("JSON exceeds size bound")
    try:
        obj = json.loads(raw.decode("utf-8"), object_pairs_hook=_no_duplicate_keys)
    except (UnicodeError, ValueError, TypeError) as error:
        raise ManifestRejected("invalid JSON") from error
    if not isinstance(obj, dict):
        raise ManifestRejected("expected object")
    return obj

def _decode_b64(value, max_bytes):
    if not isinstance(value, str) or len(value) > 4 * (max_bytes + 2) // 3 + 8:
        raise ManifestRejected("invalid base64 field")
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeError, binascii.Error, ValueError) as error:
        raise ManifestRejected("invalid base64 field") from error
    if not raw or len(raw) > max_bytes:
        raise ManifestRejected("decoded field out of bounds")
    return raw

def _version(text):
    if not isinstance(text, str) or not re.fullmatch(r"\d{1,2}\.\d{1,2}(?:\.\d{1,2})?", text):
        raise ManifestRejected("invalid iOS version")
    parts = tuple(int(v) for v in text.split("."))
    return parts + (0,) * (3 - len(parts))

def _validate_payload(obj, installed_build, installed_ios):
    version = obj.get("schemaVersion")
    if type(version) is not int or version not in (1, 2):
        raise ManifestRejected("unsupported payload schema")
    if set(obj) != (ALLOWED_FIELDS if version == 1 else V2_FIELDS):
        raise ManifestRejected("missing or unknown payload field")
    if version == 2 and obj["applicationIdentifier"] != INSTALLED_APPLICATION_IDENTIFIER:
        raise ManifestRejected("wrong installed application-identifier")
    if obj["application"] != "WebReader" or obj["bundleId"] != APP_BUNDLE_ID:
        raise ManifestRejected("wrong application identity")
    if obj["channel"] != "development":
        raise ManifestRejected("unsupported release channel")
    if type(obj["build"]) is not int or not 1 <= obj["build"] <= 2_147_483_647:
        raise ManifestRejected("invalid build")
    if type(installed_build) is not int or obj["build"] <= installed_build:
        raise ManifestRejected("not a newer build")
    if _version(obj["minimumIOS"]) > _version(installed_ios):
        raise ManifestRejected("iOS too old for this build")
    size = obj["ipaSize"]
    if type(size) is not int or not 1 <= size <= MAX_IPA_BYTES:
        raise ManifestRejected("invalid IPA size")
    if not isinstance(obj["sha256"], str) or not re.fullmatch("[0-9a-f]{64}", obj["sha256"]):
        raise ManifestRejected("invalid IPA SHA256")
    notes = obj["releaseNotes"]
    if (not isinstance(notes, list) or len(notes) > 20 or
        any(not isinstance(note, str) or not 1 <= len(note) <= 240 for note in notes)):
        raise ManifestRejected("invalid release notes")
    published = obj["publishedAt"]
    if not isinstance(published, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", published):
        raise ManifestRejected("invalid publishedAt")
    try:
        datetime.strptime(published, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise ManifestRejected("invalid publishedAt") from error
    link = obj["ipaUrl"]
    if not isinstance(link, str) or len(link) > 512:
        raise ManifestRejected("invalid URL")
    parts = urlsplit(link)
    # Initial distribution policy: stable, public GitHub Release assets only.
    # GitHub Actions artifacts are not suitable (authentication + expiry).
    release_name = (
        "WebReader-iOS12-unsigned.ipa" if version == 1 else
        "WebReader-Build" + str(obj["build"]) + "-iOS12-adhoc.ipa"
    )
    expected = ("/AugustoArbulu/MangaReader12/releases/download/"
                + "build" + str(obj["build"]) + "/" + release_name)
    if (parts.scheme != "https" or parts.netloc != "github.com" or
        parts.path != expected or parts.query or parts.fragment):
        raise ManifestRejected("not a permitted stable public Release URL")
    return obj

def validate(envelope_json, pinned_public_key_pem, installed_build=56, installed_ios="12.5.8"):
    """Verify a signed envelope and validate its claims. Never downloads files."""
    envelope = _json_object(envelope_json, MAX_ENVELOPE_BYTES)
    if set(envelope) != {"schemaVersion", "algorithm", "payload", "signature"}:
        raise ManifestRejected("invalid envelope fields")
    envelope_version = envelope["schemaVersion"]
    if type(envelope_version) is not int or envelope_version not in (1, 2):
        raise ManifestRejected("unsupported envelope")
    if envelope["algorithm"] != ALGORITHM:
        raise ManifestRejected("unsupported signature algorithm")
    payload = _decode_b64(envelope["payload"], MAX_PAYLOAD_BYTES)
    signature = _decode_b64(envelope["signature"], 128)
    if not 64 <= len(signature) <= 80:
        raise ManifestRejected("unsupported ECDSA DER signature length")
    if not isinstance(pinned_public_key_pem, bytes) or not 100 <= len(pinned_public_key_pem) <= 4096:
        raise ManifestRejected("invalid pinned key")
    with tempfile.TemporaryDirectory(prefix="webreader-update-verify-") as tmp:
        directory = Path(tmp)
        (directory / "payload.bin").write_bytes(payload)
        (directory / "signature.der").write_bytes(signature)
        (directory / "public.pem").write_bytes(pinned_public_key_pem)
        try:
            result = subprocess.run(
                ["openssl", "dgst", "-sha256", "-verify", str(directory / "public.pem"),
                 "-signature", str(directory / "signature.der"),
                 str(directory / "payload.bin")],
                check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ManifestRejected("signature verifier unavailable") from error
        if result.returncode != 0:
            raise ManifestRejected("manifest signature rejected")
    verified = _validate_payload(
        _json_object(payload, MAX_PAYLOAD_BYTES), installed_build, installed_ios
    )
    # Version is covered by the signature *and* repeated in the wrapper;
    # fail closed rather than interpreting a v1 payload as a v2 release.
    if verified["schemaVersion"] != envelope_version:
        raise ManifestRejected("envelope/payload version mismatch")
    return verified
