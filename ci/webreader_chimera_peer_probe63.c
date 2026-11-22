/*
 * WebReader Build63: isolated peer-metadata capability probe.
 * This binary has NO server mode, installation command, appinst dependency,
 * file downloads, or persistent launchd job. It opens short-lived local
 * sockets between two controlled processes and exits.
 *
 * A PID is observational data, NEVER a sufficient authorization decision.
 * TCP_PEER_PID is a private Darwin API (0x204) and may fail on iOS 12.
 */
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include <arpa/inet.h>
#include <errno.h>
#include <netinet/in.h>
#include <poll.h>
#include <signal.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/un.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <unistd.h>

#define WR_TCP_PEER_PID_PRIVATE 0x204

static void set_timeout(int fd) {
    struct timeval duration = {3, 0};
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &duration, sizeof(duration));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &duration, sizeof(duration));
}

static int connect_to_server(int domain, const struct sockaddr *addr,
                             socklen_t addr_len) {
    int fd = socket(domain, SOCK_STREAM, 0);
    char ping = 'Q', reply = 0;
    if (fd < 0) return 61;
    set_timeout(fd);
    if (connect(fd, addr, addr_len) != 0) { (void)close(fd); return 62; }
    if (send(fd, &ping, 1, 0) != 1 || recv(fd, &reply, 1, 0) != 1 || reply != 'R') {
        (void)close(fd);
        return 63;
    }
    (void)close(fd);
    return 0;
}

static void print_peer_status(const char *transport, int fd, pid_t expected) {
    pid_t observed = -1;
    socklen_t len = (socklen_t)sizeof(observed);
    int rc;
#if defined(__APPLE__)
    if (strcmp(transport, "TCP_LOOPBACK") == 0) {
        /* Private XNU TCP_PEER_PID: measured experimentally, never trusted. */
        rc = getsockopt(fd, IPPROTO_TCP, WR_TCP_PEER_PID_PRIVATE,
                        &observed, &len);
    } else {
        rc = getsockopt(fd, SOL_LOCAL, LOCAL_PEERPID, &observed, &len);
    }
#elif defined(SO_PEERCRED)
    /* Linux fallback is for host smoke testing only, not iOS evidence. */
    struct { pid_t pid; uid_t uid; gid_t gid; } cred;
    socklen_t credlen = (socklen_t)sizeof(cred);
    rc = getsockopt(fd, SOL_SOCKET, SO_PEERCRED, &cred, &credlen);
    if (rc == 0 && credlen == sizeof(cred)) {
        observed = cred.pid;
        len = sizeof(observed);
    }
#else
    (void)fd;
    rc = -1;
#endif
    if (rc != 0 || len != sizeof(observed) || observed <= 0) {
        printf("PROBE %s PEER_PID=UNAVAILABLE AUTHORIZATION=DENIED\n", transport);
    } else if (observed == expected) {
        printf("PROBE %s PEER_PID=MATCH AUTHORIZATION=DENIED\n", transport);
    } else {
        printf("PROBE %s PEER_PID=MISMATCH AUTHORIZATION=DENIED\n", transport);
    }
}

static int run_one(int domain, const char *transport) {
    struct sockaddr_storage addr;
    socklen_t addrlen = 0;
    struct sockaddr_in *tcp = (struct sockaddr_in *)(void *)&addr;
    struct sockaddr_un *unix_addr = (struct sockaddr_un *)(void *)&addr;
    char folder[] = "/tmp/wrpeer63-XXXXXX";
    char pathname[sizeof(unix_addr->sun_path)];
    int listener = -1, client = -1, status = 0;
    pid_t kid = -1;
    int wait_status = 0;
    struct pollfd event;
    memset(&addr, 0, sizeof(addr));
    memset(pathname, 0, sizeof(pathname));
    if (domain == AF_INET) {
        tcp->sin_family = AF_INET;
        tcp->sin_addr.s_addr = htonl(INADDR_LOOPBACK);
        tcp->sin_port = htons(0);
#if defined(__APPLE__)
        tcp->sin_len = (uint8_t)sizeof(*tcp);
#endif
        addrlen = (socklen_t)sizeof(*tcp);
    } else {
        if (!mkdtemp(folder)) return 10;
        if (snprintf(pathname, sizeof(pathname), "%s/s", folder) <= 0) {
            (void)rmdir(folder);
            return 11;
        }
        unix_addr->sun_family = AF_UNIX;
        (void)strcpy(unix_addr->sun_path, pathname);
        addrlen = (socklen_t)(offsetof(struct sockaddr_un, sun_path) +
                              strlen(pathname) + 1);
#if defined(__APPLE__)
        unix_addr->sun_len = (uint8_t)addrlen;
#endif
    }
    listener = socket(domain, SOCK_STREAM, 0);
    if (listener < 0) { status = 12; goto done; }
    if (bind(listener, (struct sockaddr *)(void *)&addr, addrlen) != 0 ||
        listen(listener, 1) != 0) { status = 13; goto done; }
    if (domain == AF_INET) {
        addrlen = (socklen_t)sizeof(*tcp);
        if (getsockname(listener, (struct sockaddr *)(void *)&addr,
                        &addrlen) != 0) { status = 14; goto done; }
    }
    kid = fork();
    if (kid < 0) { status = 15; goto done; }
    if (kid == 0) {
        int result;
        (void)close(listener);
        result = connect_to_server(domain,
                                   (struct sockaddr *)(void *)&addr, addrlen);
        _exit(result);
    }
    event.fd = listener;
    event.events = POLLIN;
    event.revents = 0;
    if (poll(&event, 1, 3000) <= 0 || !(event.revents & POLLIN)) {
        status = 16;
        goto done;
    }
    client = accept(listener, NULL, NULL);
    if (client < 0) { status = 17; goto done; }
    set_timeout(client);
    {
        char ping = 0, reply = 'R';
        if (recv(client, &ping, 1, 0) != 1 || ping != 'Q') {
            status = 18;
            goto done;
        }
        print_peer_status(transport, client, kid);
        if (send(client, &reply, 1, 0) != 1) status = 19;
    }
done:
    if (client >= 0) (void)close(client);
    if (listener >= 0) (void)close(listener);
    if (kid > 0) {
        if (status != 0) (void)kill(kid, SIGTERM);
        if (waitpid(kid, &wait_status, 0) != kid ||
            !WIFEXITED(wait_status) || WEXITSTATUS(wait_status) != 0)
            status = status ? status : 20;
    }
    if (domain == AF_UNIX) {
        (void)unlink(pathname);
        (void)rmdir(folder);
    }
    if (status != 0)
        printf("PROBE %s TRANSPORT=FAILED_%d AUTHORIZATION=DENIED\n",
               transport, status);
    return status;
}

int main(int argc, char **argv) {
    int tcp_rc, unix_rc;
    if (argc != 2 || strcmp(argv[1], "selftest") != 0) {
        fputs("Usage: webreader-peerprobe63 selftest\n", stderr);
        return 2;
    }
    if (geteuid() == 0) {
        fputs("REFUSE_ROOT: observational peer metadata probe only\n", stderr);
        return 3;
    }
    (void)signal(SIGPIPE, SIG_IGN);
    (void)umask(0077);
    printf("WEBREADER_BUILD63_PEER_CAPABILITY: non-root, no install\n");
    tcp_rc = run_one(AF_INET, "TCP_LOOPBACK");
    unix_rc = run_one(AF_UNIX, "UNIX_LOCAL");
    puts("FINAL_INSTALL_AUTHORIZATION=DENIED");
    return tcp_rc || unix_rc ? 4 : 0;
}
