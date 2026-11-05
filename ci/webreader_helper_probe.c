/*
 * WebReader helper IPC DIAGNOSTIC v1 — strictly non-privileged.
 *
 * Standalone one-shot UNIX socket PING/PONG. Deliberately incapable of
 * installing IPA, reading archives, executing commands, or running as root.
 *
 * Usage:
 *   webreader-helper-probe serve /absolute/private/directory
 *   webreader-helper-probe probe /absolute/private/directory
 *
 * This is NOT the production Chimera helper; it only proves that two separate
 * non-root processes can exchange a fixed local message. No socket reply
 * authenticates a production release, code signature, or future root helper.
 */
#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <sys/types.h>
#include <sys/un.h>
#include <unistd.h>

#if defined(__linux__)
#include <sys/uio.h>
#endif

#define SOCKET_NAME "wrp.sock"
#define REQUEST "WRPING1\n"
#define RESPONSE "WRPONG1\n"
#define MESSAGE_LEN 8
#define CONNECT_TIMEOUT_MS 3000

static int socket_path(const char *dir, char path[sizeof(((struct sockaddr_un *)0)->sun_path)]) {
    const size_t max = sizeof(((struct sockaddr_un *)0)->sun_path);
    size_t len;
    if (!dir || dir[0] != '/' || strlen(dir) > max) return -1;
    len = strlen(dir);
    if (len == 1 || len + 1 + strlen(SOCKET_NAME) >= max) return -1;
    if (dir[len - 1] == '/' || strstr(dir, "/../") || strstr(dir, "/./") ||
        strstr(dir, "//") || (len >= 3 && strcmp(dir + len - 3, "/..") == 0) ||
        (len >= 2 && strcmp(dir + len - 2, "/.") == 0)) return -1;
    memset(path, 0, max);
    memcpy(path, dir, len);
    path[len] = '/';
    memcpy(path + len + 1, SOCKET_NAME, strlen(SOCKET_NAME));
    return 0;
}

static int trusted_directory(const char *dir) {
    int fd;
    struct stat st;
    if (dir[0] != '/') return -1;
    fd = open(dir, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return -1;
    if (fstat(fd, &st) != 0 || !S_ISDIR(st.st_mode) ||
        st.st_uid != geteuid() || (st.st_mode & 077) != 0) {
        close(fd);
        return -1;
    }
    return fd;
}

static void timeouts(int fd) {
    struct timeval tv;
    tv.tv_sec = 2;
    tv.tv_usec = 0;
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &tv, sizeof(tv));
#if defined(SO_NOSIGPIPE)
    int enabled = 1;
    (void)setsockopt(fd, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled));
#endif
}

static int send_exact(int fd, const char *message, size_t length) {
    size_t done = 0;
    while (done < length) {
#if defined(MSG_NOSIGNAL)
        ssize_t n = send(fd, message + done, length - done, MSG_NOSIGNAL);
#else
        ssize_t n = send(fd, message + done, length - done, 0);
#endif
        if (n <= 0) return -1;
        done += (size_t)n;
    }
    return 0;
}

static int receive_exact(int fd, char *target, size_t length) {
    size_t done = 0;
    while (done < length) {
        ssize_t n = recv(fd, target + done, length - done, 0);
        if (n <= 0) return -1;
        done += (size_t)n;
    }
    return 0;
}

static int same_user_peer(int connection) {
#if defined(__APPLE__)
    uid_t peer_uid = (uid_t)-1;
    gid_t peer_gid = (gid_t)-1;
    return getpeereid(connection, &peer_uid, &peer_gid) == 0 &&
           peer_uid == geteuid();
#elif defined(__linux__)
    struct ucred peer;
    socklen_t size = sizeof(peer);
    return getsockopt(connection, SOL_SOCKET, SO_PEERCRED, &peer, &size) == 0 &&
           size == sizeof(peer) && peer.uid == geteuid();
#else
    (void)connection;
    return 0;  /* Never silently trust an unidentified OS peer. */
#endif
}

static void remove_own_socket(const char *path, const struct stat *created) {
    struct stat now;
    if (created && lstat(path, &now) == 0 &&
        S_ISSOCK(now.st_mode) && now.st_dev == created->st_dev &&
        now.st_ino == created->st_ino) {
        (void)unlink(path);
    }
}

static int serve(const char *dir, const char *path) {
    int dfd = -1, server = -1, client = -1, result = 1, bound = 0;
    struct stat created;
    struct sockaddr_un address;
    struct pollfd waitfd;
    char request[MESSAGE_LEN];
    memset(&created, 0, sizeof(created));

    dfd = trusted_directory(dir);
    if (dfd < 0) { fprintf(stderr, "private directory required\n"); goto cleanup; }
    struct stat occupied;
    if (lstat(path, &occupied) == 0 || errno != ENOENT) {
        fprintf(stderr, "socket name already occupied\n");
        goto cleanup;
    }
    server = socket(AF_UNIX, SOCK_STREAM, 0);
    if (server < 0) goto cleanup;
    timeouts(server);
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
#if defined(__APPLE__)
    address.sun_len = (uint8_t)sizeof(address);
#endif
    memcpy(address.sun_path, path, strlen(path) + 1);
    umask(0077);
    if (bind(server, (const struct sockaddr *)&address, sizeof(address)) != 0)
        goto cleanup;
    bound = 1;
    if (lstat(path, &created) != 0 ||
        !S_ISSOCK(created.st_mode) || created.st_uid != geteuid() ||
        chmod(path, 0600) != 0) goto cleanup;
    if (listen(server, 1) != 0) goto cleanup;

    waitfd.fd = server;
    waitfd.events = POLLIN;
    waitfd.revents = 0;
    if (poll(&waitfd, 1, CONNECT_TIMEOUT_MS) != 1 || !(waitfd.revents & POLLIN))
        goto cleanup;

    client = accept(server, NULL, NULL);
    if (client < 0 || !same_user_peer(client)) goto cleanup;
    timeouts(client);
    if (receive_exact(client, request, sizeof(request)) != 0 ||
        memcmp(request, REQUEST, sizeof(request)) != 0) goto cleanup;
    if (send_exact(client, RESPONSE, MESSAGE_LEN) != 0) goto cleanup;
    result = 0;
cleanup:
    if (client >= 0) close(client);
    if (server >= 0) close(server);
    if (bound && created.st_ino != 0) remove_own_socket(path, &created);
    if (dfd >= 0) close(dfd);
    return result;
}

static int probe(const char *dir, const char *path) {
    int dfd = -1, fd = -1, result = 1;
    struct stat st;
    struct sockaddr_un address;
    char answer[MESSAGE_LEN];

    dfd = trusted_directory(dir);
    if (dfd < 0) { fprintf(stderr, "private directory required\n"); goto cleanup; }
    if (lstat(path, &st) != 0 || !S_ISSOCK(st.st_mode) ||
        st.st_uid != geteuid() || (st.st_mode & 077) != 0) goto cleanup;
    fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) goto cleanup;
    timeouts(fd);
    memset(&address, 0, sizeof(address));
    address.sun_family = AF_UNIX;
#if defined(__APPLE__)
    address.sun_len = (uint8_t)sizeof(address);
#endif
    memcpy(address.sun_path, path, strlen(path) + 1);
    if (connect(fd, (const struct sockaddr *)&address, sizeof(address)) != 0)
        goto cleanup;
    if (!same_user_peer(fd)) goto cleanup;
    if (send_exact(fd, REQUEST, MESSAGE_LEN) != 0 ||
        receive_exact(fd, answer, sizeof(answer)) != 0 ||
        memcmp(answer, RESPONSE, sizeof(answer)) != 0) goto cleanup;
    puts("WEBREADER_PING_OK (same-UID, NOT authenticated for installation)");
    result = 0;
cleanup:
    if (fd >= 0) close(fd);
    if (dfd >= 0) close(dfd);
    return result;
}

int main(int argc, char **argv) {
    char path[sizeof(((struct sockaddr_un *)0)->sun_path)];
    signal(SIGPIPE, SIG_IGN);
    if (geteuid() == 0) {
        fprintf(stderr, "refusing privileged/root execution\n");
        return 2;
    }
    if (argc != 3 || socket_path(argv[2], path) != 0) {
        fprintf(stderr, "usage: webreader-helper-probe {serve|probe} /private/absolute/dir\n");
        return 2;
    }
    if (strcmp(argv[1], "serve") == 0) return serve(argv[2], path);
    if (strcmp(argv[1], "probe") == 0) return probe(argv[2], path);
    fprintf(stderr, "unsupported operation: only serve/probe\n");
    return 2;
}
