/*
 * WebReader personal appinst bridge — standalone CLI for iOS12 Chimera.
 *
 * This is NOT a daemon, not a root helper, and not embedded in the WebReader
 * IPA. It never executes a shell or accepts an executable path from the app.
 *
 * Commands:
 *   selftest
 *   inspect <STAGED_IPA_PATH> <SHA256_LOWERCASE>
 *   install-confirmed <STAGED_IPA_PATH> <SHA256_LOWERCASE> I-CONFIRM-INSTALL
 *
 * install-confirmed is destructive: ONLY after user's explicit consent,
 * signed-off disposable-app QA and backup. No automatic call from the app.
 * Test macros below are compiled only for CI, never into production binary.
 */
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#else
#define _GNU_SOURCE 1
#define _POSIX_C_SOURCE 200809L
#endif
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

extern char **environ;

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif
#ifndef O_CLOEXEC
#define O_CLOEXEC 0
#endif
#ifndef O_NOFOLLOW
#define O_NOFOLLOW 0
#endif

#ifndef WEBREADER_TEST_APPINST
#define APPINST_BINARY "/usr/bin/appinst"
#else
#define APPINST_BINARY WEBREADER_TEST_APPINST
#endif

#define MAX_IPA_BYTES (512ULL * 1024ULL * 1024ULL)
#define PREFIX "/Library/Application Support/WebReaderUpdates/"
#define LEAF_PREFIX "WebReader-build"
#define CONFIRMATION "I-CONFIRM-INSTALL"

static int check_uuid(const char *s) {
    int i;
    if (!s) return 0;
    for (i = 0; i < 36; ++i) {
        const int dash = i == 8 || i == 13 || i == 18 || i == 23;
        if (dash) {
            if (s[i] != '-') return 0;
        } else if (!((s[i] >= '0' && s[i] <= '9') ||
                     (s[i] >= 'a' && s[i] <= 'f') ||
                     (s[i] >= 'A' && s[i] <= 'F'))) return 0;
    }
    /* Parent container UUID is followed by '/', IPA leaf UUID by ".ipa". */
    return s[36] == '\0' || s[36] == '/' || s[36] == '.';
}

static int check_leaf(const char *file) {
    const size_t pre = sizeof(LEAF_PREFIX) - 1;
    size_t i = pre, digits = 0;
    if (strncmp(file, LEAF_PREFIX, pre) != 0) return 0;
    while (file[i] >= '0' && file[i] <= '9') {
        if (digits == 0 && file[i] == '0') return 0;
        if (++digits > 10) return 0;
        ++i;
    }
    if (digits == 0 || file[i++] != '-') return 0;
    if (strlen(file + i) != 40) return 0; /* 36-char UUID + ".ipa" */
    if (!check_uuid(file + i)) return 0;
    return strcmp(file + i + 36, ".ipa") == 0;
}

static int trusted_stage_path(const char *input) {
    const char *start;
    const char *uuid_end;
    const char *tail;
    char resolved[PATH_MAX];
    if (!input || input[0] != '/' || strlen(input) >= PATH_MAX ||
        strstr(input, "/../") || strstr(input, "/./") || strstr(input, "//"))
        return 0;
    if (!realpath(input, resolved)) return 0;
#ifdef WEBREADER_TEST_ROOT
    start = WEBREADER_TEST_ROOT;
    if (strncmp(resolved, start, strlen(start)) != 0 ||
        resolved[strlen(start)] != '/') return 0;
    uuid_end = resolved + strlen(start) + 1;
#else
    start = "/private/var/mobile/Containers/Data/Application/";
    if (strncmp(resolved, start, strlen(start)) != 0) return 0;
    uuid_end = resolved + strlen(start);
#endif
    if (strlen(uuid_end) < 36 || !check_uuid(uuid_end) ||
        uuid_end[36] != '/') return 0;
    tail = uuid_end + 36;
    if (strncmp(tail, PREFIX, sizeof(PREFIX) - 1) != 0) return 0;
    if (!check_leaf(tail + sizeof(PREFIX) - 1)) return 0;
    /* Never accept symlinked path components beyond canonical container path. */
    if (strcmp(input, resolved) != 0) {
#ifndef WEBREADER_TEST_ROOT
        /* /var -> /private/var is a normal iOS alias. */
        if (strncmp(input, "/var/", 5) != 0 ||
            strcmp(input + 4, resolved + 12) != 0) return 0;
#else
        return 0;
#endif
    }
    return 1;
}

static int sha64(const char *value) {
    int i;
    if (!value || strlen(value) != 64) return 0;
    for (i = 0; i < 64; ++i)
        if (!((value[i] >= '0' && value[i] <= '9') ||
              (value[i] >= 'a' && value[i] <= 'f'))) return 0;
    return 1;
}

static int verified_file(const char *path, const char *expected_sha) {
    int fd = -1, ok = 0;
    struct stat before, after, by_name;
    unsigned char magic[4], digest[CC_SHA256_DIGEST_LENGTH], buf[262144];
    CC_SHA256_CTX ctx;
    uint64_t bytes = 0;
    char actual[65];
    ssize_t read_count;
    int i;
    if (!sha64(expected_sha) || !trusted_stage_path(path)) return 0;
    if (lstat(path, &by_name) != 0 || !S_ISREG(by_name.st_mode) ||
        by_name.st_nlink != 1 || by_name.st_uid != geteuid() ||
        (by_name.st_mode & 0022) != 0) return 0;
    fd = open(path, O_RDONLY | O_CLOEXEC | O_NOFOLLOW);
    if (fd < 0 || fstat(fd, &before) != 0 || !S_ISREG(before.st_mode) ||
        before.st_nlink != 1 || before.st_uid != geteuid() ||
        before.st_size < 4 || (uint64_t)before.st_size > MAX_IPA_BYTES ||
        before.st_dev != by_name.st_dev || before.st_ino != by_name.st_ino)
        goto cleanup;
    if (read(fd, magic, 4) != 4 ||
        memcmp(magic, "PK\x03\x04", 4) != 0) goto cleanup;
    if (lseek(fd, 0, SEEK_SET) != 0 || CC_SHA256_Init(&ctx) != 1) goto cleanup;
    while ((read_count = read(fd, buf, sizeof(buf))) > 0) {
        bytes += (uint64_t)read_count;
        if (bytes > MAX_IPA_BYTES || CC_SHA256_Update(&ctx, buf,
             (CC_LONG)read_count) != 1) goto cleanup;
    }
    if (read_count < 0 || CC_SHA256_Final(digest, &ctx) != 1) goto cleanup;
    for (i = 0; i < CC_SHA256_DIGEST_LENGTH; ++i)
        snprintf(actual + i * 2, 3, "%02x", digest[i]);
    actual[64] = '\0';
    if (bytes != (uint64_t)before.st_size ||
        strcmp(actual, expected_sha) != 0 ||
        fstat(fd, &after) != 0 || lstat(path, &by_name) != 0 ||
        before.st_dev != after.st_dev || before.st_ino != after.st_ino ||
        before.st_size != after.st_size ||
        before.st_mtime != after.st_mtime || before.st_ctime != after.st_ctime ||
        before.st_dev != by_name.st_dev || before.st_ino != by_name.st_ino)
        goto cleanup;
    ok = 1;
cleanup:
    if (fd >= 0) close(fd);
    return ok;
}

static int invoke_appinst(const char *path) {
    struct stat tool;
    pid_t child = -1;
    int result, status = 0, i;
    struct timespec delay = {0, 200 * 1000 * 1000};
    char * const args[] = {(char *)APPINST_BINARY, (char *)path, NULL};
    if (lstat(APPINST_BINARY, &tool) != 0 ||
        !S_ISREG(tool.st_mode) || (tool.st_mode & 0111) == 0) {
        fputs("appinst binary unavailable or not executable\n", stderr);
        return 6;
    }
    /* Never invoke /bin/sh, interpolate input, or trust the app's PATH. */
    result = posix_spawn(&child, APPINST_BINARY, NULL, NULL, args, environ);
    if (result != 0 || child <= 0) {
        fputs("could not launch fixed appinst binary\n", stderr);
        return 7;
    }
    for (i = 0; i < 900; ++i) { /* 3 minutes, then stop waiting */
        pid_t waited = waitpid(child, &status, WNOHANG);
        if (waited == child) {
            if (WIFEXITED(status) && WEXITSTATUS(status) == 0) {
                puts("APPINST_COMPLETED: tool reported success; confirm app version in iOS");
                return 0;
            }
            fprintf(stderr, "appinst failed (exit status %d)\n",
                    WIFEXITED(status) ? WEXITSTATUS(status) : -1);
            return 8;
        }
        if (waited < 0) return 8;
        nanosleep(&delay, NULL);
    }
    /* Avoid leaving an uncontrolled installer running indefinitely. */
    kill(child, SIGTERM);
    (void)waitpid(child, &status, 0);
    fputs("appinst exceeded the maximum wait\n", stderr);
    return 9;
}

int main(int argc, char **argv) {
    if (geteuid() == 0) {
        fputs("Refusing root: this mobile-user bridge is nonprivileged\n", stderr);
        return 2;
    }
    if (argc == 2 && strcmp(argv[1], "selftest") == 0) {
        puts("WEBREADER_APPINST_BRIDGE_PRESENT (non-root, no installation)");
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "inspect") == 0 && argc == 4) {
        if (!verified_file(argv[2], argv[3])) {
            fputs("IPA path or SHA-256 rejected; no installation\n", stderr);
            return 3;
        }
        puts("IPA_BYTES_MATCH_SHA256 (not a ZIP/app signature attestation)");
        return 0;
    }
    if (argc >= 2 && strcmp(argv[1], "install-confirmed") == 0 &&
        argc == 5 && strcmp(argv[4], CONFIRMATION) == 0) {
        if (!verified_file(argv[2], argv[3])) {
            fputs("IPA path or SHA-256 rejected; no installation\n", stderr);
            return 3;
        }
        /* No installer request originates from this app, yet. This CLI is
         * for a disposable-app validation after explicit user approval. */
        return invoke_appinst(argv[2]);
    }
    fputs("Usage: selftest | inspect <ipa> <sha256> | "
          "install-confirmed <ipa> <sha256> I-CONFIRM-INSTALL\n", stderr);
    return 2;
}
