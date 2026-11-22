/*
 * WebReader iOS12/Chimera check-only transport laboratory (Phase CX).
 *
 * Deliberately NOT a software updater or installer. One non-root mobile
 * process owns one loopback listener and one serialized rate-limit gate.
 * Any untrusted local client can submit exactly WRCHK2\n, then half-close
 * its writing side. No paths, release identifiers, URLs, digests, secrets
 * or installation requests exist in this protocol. An accepted notice
 * records NO network fetch and NO authorization to modify applications.
 *
 * Reuses the Phase CW native policy and mutex dispatcher. This service
 * cannot inherit privileges, install apps, execute subprocesses, or write
 * the user's files. Compile for the device only AFTER reviewing the lab.
 */
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "build70_cw_shared_dispatch.h"
#include <arpa/inet.h>
#include <errno.h>
#include <inttypes.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>

#if defined(WR_CX_HOST_TEST_PORT)
#if defined(__APPLE__)
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE
#error "Host-test port override cannot be used for an iOS device service"
#endif
#endif
#define WR_CX_PORT WR_CX_HOST_TEST_PORT
#else
#define WR_CX_PORT 38973
#endif

static volatile sig_atomic_t stopped = 0;

static void stop_handler(int ignored) {
    (void)ignored;
    stopped = 1;
}

static int accepted_identity(void) {
    if (geteuid() == 0) return 0;
#ifndef WR_CX_HOST_TEST_PORT
    return getuid() == 501 && geteuid() == 501;
#else
    return 1; /* Unprivileged test runner, NEVER iOS device build. */
#endif
}

static int monotonic_milliseconds(uint64_t *value) {
    struct timespec now;
    if (clock_gettime(CLOCK_MONOTONIC, &now) != 0 ||
        now.tv_sec < 0 || now.tv_nsec < 0 ||
        now.tv_nsec >= 1000000000L) return 0;
    if ((uint64_t)now.tv_sec > (UINT64_MAX - 999u) / 1000u) return 0;
    *value = (uint64_t)now.tv_sec * 1000u +
             (uint64_t)now.tv_nsec / 1000000u;
    return 1;
}

static int send_all(int fd, const char *bytes, size_t length) {
    size_t sent = 0;
    while (sent < length) {
        ssize_t n = send(fd, bytes + sent, length - sent, 0);
        if (n <= 0) return 0;
        sent += (size_t)n;
    }
    return 1;
}

static void handle_one(int fd, WR_CW_Dispatcher *dispatcher) {
    uint8_t packet[WR_CW_FRAME_BYTES + 1];
    size_t total = 0;
    ssize_t got;
    uint64_t ms = 0;
    WR_CW_Decision outcome = {0};
    const char *response = "WRDENY2\n"; /* Fixed response, never an install token. */
    struct timeval timeout = {2, 0};

    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
    /*
     * Require EOF after a complete seven-byte frame. This removes the
     * ambiguity of a valid prefix followed by a delayed installer request.
     * A stuck client is bounded by a receive timeout; no content is logged.
     */
    for (;;) {
        if (total == sizeof(packet)) break;
        got = recv(fd, packet + total, sizeof(packet) - total, 0);
        if (got < 0) return;  /* Timeout, signal, or malformed transmission. */
        if (got == 0) {
            if (total == WR_CW_FRAME_BYTES &&
                monotonic_milliseconds(&ms)) {
                outcome = wr_cw_dispatch_offer(dispatcher, packet, total, ms);
                /* Every bit of installation/publisher authority is false. */
                if (!outcome.caller_authenticated &&
                    !outcome.publisher_verified &&
                    !outcome.artifact_selected_by_client &&
                    !outcome.installer_authorized &&
                    !outcome.installation_performed) {
                    if (outcome.status == WR_CW_CHECK_NOTICE_ACCEPTED)
                        response = "WRNOTE2\n";
                    else if (outcome.status == WR_CW_RATE_LIMITED)
                        response = "WRRATE2\n";
                }
            }
            break;
        }
        total += (size_t)got;
    }
    (void)send_all(fd, response, 8);
}

static int serve(void) {
    int listener = -1, reuse = 1, result = 1;
    struct sockaddr_in addr;
    WR_CW_Dispatcher *dispatcher = NULL;
    struct sigaction action;
    if (!accepted_identity()) {
        fputs("WR_CX_DENIED_IDENTITY\n", stderr);
        return 2;
    }
    dispatcher = wr_cw_dispatch_new();
    if (!dispatcher) return 3;
    memset(&action, 0, sizeof(action));
    action.sa_handler = stop_handler;
    sigemptyset(&action.sa_mask);
    (void)sigaction(SIGINT, &action, NULL);
    (void)sigaction(SIGTERM, &action, NULL);
    (void)signal(SIGPIPE, SIG_IGN);
    listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) goto finish;
    if (setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &reuse,
                   sizeof(reuse)) != 0) goto finish;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(WR_CX_PORT);
#ifdef __APPLE__
    addr.sin_len = (uint8_t)sizeof(addr);
#endif
    if (bind(listener, (struct sockaddr *)&addr, sizeof(addr)) != 0 ||
        listen(listener, 8) != 0) goto finish;
#if defined(WR_CX_HOST_TEST_PORT)
    {
        socklen_t size = sizeof(addr);
        if (getsockname(listener, (struct sockaddr *)&addr, &size) != 0)
            goto finish;
        printf("WR_CX_HOST_PORT=%u\n", (unsigned)ntohs(addr.sin_port));
    }
#else
    puts("WR_CX_LISTENING_127_0_0_1_38973");
#endif
    fflush(stdout);
    result = 0;
    while (!stopped) {
        struct pollfd waitfd = {listener, POLLIN, 0};
        int ready = poll(&waitfd, 1, 250);
        if (ready == 0 || (ready < 0 && errno == EINTR)) continue;
        if (ready < 0 || (waitfd.revents & (POLLERR | POLLNVAL))) {
            result = 4;
            break;
        }
        if (!(waitfd.revents & POLLIN)) continue;
        {
            struct sockaddr_in remote;
            socklen_t length = sizeof(remote);
            int client = accept(listener, (struct sockaddr *)&remote, &length);
            if (client < 0) continue;
            if (length == sizeof(remote) &&
                remote.sin_family == AF_INET &&
                ntohl(remote.sin_addr.s_addr) == INADDR_LOOPBACK) {
                handle_one(client, dispatcher);
            }
            (void)close(client);
        }
    }
finish:
    if (listener >= 0) (void)close(listener);
    wr_cw_dispatch_free(dispatcher);
    return result;
}

/*
 * Explicit CLI-only physical QA. Runs as mobile under NewTerm, not inside the
 * sandboxed app; sends no data other than WRCHK2\n to the local check-only
 * service. This is intentionally NOT an update or installation command.
 */
static int probe(uint16_t port) {
    int fd = -1, result = 6;
    struct sockaddr_in addr;
    struct timeval timeout = {3, 0};
    const uint8_t request[WR_CW_FRAME_BYTES] = {'W','R','C','H','K','2','\n'};
    uint8_t response[9] = {0};
    size_t sent = 0, received = 0;
    ssize_t count;
    int nosigpipe = 1;
    if (!accepted_identity()) return 2;
    fd = socket(AF_INET, SOCK_STREAM, 0);
    if (fd < 0) goto finish;
#ifdef SO_NOSIGPIPE
    if (setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &nosigpipe,
                   sizeof(nosigpipe)) != 0) goto finish;
#else
    (void)nosigpipe;
    (void)signal(SIGPIPE, SIG_IGN);
#endif
    if (setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout,
                   sizeof(timeout)) != 0 ||
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                   sizeof(timeout)) != 0) goto finish;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(port);
#ifdef __APPLE__
    addr.sin_len = (uint8_t)sizeof(addr);
#endif
    if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) != 0) {
        puts("WR_CX_PROBE=UNAVAILABLE");
        result = 3;
        goto finish;
    }
    while (sent < sizeof(request)) {
        count = send(fd, request + sent, sizeof(request) - sent, 0);
        if (count <= 0) goto finish;
        sent += (size_t)count;
    }
    if (shutdown(fd, SHUT_WR) != 0) goto finish;
    while (received < 8) {
        count = recv(fd, response + received, 8 - received, 0);
        if (count <= 0) goto finish;
        received += (size_t)count;
    }
    count = recv(fd, response + 8, 1, 0);
    if (count != 0) goto finish;
    if (memcmp(response, "WRNOTE2\n", 8) == 0) {
        puts("WR_CX_PROBE=NOTE_ONLY_NO_RELEASE_CHECK_NO_INSTALL");
        result = 0;
    } else if (memcmp(response, "WRRATE2\n", 8) == 0) {
        puts("WR_CX_PROBE=RATE_LIMITED_NO_INSTALL");
        result = 0;
    } else if (memcmp(response, "WRDENY2\n", 8) == 0) {
        puts("WR_CX_PROBE=DENIED_NO_INSTALL");
        result = 5;
    }
finish:
    if (fd >= 0) (void)close(fd);
    if (result == 6) puts("WR_CX_PROBE=PROTOCOL_OR_TRANSPORT_FAILURE_NO_INSTALL");
    return result;
}

int main(int argc, char **argv) {
#if defined(WR_CX_HOST_TEST_PORT)
    // A dynamic test port is permitted ONLY on an unprivileged host build.
    // Device binaries do not compile this branch (see TARGET_OS_IPHONE).
    if (argc == 3 && strcmp(argv[1], "probe") == 0) {
        char *end = NULL;
        unsigned long number = strtoul(argv[2], &end, 10);
        if (argv[2][0] == '\0' || *end != '\0' ||
            number == 0 || number > 65535) return 2;
        return probe((uint16_t)number);
    }
#endif
    if (argc != 2) {
        fputs("Usage: webreader-checkonly selftest | serve | probe\n", stderr);
        return 2;
    }
    if (strcmp(argv[1], "selftest") == 0) {
        if (!accepted_identity()) return 2;
        puts("WR_CX_CHECKONLY_POLICY_ONLY");
        puts("WR_CX_NO_IPA_NO_APPINST_NO_INSTALL");
        return 0;
    }
    if (strcmp(argv[1], "serve") == 0) return serve();
    if (strcmp(argv[1], "probe") == 0) return probe(WR_CX_PORT);
    return 2;
}
