/*
 * WebReader Build60 — throwaway-app-only installer validation (Chimera iOS12).
 *
 * This executable is NOT an updater daemon and never receives an IPA path,
 * a digest, a bundle ID, an executable name, or an install request over IPC.
 * The exact two synthetic app IPAs are pinned by SHA-256 during GitHub Actions
 * compilation, after their actual contents have been audited.
 *
 * There is NO code path here that can install WebReader itself. Only use
 * after personal confirmation on the iPad and a backup of unrelated apps.
 */
#define _DARWIN_C_SOURCE 1
#include <CommonCrypto/CommonDigest.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <signal.h>
#include <spawn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <time.h>
#include <unistd.h>

#ifndef WRD_SHA_V1
#error "Build60 requires SHA-256 of the audited disposable v1 IPA"
#endif
#ifndef WRD_SHA_V2
#error "Build60 requires SHA-256 of the audited disposable v2 IPA"
#endif
#ifndef PATH_MAX
#define PATH_MAX 4096
#endif
#ifndef O_NOFOLLOW
#define O_NOFOLLOW 0
#endif
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef WRD_TEST_ROOT
#define WRD_BASE "/var/mobile/Documents"
#define WRD_APPINST "/usr/bin/appinst"
#else
#define WRD_BASE WRD_TEST_ROOT
#define WRD_APPINST WRD_TEST_APPINST
#endif
#define WRD_V1 "WebReader-Appinst-Disposable-v1-iOS12-unsigned.ipa"
#define WRD_V2 "WebReader-Appinst-Disposable-v2-iOS12-unsigned.ipa"
#define WRD_CONSENT "I-CONFIRM-DISPOSABLE-ONLY"
#define WRD_MAX_SIZE (2U * 1024U * 1024U)

extern char **environ;

static int mobile_user(void) {
    if (geteuid() == 0) return 0;
#ifndef WRD_TEST_ROOT
    return geteuid() == 501;
#else
    return 1;
#endif
}

static int is_lower_sha(const char *s) {
    size_t i;
    if (!s || strlen(s) != 64) return 0;
    for (i = 0; i != 64; ++i)
        if (!((s[i] >= '0' && s[i] <= '9') ||
              (s[i] >= 'a' && s[i] <= 'f'))) return 0;
    return 1;
}

static int disposable_path(char path[PATH_MAX], int version) {
    char resolved_base[PATH_MAX], resolved_file[PATH_MAX];
    struct stat base_stat;
    const char *name = version == 1 ? WRD_V1 : WRD_V2;
    int n;
    if (!realpath(WRD_BASE, resolved_base)) return 0;
    if (lstat(resolved_base, &base_stat) ||
        !S_ISDIR(base_stat.st_mode) ||
        base_stat.st_uid != geteuid() ||
        (base_stat.st_mode & 0022) != 0) return 0;
    n = snprintf(path, PATH_MAX, "%s/%s", resolved_base, name);
    if (n < 0 || n >= PATH_MAX) return 0;
    if (!realpath(path, resolved_file) || strcmp(path, resolved_file) != 0)
        return 0;
    return 1;
}

static int verify_disposable(int version, char path[PATH_MAX]) {
    const char *expected = version == 1 ? WRD_SHA_V1 : WRD_SHA_V2;
    struct stat name_stat, before, after, final_name;
    char digest_hex[65];
    unsigned char digest[CC_SHA256_DIGEST_LENGTH];
    unsigned char buffer[16384], prefix[4];
    uint64_t total = 0;
    CC_SHA256_CTX ctx;
    int fd = -1, ok = 0, i;
    ssize_t n;
    if (!is_lower_sha(expected) || !disposable_path(path, version))
        return 0;
    if (lstat(path, &name_stat) ||
        !S_ISREG(name_stat.st_mode) || name_stat.st_nlink != 1 ||
        name_stat.st_uid != geteuid() ||
        (name_stat.st_mode & 0022) != 0) return 0;
    fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0 || fstat(fd, &before) ||
        !S_ISREG(before.st_mode) || before.st_nlink != 1 ||
        before.st_uid != geteuid() ||
        before.st_size < 4 ||
        (uint64_t)before.st_size > WRD_MAX_SIZE ||
        before.st_dev != name_stat.st_dev ||
        before.st_ino != name_stat.st_ino) goto done;
    if (read(fd, prefix, 4) != 4 ||
        memcmp(prefix, "PK\x03\x04", 4) != 0 ||
        lseek(fd, 0, SEEK_SET) != 0 ||
        CC_SHA256_Init(&ctx) != 1) goto done;
    while ((n = read(fd, buffer, sizeof(buffer))) > 0) {
        total += (uint64_t)n;
        if (total > WRD_MAX_SIZE ||
            CC_SHA256_Update(&ctx, buffer, (CC_LONG)n) != 1) goto done;
    }
    if (n < 0 || CC_SHA256_Final(digest, &ctx) != 1) goto done;
    for (i = 0; i < CC_SHA256_DIGEST_LENGTH; ++i)
        (void)snprintf(digest_hex + 2 * i, 3, "%02x", digest[i]);
    digest_hex[64] = '\0';
    if (strcmp(digest_hex, expected) != 0 ||
        total != (uint64_t)before.st_size ||
        fstat(fd, &after) || lstat(path, &final_name) ||
        before.st_dev != after.st_dev ||
        before.st_ino != after.st_ino ||
        before.st_size != after.st_size ||
        before.st_mtime != after.st_mtime ||
        before.st_ctime != after.st_ctime ||
        before.st_dev != final_name.st_dev ||
        before.st_ino != final_name.st_ino ||
        before.st_size != final_name.st_size) goto done;
    ok = 1;
done:
    if (fd >= 0) (void)close(fd);
    return ok;
}

static int install_disposable(const char *path) {
    struct stat executable;
    pid_t child = -1;
    char *const args[] = {(char *)WRD_APPINST, (char *)path, NULL};
    struct timespec pause_time = {0, 200000000};
    int rc, status = 0, i;
    if (lstat(WRD_APPINST, &executable) ||
        !S_ISREG(executable.st_mode) ||
        !(executable.st_mode & 0111)) return 7;
    /* Literal executable path and exactly one package argument; no shell. */
    rc = posix_spawn(&child, WRD_APPINST, NULL, NULL, args, environ);
    if (rc != 0 || child <= 0) return 8;
    for (i = 0; i < 900; ++i) {
        pid_t ended = waitpid(child, &status, WNOHANG);
        if (ended == child) {
            if (WIFEXITED(status) && WEXITSTATUS(status) == 0)
                return 0;
            return 9;
        }
        if (ended < 0) return 9;
        (void)nanosleep(&pause_time, NULL);
    }
    (void)kill(child, SIGTERM);
    (void)waitpid(child, &status, 0);
    return 10;
}

/* One interactive field session. The two IPA hashes are fixed at build time.
 * The user must open v1 to create its NSUserDefaults marker before v2.
 * No WebReader installation is possible in either stage. */
static int run_disposable_batch(void) {
    char first[PATH_MAX] = {0}, second[PATH_MAX] = {0};
    char acknowledgement[16] = {0};
    int rc;
#ifndef WRD_TEST_ROOT
    if (!isatty(STDIN_FILENO)) {
        fputs("WRDISPOSABLE_DENIED: interactive NewTerm required\n", stderr);
        return 2;
    }
#endif
    if (!verify_disposable(1, first) || !verify_disposable(2, second)) {
        fputs("WRDISPOSABLE_DENIED: batch SHA/ownership/IPA preflight failed\n",
              stderr);
        return 3;
    }
    puts("WRDISPOSABLE_BOTH_VERIFIED: only throwaway app; no WebReader");
    fflush(stdout);
    if (!verify_disposable(1, first)) return 4;
    rc = install_disposable(first);
    if (rc != 0) {
        fprintf(stderr, "WRDISPOSABLE_INSTALL_FAILED: v1 code=%d\n", rc);
        return rc;
    }
    puts("WRDISPOSABLE_V1_APPINST_SUCCESS");
    puts("Abra WR Appinst Test v1 UMA VEZ para criar o registro local.");
    puts("Retorne ao NewTerm, digite NEXT e Enter para atualizar somente esse app.");
    fflush(stdout);
    if (!fgets(acknowledgement, sizeof(acknowledgement), stdin) ||
        (strcmp(acknowledgement, "NEXT\n") != 0 &&
         strcmp(acknowledgement, "NEXT\r\n") != 0)) {
        fputs("WRDISPOSABLE_STOPPED: v2 not installed\n", stderr);
        return 5;
    }
    if (!verify_disposable(2, second)) {
        fputs("WRDISPOSABLE_DENIED: v2 SHA changed\n", stderr);
        return 3;
    }
    rc = install_disposable(second);
    if (rc != 0) {
        fprintf(stderr, "WRDISPOSABLE_INSTALL_FAILED: v2 code=%d\n", rc);
        return rc;
    }
    puts("WRDISPOSABLE_V2_APPINST_SUCCESS");
    puts("Agora abra WR Appinst Test v2 e confira Persistencia dos dados: SIM.");
    return 0;
}

int main(int argc, char **argv) {
    int version = 0, perform = 0, result;
    char path[PATH_MAX] = {0};
    if (!mobile_user()) {
        fputs("WRDISPOSABLE_DENIED: user mobile only; root not allowed\n", stderr);
        return 2;
    }
    if (argc == 2 && strcmp(argv[1], "selftest") == 0) {
        puts("WRDISPOSABLE_READY: only fixed disposable v1/v2; never WebReader");
        puts("NO_IPA_INSTALLED");
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "run-disposable-qa") == 0 &&
        strcmp(argv[2], WRD_CONSENT) == 0) {
        return run_disposable_batch();
    }
    if (argc == 2 && strcmp(argv[1], "inspect-v1") == 0) version = 1;
    if (argc == 2 && strcmp(argv[1], "inspect-v2") == 0) version = 2;
    if (argc == 3 && strcmp(argv[2], WRD_CONSENT) == 0) {
        if (strcmp(argv[1], "install-v1") == 0) version = 1;
        if (strcmp(argv[1], "install-v2") == 0) version = 2;
        if (version) perform = 1;
    }
    if (version == 0) {
        fputs("Usage: selftest | inspect-v1 | inspect-v2 | run-disposable-qa I-CONFIRM-DISPOSABLE-ONLY | install-v1/install-v2 I-CONFIRM-DISPOSABLE-ONLY\n", stderr);
        return 2;
    }
    if (!verify_disposable(version, path)) {
        fputs("WRDISPOSABLE_DENIED: filename, ownership, IPA bytes or pinned SHA-256 mismatch\n", stderr);
        return 3;
    }
    if (!perform) {
        printf("WRDISPOSABLE_V%d_VERIFIED: pinned SHA-256, no install\n", version);
        return 0;
    }
    /* A second verification reduces time between integrity validation and
       appinst opening the fixed path; it does not eliminate TOCTOU on a
       compromised, same-UID jailbroken environment. */
    if (!verify_disposable(version, path)) return 4;
    result = install_disposable(path);
    if (result != 0) {
        fprintf(stderr, "WRDISPOSABLE_INSTALL_FAILED: version=%d code=%d\n",
                version, result);
        return result;
    }
    printf("WRDISPOSABLE_V%d_APPINST_SUCCESS: verify installed app on device\n",
           version);
    return 0;
}
