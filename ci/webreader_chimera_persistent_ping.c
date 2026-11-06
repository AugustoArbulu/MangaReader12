/*
 * WebReader Chimera iOS12 persistent PING laboratory.
 *
 * Diagnostic ONLY: there is NO installer, no shell, no file read/write, no
 * IPC command besides the 8-byte WRPING1 newline. All other input is denied.
 * This can be loaded with launchd as the non-root "mobile" user.
 *
 * Listener at 127.0.0.1:38971 is NOT client code-signature authentication
 * and MUST NEVER be given installation capabilities.
 */
#define _DARWIN_C_SOURCE 1
#include <arpa/inet.h>
#include <errno.h>
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
#include <unistd.h>

#ifndef WRP_TEST_PORT
#define WRP_PORT 38971
#else
#define WRP_PORT WRP_TEST_PORT
#endif

static volatile sig_atomic_t stopped = 0;

static void stop_signal(int sig) {
    (void)sig;
    stopped = 1;
}

static int mobile_user(void) {
    if (geteuid() == 0) return 0;
#ifndef WRP_TEST_PORT
    return geteuid() == 501;
#else
    return 1;
#endif
}

static int respond_to_client(int fd) {
    char request[64];
    const char pong[] = "WRPONG1\n";
    struct timeval timeout = {2, 0};
    ssize_t received;
    size_t total = 0, sent = 0;
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO,
                     &timeout, (socklen_t)sizeof(timeout));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO,
                     &timeout, (socklen_t)sizeof(timeout));
    /* Read at most one bounded request. A zero-byte request is denied. */
    while (total < 8) {
        received = recv(fd, request + total, sizeof(request) - total, 0);
        if (received <= 0) return 0;
        total += (size_t)received;
        if (total > 8) return 0;
    }
    if (memcmp(request, "WRPING1\n", 8) != 0) return 0;
    while (sent < sizeof(pong) - 1) {
        ssize_t n = send(fd, pong + sent, sizeof(pong) - 1 - sent, 0);
        if (n <= 0) return 0;
        sent += (size_t)n;
    }
    return 1;
}

static int serve_loopback(void) {
    int listener, opt = 1;
    struct sockaddr_in address;
    struct pollfd wait_for_client;
    struct sigaction action;
    if (!mobile_user()) {
        fputs("WRP_DENY_ROOT_OR_NON_MOBILE\n", stderr);
        return 2;
    }
    memset(&action, 0, sizeof(action));
    action.sa_handler = stop_signal;
    sigemptyset(&action.sa_mask);
    (void)sigaction(SIGTERM, &action, NULL);
    (void)sigaction(SIGINT, &action, NULL);
    (void)signal(SIGPIPE, SIG_IGN);
    listener = socket(AF_INET, SOCK_STREAM, 0);
    if (listener < 0) return 3;
    if (setsockopt(listener, SOL_SOCKET, SO_REUSEADDR,
                   &opt, (socklen_t)sizeof(opt)) < 0) {
        (void)close(listener);
        return 4;
    }
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_port = htons(WRP_PORT);
    address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
#ifdef __APPLE__
    address.sin_len = (uint8_t)sizeof(address);
#endif
    if (bind(listener, (struct sockaddr *)&address,
             (socklen_t)sizeof(address)) < 0 ||
        listen(listener, 8) < 0) {
        (void)close(listener);
        return 5;
    }
    puts("WRPERSIST_READY: PING/PONG only; no installation");
    fflush(stdout);
    wait_for_client.fd = listener;
    wait_for_client.events = POLLIN;
    wait_for_client.revents = 0;
    while (!stopped) {
        int ready = poll(&wait_for_client, 1, 1000);
        if (ready == 0 || (ready < 0 && errno == EINTR)) continue;
        if (ready < 0) break;
        if ((wait_for_client.revents & POLLIN) == 0) continue;
        {
            struct sockaddr_in peer;
            socklen_t peerlen = (socklen_t)sizeof(peer);
            int client = accept(listener, (struct sockaddr *)&peer, &peerlen);
            if (client < 0) continue;
            /* Defensive check even though listener is loopback-bound. */
            if (peerlen == sizeof(peer) &&
                peer.sin_family == AF_INET &&
                ntohl(peer.sin_addr.s_addr) == INADDR_LOOPBACK)
                (void)respond_to_client(client);
            (void)close(client);
        }
    }
    (void)close(listener);
    return 0;
}

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "selftest") == 0) {
        if (!mobile_user()) return 2;
        puts("WRPERSIST_READ_ONLY: accepts WRPING1 only");
        puts("NO_APPINST_NO_IPA_NO_INSTALL");
        return 0;
    }
    if (argc == 2 && strcmp(argv[1], "serve") == 0)
        return serve_loopback();
    fputs("Usage: webreader-pinglab selftest | serve\n", stderr);
    return 2;
}
