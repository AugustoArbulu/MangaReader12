#!/usr/bin/env python3
"""DF: adversarial offline Mach-O artifact metadata preflight fixtures.

These are synthetic tool transcripts, not verified device images or executable
provenance. A green result cannot authorize downloading, signing or installing.
"""
from dataclasses import asdict, replace
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from build70_df_ios12_macho_preflight import (
    DFMachORejected, inspect_static_macho,
)

ROOT = Path(__file__).resolve().parent
REQUIRED_SYMBOLS = (
    "_getuid", "_geteuid", "_getgid", "_getegid", "_getpid",
    "_getppid", "_getgroups", "_stat", "_uname", "_printf", "_puts",
    "_putchar", "__NSGetExecutablePath",
)


def transcript():
    return {
        "file_summary": "/runner/tmp/de: Mach-O 64-bit executable arm64\n",
        "header": (
            "/runner/tmp/de:\n"
            "Mach header\n"
            "magic cputype cpusubtype caps filetype ncmds sizeofcmds flags\n"
            "MH_MAGIC_64 ARM64 ALL 0x00 EXECUTE 17 852 NOUNDEFS DYLDLINK TWOLEVEL PIE\n"
        ),
        "loads": (
            "/runner/tmp/de:\n"
            "Load command 0\n"
            "      cmd LC_SEGMENT_64\n"
            "  cmdsize 72\n"
            "Load command 1\n"
            "      cmd LC_BUILD_VERSION\n"
            " platform IOS\n"
            "    minos 12.0\n"
            "      sdk 18.5\n"
        ),
        "dylibs": (
            "/runner/tmp/de:\n"
            "\t/usr/lib/libSystem.B.dylib "
            "(compatibility version 1.0.0, current version 1353.0.0)\n"
        ),
        "undefined": "".join("                 U " + s + "\n" for s in REQUIRED_SYMBOLS),
    }


class DFStaticABIHostTests(unittest.TestCase):
    def check(self, overrides=None):
        d = transcript()
        d.update(overrides or {})
        return inspect_static_macho(**d)

    def assert_unauthorized(self, r):
        for field in (
            "code_signature_validated_on_ios12",
            "app_sandbox_entitlements_validated",
            "actual_ipad_execution_proven",
            "ios12_helper_identity_proven",
            "ipc_peer_authenticated", "editor_trust_provisioned",
            "owner_install_consent_verified", "installation_authorized",
            "installation_performed",
        ):
            self.assertFalse(getattr(r, field), field)

    def test_canonical_ios12_arm64_pie_restricted_dylib_passes_static_only(self):
        r = self.check()
        self.assertEqual(r.target_arch, "arm64")
        self.assertEqual(r.target_platform, "IOS")
        self.assertEqual(r.target_min_ios, "12.0")
        self.assertEqual(r.imported_symbol_count, len(REQUIRED_SYMBOLS))
        self.assertEqual(r.verdict, "HOST_STATIC_ABI_ONLY_NOT_DEVICE_AUTHORIZED")
        self.assertTrue(r.self_identity_cli_compatible_by_static_host_checks)
        self.assert_unauthorized(r)

    def test_numeric_ios_platform_in_load_command_accepted_as_ios(self):
        d = transcript()
        self.assertEqual(self.check({
            "loads": d["loads"].replace("platform IOS", "platform 2"),
        }).target_platform, "IOS")

    def test_legacy_version_min_iphoneos_accepted_if_only_one(self):
        d = transcript()
        loads = d["loads"].replace("LC_BUILD_VERSION", "LC_VERSION_MIN_IPHONEOS").replace(
            " platform IOS\n    minos 12.0\n", "  version 12.0\n"
        )
        self.assertEqual(self.check({"loads": loads}).target_min_ios, "12.0")

    def test_ios_12_0_0_version_allowed(self):
        d = transcript()
        r = self.check({"loads": d["loads"].replace("minos 12.0", "minos 12.0.0")})
        self.assertEqual(r.target_min_ios, "12.0")
        self.assert_unauthorized(r)

    def test_ios_minimum_13_is_rejected(self):
        d = transcript()
        for minos in ("11.0", "12.1", "12.5", "13.0", "17.0", "18.0"):
            with self.subTest(minos=minos), self.assertRaises(DFMachORejected):
                self.check({"loads": d["loads"].replace("minos 12.0", "minos " + minos)})

    def test_macos_and_simulator_platforms_rejected(self):
        d = transcript()
        for value in ("MACOS", "IOS_SIMULATOR", "7", "1", "TVOS", "8"):
            with self.subTest(platform=value), self.assertRaises(DFMachORejected):
                self.check({"loads": d["loads"].replace("platform IOS", "platform " + value)})

    def test_macho_requires_pie_arm64_executable(self):
        d = transcript()
        for field, replacement in (
            ("file_summary", d["file_summary"].replace("arm64", "x86_64")),
            ("file_summary", d["file_summary"].replace("executable", "object")),
            ("header", d["header"].replace(" PIE", "")),
            ("header", d["header"].replace("ARM64", "X86_64")),
            ("header", d["header"].replace(" EXECUTE", " DYLIB")),
        ):
            with self.subTest(replacement=replacement[:40]), self.assertRaises(DFMachORejected):
                self.check({field: replacement})

    def test_duplicate_or_missing_min_os_commands_rejected(self):
        d = transcript()
        for value in (
            d["loads"].replace("LC_BUILD_VERSION", "LC_SEGMENT_64"),
            d["loads"] + d["loads"].split("Load command 1")[1].join(
                ["Load command 2", ""]
            ),
        ):
            with self.assertRaises(DFMachORejected):
                self.check({"loads": value})

    def test_reject_extra_unreviewed_dylib_dependencies(self):
        d = transcript()
        for lib in (
            "@rpath/Injected.dylib",
            "/usr/lib/libobjc.A.dylib",
            "/System/Library/Frameworks/Security.framework/Security",
            "/tmp/liboverride.dylib",
        ):
            with self.subTest(lib=lib), self.assertRaises(DFMachORejected):
                self.check({"dylibs": d["dylibs"] + f"\t{lib} "
                            "(compatibility version 1.0.0, current version 1.0.0)\n"})

    def test_reject_no_dependency_duplicates_and_malformed_line(self):
        d = transcript()
        for value in (
            "/tmp/de:\n",
            d["dylibs"] + d["dylibs"].splitlines()[1] + "\n",
            d["dylibs"].replace("compatibility version ", "version "),
        ):
            with self.assertRaises(DFMachORejected):
                self.check({"dylibs": value})

    def test_reject_install_network_privilege_and_dynamic_loader_symbols(self):
        d = transcript()
        for symbol in ("_posix_spawn", "_socket", "_connect", "_open",
                       "_unlink", "_rename", "_dlopen", "_objc_msgSend",
                       "_system", "_fork", "_execve", "_task_for_pid", "_csops"):
            with self.subTest(symbol=symbol), self.assertRaises(DFMachORejected):
                self.check({"undefined": d["undefined"] + " U " + symbol + "\n"})

    def test_reject_unknown_undefined_symbol_and_duplicate(self):
        d = transcript()
        for value in (
            d["undefined"] + " U _unreviewed\n",
            d["undefined"] + " U _printf\n",
            "",
            "INVALID NM REPORT\n" + d["undefined"],
        ):
            with self.assertRaises(DFMachORejected):
                self.check({"undefined": value})

    def test_missing_required_self_credential_symbols_rejected(self):
        d = transcript()
        for symbol in ("_getuid", "_geteuid", "_getgroups", "_uname",
                       "_stat", "_putchar", "__NSGetExecutablePath"):
            with self.subTest(symbol=symbol), self.assertRaises(DFMachORejected):
                self.check({"undefined": d["undefined"].replace(" U " + symbol + "\n", "")})

    def test_reject_truncated_invalid_and_oversized_tool_logs(self):
        d = transcript()
        for name in d:
            with self.subTest(name=name), self.assertRaises(DFMachORejected):
                self.check({name: ""})
            with self.subTest(oversize=name), self.assertRaises(DFMachORejected):
                self.check({name: "A" * 128001})
            with self.subTest(null=name), self.assertRaises(DFMachORejected):
                self.check({name: d[name] + "\0"})

    def test_success_receipt_never_claims_device_or_installer_authority(self):
        r = self.check()
        self.assert_unauthorized(r)
        self.assertNotIn("AUTHORIZED", asdict(r)["verdict"].split("_")[-1:])

    def test_cli_reads_only_fixture_text_and_does_not_execute_target_binary(self):
        d = transcript()
        with tempfile.TemporaryDirectory(prefix="wr-df-cli-") as tmp:
            paths = []
            for k, v in d.items():
                path = Path(tmp) / (k + ".txt")
                path.write_text(v, encoding="utf-8")
                paths.append(str(path))
            result = subprocess.run(
                [sys.executable, str(ROOT / "build70_df_ios12_macho_preflight.py"), *paths],
                text=True, capture_output=True, timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            observation = json.loads(result.stdout)
            self.assertEqual(observation["target_min_ios"], "12.0")
            self.assertFalse(observation["installation_authorized"])

    def test_no_device_runtime_installer_or_network_in_preflight(self):
        src = (ROOT / "build70_df_ios12_macho_preflight.py").read_text()
        for forbidden in ("subprocess", "os.system(", "os.exec", "socket.",
                          "requests.", "urllib", "appinst(", "WRINST1",
                          "installApplication:", "posix_spawn("):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, src)


if __name__ == "__main__":
    unittest.main()
