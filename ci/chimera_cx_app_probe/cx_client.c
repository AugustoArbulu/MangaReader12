/*
 * DA: check-only, sandboxed iOS12 client for the physically tested CX helper.
 * NO installation, no release fetching, no trusted identity claims.
 * Only WRCHK2\n to loopback 127.0.0.1:38973. TCP is NOT authentication.
 */
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE && defined(WR_DA_HOST_TEST)
#error "Host-test port override MUST NOT exist in iOS apps"
#endif
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "cx_client.h"
#include <arpa/inet.h>
#include <netinet/in.h>
#include <signal.h>
#include <stdint.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/time.h>
#include <unistd.h>

#define WR_DA_PORT 38973u

static WR_DA_Result exchange_fixed_frame(uint16_t port) {
    const uint8_t frame[7] = {'W','R','C','H','K','2','\n'};
    uint8_t response[8] = {0};
    uint8_t extra = 0;
    struct sockaddr_in addr;
    struct timeval timeout = {3, 0};
    int fd = socket(AF_INET, SOCK_STREAM, 0);
    WR_DA_Result status = WR_DA_TRANSPORT_ERROR;
    size_t sent = 0, received = 0;
    if (fd < 0) return status;
#ifdef SO_NOSIGPIPE
    {
        int option = 1;
        if (setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &option,
                       (socklen_t)sizeof(option)) != 0) goto done;
    }
#else
    /*
     * POSIX host harness only. Never alter the app process signal disposition
     * in the iOS target, where SO_NOSIGPIPE is defined.
     */
#if !defined(__APPLE__)
    (void)signal(SIGPIPE, SIG_IGN);
#endif
#endif
    if (setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout,
                   (socklen_t)sizeof(timeout)) != 0 ||
        setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout,
                   (socklen_t)sizeof(timeout)) != 0) goto done;
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
    addr.sin_port = htons(port);
#if defined(__APPLE__)
    addr.sin_len = (uint8_t)sizeof(addr);
#endif
    if (connect(fd, (struct sockaddr *)&addr, (socklen_t)sizeof(addr)) != 0) {
        status = WR_DA_UNAVAILABLE;
        goto done;
    }
    while (sent < sizeof(frame)) {
        ssize_t n = send(fd, frame + sent, sizeof(frame) - sent, 0);
        if (n <= 0) goto done;
        sent += (size_t)n;
    }
    if (shutdown(fd, SHUT_WR) != 0) goto done;
    while (received < sizeof(response)) {
        ssize_t n = recv(fd, response + received,
                         sizeof(response) - received, 0);
        if (n <= 0) {
            status = WR_DA_BAD_RESPONSE;
            goto done;
        }
        received += (size_t)n;
    }
    /* No trusted prefix: a response with extra bytes is invalid. */
    if (recv(fd, &extra, 1, 0) != 0) {
        status = WR_DA_BAD_RESPONSE;
        goto done;
    }
    status = WR_DA_BAD_RESPONSE;
    if (memcmp(response, "WRNOTE2\n", 8) == 0) status = WR_DA_NOTE;
    else if (memcmp(response, "WRRATE2\n", 8) == 0) status = WR_DA_RATE;
    else if (memcmp(response, "WRDENY2\n", 8) == 0) status = WR_DA_DENY;
done:
    (void)close(fd);
    return status;
}

WR_DA_Result wr_da_probe(void) {
    return exchange_fixed_frame(WR_DA_PORT);
}

#if defined(WR_DA_HOST_TEST)
WR_DA_Result wr_da_host_probe(uint16_t port) {
    if (port == 0) return WR_DA_UNAVAILABLE;
    return exchange_fixed_frame(port);
}
#endif
