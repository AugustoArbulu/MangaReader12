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
#ifdef WEBREADER_PING_ONLY
#include <CommonCrypto/CommonHMAC.h>
#endif
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/un.h>
#ifdef WEBREADER_PING_ONLY
#include <arpa/inet.h>
#include <netinet/in.h>
#endif
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
/* PING-only diagnostic TCP on IPv4 loopback. NOT an installation transport. */
#define PING_LOOPBACK_PORT 38971
/* Separate non-installing, one-use pairing laboratory (NOT an updater). */
#define PAIR_LOOPBACK_PORT 38972
#define PAIR_WAIT_MS 120000
#define INSTALL_HEADER "WRINST1\n"
#define SOCKET_PING "WRPING1\n"
#define SOCKET_PONG "WRPONG1\n"
#define SOCKET_SUCCESS "WRDONE1\n"
#define SOCKET_FAILURE "WRFAIL1\n"
#define MAX_REQUEST_PATH 1024
#ifndef SOCKET_WAIT_MS
#define SOCKET_WAIT_MS 60000
#endif
/* PING-only physical QA diagnostics are printed only by the
 * non-installer build. Production bridge does not emit diagnostic logs. */
#ifdef WEBREADER_PING_ONLY
#define WR_DIAG(...) do { fprintf(stderr, "WRDIAG: "); \
    fprintf(stderr, __VA_ARGS__); fprintf(stderr, "\n"); } while (0)
#else
#define WR_DIAG(...) ((void)0)
#endif

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
    if (!recv_all(connection, header, 8)) {
        WR_DIAG("connected, but request header read failed (errno=%d)", errno);
        return 1;
    }
    if (memcmp(header, SOCKET_PING, 8) == 0) {
        int ok = send_all(connection, SOCKET_PONG, 8);
        WR_DIAG("PING matched; PONG send %s (errno=%d)",
                ok ? "OK" : "FAILED", ok ? 0 : errno);
        return ok ? 0 : 1;
    }
#ifdef WEBREADER_PING_ONLY
    /* Device QA binary cannot execute installer even if a client sends
       a formally valid INSTALL request. PING is the only allowed opcode. */
    WR_DIAG("request header not PING; refusing with WRFAIL1");
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
    int polled = poll(&waiting, 1, SOCKET_WAIT_MS);
    if (polled != 1 || !(waiting.revents & POLLIN)) {
        WR_DIAG("NO_CONNECTION: poll=%d revents=%d errno=%d",
                polled, waiting.revents, polled < 0 ? errno : 0);
        goto finish;
    }
    connection = accept(listener, NULL, NULL);
    if (connection < 0) {
        WR_DIAG("ACCEPT_FAILED: errno=%d", errno);
        goto finish;
    }
    WR_DIAG("ACCEPTED_CONNECTION");
    if (!same_mobile_peer(connection)) {
        WR_DIAG("PEER_REJECTED: getpeereid/UID mismatch errno=%d", errno);
        goto finish;
    }
    WR_DIAG("PEER_ACCEPTED: same UID");
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
    WR_DIAG("REQUEST_FINISHED: result=%d", result);
finish:
    if (connection >= 0) close(connection);
    if (listener >= 0) close(listener);
    if (created && initial.st_ino != 0 &&
        lstat(path, &current) == 0 && S_ISSOCK(current.st_mode) &&
        current.st_dev == initial.st_dev && current.st_ino == initial.st_ino)
        (void)unlink(path);
    return result;
}

#ifdef WEBREADER_PING_ONLY
/*
 * iOS12 can reject lstat of a UNIX socket created by a non-container process
 * even when its parent folder belongs to the sandboxed application.
 * This separate, deliberately unprivileged, PING-only test listens on
 * 127.0.0.1:38971, never a device LAN address, for one request.
 *
 * Any local process can reach loopback: this is NOT authentication. The
 * protocol does not contain any install operation, path or file access.
 */
static int serve_loopback_once(void) {
    int listener = -1, client = -1, result = 1, polled, reuse = 1;
    struct sockaddr_in address, remote;
    socklen_t remote_length = (socklen_t)sizeof(remote);
    struct pollfd waiting;
    struct timeval timeout = {3, 0};
    listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) {
        WR_DIAG("LOOPBACK_SOCKET_FAILED errno=%d", errno);
        return 2;
    }
    (void)setsockopt(listener, SOL_SOCKET, SO_REUSEADDR,
                     &reuse, sizeof(reuse));
    memset(&address, 0, sizeof(address));
#if defined(__APPLE__)
    address.sin_len = (uint8_t)sizeof(address);
#endif
    address.sin_family = AF_INET;
    address.sin_port = htons(PING_LOOPBACK_PORT);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    if (bind(listener, (const struct sockaddr *)&address,
             (socklen_t)sizeof(address)) != 0 ||
        listen(listener, 1) != 0) {
        WR_DIAG("LOOPBACK_BIND_OR_LISTEN_FAILED errno=%d", errno);
        goto finish;
    }
    puts("WRLOOPBACK_READY (127.0.0.1:38971, PING ONLY, 60s timeout)");
    fflush(stdout);
    waiting.fd = listener;
    waiting.events = POLLIN;
    waiting.revents = 0;
    polled = poll(&waiting, 1, SOCKET_WAIT_MS);
    if (polled != 1 || !(waiting.revents & POLLIN)) {
        WR_DIAG("LOOPBACK_NO_CONNECTION poll=%d revents=%d errno=%d",
                polled, waiting.revents, polled < 0 ? errno : 0);
        goto finish;
    }
    memset(&remote, 0, sizeof(remote));
    client = accept(listener, (struct sockaddr *)&remote, &remote_length);
    if (client < 0) {
        WR_DIAG("LOOPBACK_ACCEPT_FAILED errno=%d", errno);
        goto finish;
    }
    if (remote.sin_family != AF_INET ||
        ntohl(remote.sin_addr.s_addr) != INADDR_LOOPBACK) {
        WR_DIAG("LOOPBACK_REJECTED_NONLOCAL_PEER");
        goto finish;
    }
    WR_DIAG("LOOPBACK_ACCEPTED_127_0_0_1");
#if defined(SO_NOSIGPIPE)
    int no_sigpipe = 1;
    (void)setsockopt(client, SOL_SOCKET, SO_NOSIGPIPE,
                     &no_sigpipe, sizeof(no_sigpipe));
#endif
    (void)setsockopt(client, SOL_SOCKET, SO_RCVTIMEO,
                     &timeout, sizeof(timeout));
    (void)setsockopt(client, SOL_SOCKET, SO_SNDTIMEO,
                     &timeout, sizeof(timeout));
    result = socket_request(client, NULL);
    WR_DIAG("LOOPBACK_REQUEST_FINISHED result=%d", result);
finish:
    if (client >= 0) close(client);
    if (listener >= 0) close(listener);
    return result;
}
#endif

#ifdef WEBREADER_PING_ONLY
/*
 * Ephemeral proof-of-possession experiment for iOS12 loopback IPC.
 *
 * Security boundary: This merely proves the remote process knew a
 * terminal-displayed one-shot random code. It does not authenticate an app
 * signature or process identity, so it MUST NEVER install an IPA, execute
 * appinst, accept file paths or be promoted to a privileged listener.
 *
 * Fixed framing (all tokens exactly 8 bytes):
 * client: WRPAIR1\n
 * server: WRCHAL1\n + random 16-byte challenge
 * client: WRAUTH1\n + HMAC-SHA256(code, "WR-PAIR-CLIENT-V1" || challenge)
 * server: WROKAY1\n + HMAC-SHA256(code, "WR-PAIR-SERVER-V1" || challenge)
 *     OR: WRDENY1\n
 *
 * One connection / one attempted authentication, then exit. Separate port
 * 38972. Code is 16 random uppercase hexadecimal chars (64 random bits),
 * printed only on the local NewTerm screen, never in CI or device reports.
 */
static void pair_zero(void *pointer, size_t size) {
    volatile unsigned char *p = (volatile unsigned char *)pointer;
    while (size--) *p++ = 0;
}
static int pair_equal(const unsigned char *a, const unsigned char *b,
                      size_t count) {
    unsigned char diff = 0;
    size_t i;
    for (i = 0; i < count; ++i) diff |= (unsigned char)(a[i] ^ b[i]);
    return diff == 0;
}
static void pair_mac(const char code[17], const char *domain,
                     const unsigned char nonce[16],
                     unsigned char output[CC_SHA256_DIGEST_LENGTH]) {
    unsigned char data[64];
    const size_t length = strlen(domain);
    memcpy(data, domain, length);
    memcpy(data + length, nonce, 16);
    CCHmac(kCCHmacAlgSHA256, code, 16, data, length + 16, output);
    pair_zero(data, sizeof(data));
}

static int serve_pair_once(void) {
    int listener = -1, client = -1, result = 1;
    int polled;
    struct sockaddr_in local, remote;
    socklen_t remote_length = (socklen_t)sizeof(remote);
    struct pollfd waiting;
    struct timeval timeout = {3, 0};
    char code[17] = {0};
    unsigned char secret[8] = {0};
    unsigned char nonce[16] = {0};
    unsigned char received_mac[CC_SHA256_DIGEST_LENGTH] = {0};
    unsigned char expected_mac[CC_SHA256_DIGEST_LENGTH] = {0};
    unsigned char server_mac[CC_SHA256_DIGEST_LENGTH] = {0};
    char header[8] = {0};
    char challenge[24] = {0};
    char response[40] = {0};
    size_t i;
    int no_sigpipe = 1;

    listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) {
        WR_DIAG("PAIR_SOCKET_FAILED errno=%d", errno);
        goto finish;
    }
    memset(&local, 0, sizeof(local));
#if defined(__APPLE__)
    local.sin_len = (uint8_t)sizeof(local);
#endif
    local.sin_family = AF_INET;
    local.sin_port = htons(PAIR_LOOPBACK_PORT);
    local.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    /* Deliberately no SO_REUSEPORT or SO_REUSEADDR; do not share port. */
    if (bind(listener, (const struct sockaddr *)&local,
             (socklen_t)sizeof(local)) != 0 || listen(listener, 1) != 0) {
        WR_DIAG("PAIR_BIND_FAILED errno=%d", errno);
        goto finish;
    }

    arc4random_buf(secret, sizeof(secret));
    arc4random_buf(nonce, sizeof(nonce));
    for (i = 0; i < sizeof(secret); ++i)
        (void)snprintf(code + (2 * i), 3, "%02X", secret[i]);
    puts("WRPAIR_READY (127.0.0.1:38972, ONE-USE, 120s)");
    /* Only displayed on the user's terminal, never logged to artifacts. */
    printf("WRPAIR_CODE: %s\n", code);
    fflush(stdout);
    waiting.fd = listener;
    waiting.events = POLLIN;
    waiting.revents = 0;
    polled = poll(&waiting, 1, PAIR_WAIT_MS);
    if (polled != 1 || !(waiting.revents & POLLIN)) {
        WR_DIAG("PAIR_TIMEOUT: no connection; code expired");
        goto finish;
    }
    memset(&remote, 0, sizeof(remote));
    client = accept(listener, (struct sockaddr *)&remote, &remote_length);
    if (client < 0 ||
        remote.sin_family != AF_INET ||
        ntohl(remote.sin_addr.s_addr) != INADDR_LOOPBACK) {
        WR_DIAG("PAIR_REJECTED_NONLOCAL_OR_ACCEPT_FAILED");
        goto finish;
    }
#if defined(SO_NOSIGPIPE)
    (void)setsockopt(client, SOL_SOCKET, SO_NOSIGPIPE,
                     &no_sigpipe, sizeof(no_sigpipe));
#else
    (void)no_sigpipe;
#endif
    (void)setsockopt(client, SOL_SOCKET, SO_RCVTIMEO,
                     &timeout, sizeof(timeout));
    (void)setsockopt(client, SOL_SOCKET, SO_SNDTIMEO,
                     &timeout, sizeof(timeout));

    if (!recv_all(client, header, sizeof(header)) ||
        memcmp(header, "WRPAIR1\n", 8) != 0) {
        WR_DIAG("PAIR_REJECTED_BAD_REQUEST");
        goto finish;
    }
    memcpy(challenge, "WRCHAL1\n", 8);
    memcpy(challenge + 8, nonce, sizeof(nonce));
    if (!send_all(client, challenge, sizeof(challenge)) ||
        !recv_all(client, header, sizeof(header)) ||
        memcmp(header, "WRAUTH1\n", 8) != 0 ||
        !recv_all(client, (char *)received_mac, sizeof(received_mac))) {
        WR_DIAG("PAIR_REJECTED_BAD_PROOF_FRAME");
        goto finish;
    }
    pair_mac(code, "WR-PAIR-CLIENT-V1", nonce, expected_mac);
    if (!pair_equal(received_mac, expected_mac, sizeof(received_mac))) {
        (void)send_all(client, "WRDENY1\n", 8);
        WR_DIAG("PAIR_DENIED: invalid proof; session consumed");
        goto finish;
    }
    pair_mac(code, "WR-PAIR-SERVER-V1", nonce, server_mac);
    memcpy(response, "WROKAY1\n", 8);
    memcpy(response + 8, server_mac, sizeof(server_mac));
    if (!send_all(client, response, sizeof(response))) {
        WR_DIAG("PAIR_FAILED_TO_SEND_ACK");
        goto finish;
    }
    WR_DIAG("PAIR_PROOF_ACCEPTED: possession only, NOT app identity");
    result = 0;
finish:
    if (client >= 0) close(client);
    if (listener >= 0) close(listener);
    pair_zero(code, sizeof(code));
    pair_zero(secret, sizeof(secret));
    pair_zero(nonce, sizeof(nonce));
    pair_zero(received_mac, sizeof(received_mac));
    pair_zero(expected_mac, sizeof(expected_mac));
    pair_zero(server_mac, sizeof(server_mac));
    return result;
}
#endif

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
#ifdef WEBREADER_PING_ONLY
    if (argc == 2 && strcmp(argv[1], "serve-loopback-once") == 0) {
        return serve_loopback_once();
    }
    if (argc == 2 && strcmp(argv[1], "serve-pair-once") == 0) {
        return serve_pair_once();
    }
#endif
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
    fputs("Usage: selftest | serve-once <app-container/WR> | serve-loopback-once | serve-pair-once (no installation)\n", stderr);
#else
    fputs("Usage: selftest | serve-once <app-container/WR> | inspect <ipa> <sha256> | "
          "install-confirmed <ipa> <sha256> I-CONFIRM-INSTALL\n", stderr);
#endif
    return 2;
}
