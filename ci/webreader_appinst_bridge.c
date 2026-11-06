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
#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <signal.h>
#include <spawn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/time.h>
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
#define SOCKET_NAME "wri.sock"
#define INSTALL_HEADER "WRINST1\n"
#define SOCKET_PING "WRPING1\n"
#define SOCKET_PONG "WRPONG1\n"
#define SOCKET_SUCCESS "WRDONE1\n"
#define SOCKET_FAILURE "WRFAIL1\n"
#define MAX_REQUEST_PATH 1024
#define SOCKET_WAIT_MS 60000

#ifndef WEBREADER_PING_ONLY
/* Exclude all installer parsing, verification and process launch code
   from the standalone, physically tested PING-only binary. */
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


#endif /* !WEBREADER_PING_ONLY */

static int send_all(int fd, const char *data, size_t len) {
    size_t sent = 0;
    while (sent < len) {
#if defined(MSG_NOSIGNAL)
        ssize_t n = send(fd, data + sent, len - sent, MSG_NOSIGNAL);
#else
        ssize_t n = send(fd, data + sent, len - sent, 0);
#endif
        if (n <= 0) return 0;
        sent += (size_t)n;
    }
    return 1;
}

static int recv_all(int fd, char *data, size_t len) {
    size_t consumed = 0;
    while (consumed < len) {
        ssize_t n = recv(fd, data + consumed, len - consumed, 0);
        if (n <= 0) return 0;
        consumed += (size_t)n;
    }
    return 1;
}

/* The helper is started manually with an app-owned <container>/WR directory.
   It cannot accept a staged IPA located in a DIFFERENT app container. */
#ifndef WEBREADER_PING_ONLY
static int same_app_container(const char *dir, const char *file) {
    char real_dir[PATH_MAX], real_file[PATH_MAX];
    const char *suffix = "/WR";
    size_t len;
    if (!realpath(dir, real_dir) || !realpath(file, real_file)) return 0;
    len = strlen(real_dir);
    if (len <= 3 || strcmp(real_dir + len - 3, suffix) != 0) return 0;
    real_dir[len - 3] = '\0';
    if (strncmp(real_file, real_dir, strlen(real_dir)) != 0) return 0;
    return strncmp(real_file + strlen(real_dir), PREFIX,
                   sizeof(PREFIX) - 1) == 0;
}

#endif /* !WEBREADER_PING_ONLY */

static int verify_socket_directory(const char *dir, char *path, size_t capacity) {
    int fd;
    struct stat st;
    size_t len;
    char resolved[PATH_MAX];
    if (!dir || dir[0] != '/' || !realpath(dir, resolved)) return 0;
    if (strcmp(dir, resolved) != 0) {
        /* iOS12 commonly reports /var/... while realpath is /private/var/... */
        if (strncmp(dir, "/var/", 5) != 0 ||
            strcmp(dir + 4, resolved + 12) != 0) return 0;
    }
    len = strlen(dir);
    if (len + 1 + strlen(SOCKET_NAME) + 1 > capacity) return 0;
    fd = open(dir, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return 0;
    if (fstat(fd, &st) != 0 || !S_ISDIR(st.st_mode) ||
        st.st_uid != geteuid() || (st.st_mode & 0077) != 0) {
        close(fd);
        return 0;
    }
    close(fd);
    if (len < 4 || strcmp(dir + len - 3, "/WR") != 0) return 0;
    snprintf(path, capacity, "%s/%s", dir, SOCKET_NAME);
    return 1;
}

static int same_mobile_peer(int fd) {
#if defined(__APPLE__)
    uid_t uid;
    gid_t gid;
    return getpeereid(fd, &uid, &gid) == 0 && uid == geteuid();
#else
    (void)fd;
    return 0;  /* Socket mode only implemented on Darwin/iOS12. */
#endif
}

static int socket_request(int connection, const char *directory) {
    char header[8];
#ifdef WEBREADER_PING_ONLY
    (void)directory;
#else
    char two[2], path[MAX_REQUEST_PATH + 1], digest[65];
    char consent[sizeof(CONFIRMATION)];
    unsigned int length;
#endif
    if (!recv_all(connection, header, 8)) return 1;
    if (memcmp(header, SOCKET_PING, 8) == 0) {
        return send_all(connection, SOCKET_PONG, 8) ? 0 : 1;
    }
#ifdef WEBREADER_PING_ONLY
    /* Device QA binary cannot execute installer even if a client sends
       a formally valid INSTALL request. PING is the only allowed opcode. */
    (void)send_all(connection, SOCKET_FAILURE, 8);
    return 1;
#else
    if (memcmp(header, INSTALL_HEADER, 8) != 0 ||
        !recv_all(connection, two, 2)) return 1;
    length = ((unsigned char)two[0] << 8) | (unsigned char)two[1];
    if (length < 70 || length > MAX_REQUEST_PATH) return 1;
    if (!recv_all(connection, path, length) ||
        !recv_all(connection, digest, 64) ||
        !recv_all(connection, consent, sizeof(CONFIRMATION) - 1))
        return 1;
    path[length] = '\0';
    digest[64] = '\0';
    consent[sizeof(CONFIRMATION) - 1] = '\0';
    if (memchr(path, '\0', length) ||
        memcmp(consent, CONFIRMATION, sizeof(CONFIRMATION) - 1) != 0 ||
        !same_app_container(directory, path) || !verified_file(path, digest)) {
        (void)send_all(connection, SOCKET_FAILURE, 8);
        return 1;
    }
    /* Once only. A future background agent needs stronger code-identity
       attestation; this mobile-user socket is not a privileged service. */
    if (invoke_appinst(path) == 0) {
        return send_all(connection, SOCKET_SUCCESS, 8) ? 0 : 1;
    }
    (void)send_all(connection, SOCKET_FAILURE, 8);
    return 1;
#endif
}

static int serve_once(const char *directory) {
    int listener = -1, connection = -1, result = 1, created = 0;
    struct sockaddr_un address;
    struct stat initial, current;
    struct pollfd waiting;
    char path[sizeof(address.sun_path)];
    struct timeval timeout = {180, 0};
    memset(&initial, 0, sizeof(initial));
    if (!verify_socket_directory(directory, path, sizeof(path))) {
        fputs("rejected socket directory\n", stderr);
        return 2;
    }
    /* Do not remove a socket/file belonging to another process. */
    if (lstat(path, &current) == 0 || errno != ENOENT) return 3;
    listener = socket(AF_UNIX, SOCK_STREAM, 0);
    if (listener < 0) return 4;
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
#if defined(__APPLE__)
    address.sun_len = (uint8_t)sizeof(address);
#endif
    memcpy(address.sun_path, path, strlen(path) + 1);
    umask(0077);
    if (bind(listener, (const struct sockaddr *)&address, sizeof(address)) != 0)
        goto finish;
    created = 1;
    if (chmod(path, 0600) != 0 || lstat(path, &initial) != 0 ||
        !S_ISSOCK(initial.st_mode) || initial.st_uid != geteuid() ||
        listen(listener, 1) != 0) goto finish;
    puts("WRAPPINST_READY (one request, non-root, 60s timeout)");
    fflush(stdout);
    waiting.fd = listener;
    waiting.events = POLLIN;
    waiting.revents = 0;
    if (poll(&waiting, 1, SOCKET_WAIT_MS) != 1 ||
        !(waiting.revents & POLLIN)) goto finish;
    connection = accept(listener, NULL, NULL);
    if (connection < 0 || !same_mobile_peer(connection)) goto finish;
#if defined(SO_NOSIGPIPE)
    int enabled = 1;
    (void)setsockopt(connection, SOL_SOCKET, SO_NOSIGPIPE,
                     &enabled, sizeof(enabled));
#endif
    (void)setsockopt(connection, SOL_SOCKET, SO_RCVTIMEO,
                     &timeout, sizeof(timeout));
    (void)setsockopt(connection, SOL_SOCKET, SO_SNDTIMEO,
                     &timeout, sizeof(timeout));
    result = socket_request(connection, directory);
finish:
    if (connection >= 0) close(connection);
    if (listener >= 0) close(listener);
    if (created && initial.st_ino != 0 &&
        lstat(path, &current) == 0 && S_ISSOCK(current.st_mode) &&
        current.st_dev == initial.st_dev && current.st_ino == initial.st_ino)
        (void)unlink(path);
    return result;
}

int main(int argc, char **argv) {
    if (geteuid() == 0) {
        fputs("Refusing root: this mobile-user bridge is nonprivileged\n", stderr);
        return 2;
    }
    if (argc == 2 && strcmp(argv[1], "selftest") == 0) {
#ifdef WEBREADER_PING_ONLY
        puts("WEBREADER_PING_ONLY: no IPA installation supported");
#else
        struct stat installed;
        puts("WEBREADER_APPINST_BRIDGE_PRESENT (non-root, no installation)");
        if (lstat(APPINST_BINARY, &installed) == 0 &&
            S_ISREG(installed.st_mode) && (installed.st_mode & 0111)) {
            puts("APPINST_PATH_PRESENT /usr/bin/appinst (not executed)");
        } else {
            puts("APPINST_PATH_UNAVAILABLE /usr/bin/appinst (not executed)");
        }
#endif
        return 0;
    }
    if (argc == 3 && strcmp(argv[1], "serve-once") == 0) {
        return serve_once(argv[2]);
    }
#ifndef WEBREADER_PING_ONLY
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
#endif
#ifdef WEBREADER_PING_ONLY
    fputs("Usage: selftest | serve-once <app-container/WR> (PING only)\n", stderr);
#else
    fputs("Usage: selftest | serve-once <app-container/WR> | inspect <ipa> <sha256> | "
          "install-confirmed <ipa> <sha256> I-CONFIRM-INSTALL\n", stderr);
#endif
    return 2;
}
