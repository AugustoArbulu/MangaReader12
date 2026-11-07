/*
 * WebReader Build66 Phase H — macOS-only NONPRIVILEGED separate-executable lab.
 *
 * Distinct signed client processes connect to a separately signed server.
 * Server uses kernel LOCAL_PEERTOKEN + csops_audittoken to compare the code
 * running on THAT live connection to an independently derived reference
 * from the expected CLIENT executable's CodeDirectory. The reference is
 * supplied on argv by the test harness and is NOT a trusted deployment pin.
 *
 * This is a controlled macOS laboratory, NOT iOS12/Chimera support evidence.
 * There is NO installation, helper, root, appinst, network, privileged socket,
 * token/hash/PID logging, or WebReader app authentication here.
 */
#define _DARWIN_C_SOURCE 1
#include <dlfcn.h>
#include <errno.h>
#include <mach/mach.h>
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
#include <sys/time.h>
#include <unistd.h>

#ifndef LOCAL_PEERTOKEN
#define WR_LOCAL_PEERTOKEN 0x006
#else
#define WR_LOCAL_PEERTOKEN LOCAL_PEERTOKEN
#endif
#define WR_CS_OPS_CDHASH 5
#define WR_MAX_SOCKET_PATH 100

#ifndef WR66_VARIANT
#define WR66_VARIANT 0
#endif
#define WR_STRINGIFY_INNER(x) #x
#define WR_STRINGIFY(x) WR_STRINGIFY_INNER(x)
/* The included constant makes clients have different CodeDirectories. */
__attribute__((used))
static const char wr_lab_variant[] = "WR66-TEST-EXECUTABLE-VARIANT-" WR_STRINGIFY(WR66_VARIANT);

typedef int (*wr_csops_t)(pid_t, unsigned int, void *, size_t, audit_token_t *);

static void timeout_for(int fd) {
    struct timeval timeout = {3, 0};
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &timeout, sizeof(timeout));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &timeout, sizeof(timeout));
}

static int parse_hex(const char *text, unsigned char out[20]) {
    size_t i;
    if (strlen(text) != 40) return 0;
    for (i = 0; i < 20; ++i) {
        char pair[3] = {text[i * 2], text[i * 2 + 1], 0};
        unsigned int v;
        if (!((pair[0] >= '0' && pair[0] <= '9') ||
              (pair[0] >= 'a' && pair[0] <= 'f'))) return 0;
        if (!((pair[1] >= '0' && pair[1] <= '9') ||
              (pair[1] >= 'a' && pair[1] <= 'f'))) return 0;
        if (sscanf(pair, "%2x", &v) != 1) return 0;
        out[i] = (unsigned char)v;
    }
    return 1;
}

static int address_for(const char *path, struct sockaddr_un *address,
                       socklen_t *length) {
    size_t n = strlen(path);
    if (n == 0 || n >= sizeof(address->sun_path) ||
        n > WR_MAX_SOCKET_PATH || path[0] != '/') return 0;
    memset(address, 0, sizeof(*address));
    address->sun_family = AF_UNIX;
    memcpy(address->sun_path, path, n + 1);
    *length = (socklen_t)(offsetof(struct sockaddr_un, sun_path) + n + 1);
    address->sun_len = (uint8_t)*length;
    return 1;
}

static int client(const char *path) {
    struct sockaddr_un address;
    socklen_t length;
    int fd, result = 0;
    char acknowledgement = 0;
    if (!address_for(path, &address, &length)) return 2;
    fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return 3;
    timeout_for(fd);
    if (connect(fd, (struct sockaddr *)(void *)&address, length) != 0 ||
        send(fd, "WRHELLO1", 8, 0) != 8 ||
        recv(fd, &acknowledgement, 1, 0) != 1 ||
        acknowledgement != 'R') result = 4;
    (void)close(fd);
    return result;
}

static const char *classify_peer(int fd, const unsigned char expected[20]) {
    audit_token_t token, mutation;
    socklen_t size = sizeof(token);
    wr_csops_t csops;
    unsigned char observed[20] = {0};
    int result;
    memset(&token, 0, sizeof(token));
    if (getsockopt(fd, SOL_LOCAL, WR_LOCAL_PEERTOKEN, &token, &size) != 0 ||
        size != sizeof(token) || token.val[5] == 0 || token.val[7] == 0)
        return "TOKEN_UNAVAILABLE";
    csops = (wr_csops_t)dlsym(RTLD_DEFAULT, "csops_audittoken");
    if (!csops) return "CSOPS_MISSING";
    result = csops((pid_t)token.val[5], WR_CS_OPS_CDHASH,
                   observed, sizeof(observed), &token);
    if (result != 0) return "CDHASH_UNAVAILABLE";
    mutation = token;
    mutation.val[7] ^= 1u;
    result = csops((pid_t)token.val[5], WR_CS_OPS_CDHASH,
                   observed, sizeof(observed), &mutation);
    if (result == 0) return "TOKEN_MUTATION_UNSAFE";
    result = csops(getpid(), WR_CS_OPS_CDHASH,
                   observed, sizeof(observed), &token);
    if (result == 0) return "CROSS_PID_UNSAFE";
    /* The successful original must be sampled AFTER negative probes:
       an implementation could scribble over the destination buffer. */
    memset(observed, 0, sizeof(observed));
    if (csops((pid_t)token.val[5], WR_CS_OPS_CDHASH,
              observed, sizeof(observed), &token) != 0)
        return "CDHASH_UNAVAILABLE";
    return memcmp(expected, observed, sizeof(observed)) == 0 ?
           "MATCH_ONLY_NO_AUTH" : "MISMATCH_REJECTED";
}

static int serve(const char *path, const char *expected_text) {
    struct sockaddr_un address;
    socklen_t length;
    unsigned char expected[20] = {0};
    int fd = -1, clientfd = -1, success = 0;
    struct pollfd poll_wait;
    char incoming[8] = {0};
    const char *outcome = "TRANSPORT_FAILED";
    if (!parse_hex(expected_text, expected)) {
        puts("RESULT REFERENCE_INVALID AUTHORIZATION=DENIED");
        puts("FINAL_INSTALL_AUTHORIZATION=DENIED");
        return 5;
    }
    if (!address_for(path, &address, &length)) return 6;
    fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) return 7;
    timeout_for(fd);
    if (bind(fd, (struct sockaddr *)(void *)&address, length) != 0 ||
        chmod(path, 0600) != 0 || listen(fd, 1) != 0) goto done;
    puts("READY NONROOT SINGLE_CONNECTION AUTHORIZATION=DENIED");
    fflush(stdout);
    poll_wait.fd = fd;
    poll_wait.events = POLLIN;
    poll_wait.revents = 0;
    if (poll(&poll_wait, 1, 3000) != 1 ||
        !(poll_wait.revents & POLLIN)) goto done;
    clientfd = accept(fd, NULL, NULL);
    if (clientfd < 0) goto done;
    timeout_for(clientfd);
    if (recv(clientfd, incoming, sizeof(incoming), MSG_WAITALL) != 8 ||
        memcmp(incoming, "WRHELLO1", 8) != 0) {
        outcome = "PROTOCOL_REJECTED";
        goto done;
    }
    outcome = classify_peer(clientfd, expected);
    success = send(clientfd, "R", 1, 0) == 1;
done:
    if (clientfd >= 0) (void)close(clientfd);
    if (fd >= 0) (void)close(fd);
    (void)unlink(path);
    printf("RESULT %s AUTHORIZATION=DENIED\n", outcome);
    puts("FINAL_INSTALL_AUTHORIZATION=DENIED");
    return success ? 0 : 8;
}


/* Phase H: transfer an already CONNECTED application socket via SCM_RIGHTS.
 * The origin executable NEVER writes WRHELLO1 on the connected descriptor.
 * Only the separately executed receiver writes application bytes.
 * This deliberately tests whether LOCAL_PEERTOKEN identifies the original
 * CONNECTOR rather than the process now WRITING to the shared socket.
 */
static int send_connected_fd(int control_fd, int app_fd) {
    union {
        struct cmsghdr alignment;
        unsigned char bytes[CMSG_SPACE(sizeof(int))];
    } aux;
    struct iovec iov;
    struct msghdr msg;
    struct cmsghdr *cmsg;
    char tag = 'F';
    memset(&aux, 0, sizeof(aux));
    memset(&msg, 0, sizeof(msg));
    iov.iov_base = &tag;
    iov.iov_len = 1;
    msg.msg_iov = &iov;
    msg.msg_iovlen = 1;
    msg.msg_control = aux.bytes;
    msg.msg_controllen = sizeof(aux.bytes);
    cmsg = CMSG_FIRSTHDR(&msg);
    if (!cmsg) return 0;
    cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type = SCM_RIGHTS;
    cmsg->cmsg_len = CMSG_LEN(sizeof(int));
    memcpy(CMSG_DATA(cmsg), &app_fd, sizeof(app_fd));
    return sendmsg(control_fd, &msg, 0) == 1;
}

static int receive_connected_fd(int control_fd) {
    union {
        struct cmsghdr alignment;
        unsigned char bytes[CMSG_SPACE(sizeof(int))];
    } aux;
    struct iovec iov;
    struct msghdr msg;
    struct cmsghdr *cmsg;
    char tag = 0;
    int received = -1;
    memset(&aux, 0, sizeof(aux));
    memset(&msg, 0, sizeof(msg));
    iov.iov_base = &tag;
    iov.iov_len = 1;
    msg.msg_iov = &iov;
    msg.msg_iovlen = 1;
    msg.msg_control = aux.bytes;
    msg.msg_controllen = sizeof(aux.bytes);
    if (recvmsg(control_fd, &msg, 0) != 1 || tag != 'F' ||
        (msg.msg_flags & (MSG_CTRUNC | MSG_TRUNC)) != 0) return -1;
    cmsg = CMSG_FIRSTHDR(&msg);
    if (!cmsg || cmsg->cmsg_level != SOL_SOCKET ||
        cmsg->cmsg_type != SCM_RIGHTS ||
        cmsg->cmsg_len != CMSG_LEN(sizeof(int)) ||
        CMSG_NXTHDR(&msg, cmsg) != NULL) return -1;
    memcpy(&received, CMSG_DATA(cmsg), sizeof(received));
    return received;
}

static int handoff_origin(const char *app_path, const char *receiver_path,
                          int three_messages) {
    struct sockaddr_un appaddr, ctrladdr;
    socklen_t applen, ctrllen;
    int app_fd = -1, ctrl_fd = -1, outcome = 22;
    char acknowledgement = 0;
    if (!address_for(app_path, &appaddr, &applen) ||
        !address_for(receiver_path, &ctrladdr, &ctrllen)) return 21;
    app_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    ctrl_fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (app_fd < 0 || ctrl_fd < 0) goto done;
    timeout_for(app_fd);
    timeout_for(ctrl_fd);
    if (connect(app_fd, (struct sockaddr *)(void *)&appaddr, applen) != 0)
        goto done;
    /* Three-message variant: A sends the first application message. */
    if (three_messages &&
        (send(app_fd, "WRHELLO1", 8, 0) != 8 ||
         recv(app_fd, &acknowledgement, 1, 0) != 1 ||
         acknowledgement != 'R')) goto done;
    if (connect(ctrl_fd, (struct sockaddr *)(void *)&ctrladdr, ctrllen) != 0 ||
        !send_connected_fd(ctrl_fd, app_fd)) goto done;
    /* One-message mode: A never writes application data. Three-message
     * mode: A sent message 1; B alone writes message 2. A remains alive
     * while B receives its ACK through the same application connection.
     */
    if (recv(ctrl_fd, &acknowledgement, 1, 0) != 1 ||
        acknowledgement != 'K') goto done;
    /* B sent message 2. In three-message mode B still holds its copy,
     * while A sends message 3; descriptor closure cannot explain rebinding.
     */
    if (three_messages &&
        (send(app_fd, "WRHELLO1", 8, 0) != 8 ||
         recv(app_fd, &acknowledgement, 1, 0) != 1 ||
         acknowledgement != 'R' ||
         send(ctrl_fd, "D", 1, 0) != 1)) goto done;
    outcome = 0;
done:
    if (ctrl_fd >= 0) (void)close(ctrl_fd);
    if (app_fd >= 0) (void)close(app_fd);
    if (outcome == 0) {
        puts(three_messages ? "ORIGIN_SENT_FIRST_LAST_NO_INSTALL" :
                              "ORIGIN_TRANSFERRED_WITHOUT_MESSAGE NO_INSTALL");
    }
    return outcome;
}

static int handoff_receiver(const char *ctrl_path, int hold_descriptor) {
    struct sockaddr_un addr;
    socklen_t length;
    int listener = -1, control_fd = -1, received_fd = -1, result = 32;
    struct pollfd pending;
    char response = 0;
    if (!address_for(ctrl_path, &addr, &length)) return 31;
    listener = socket(AF_UNIX, SOCK_STREAM, 0);
    if (listener < 0) goto done;
    timeout_for(listener);
    if (bind(listener, (struct sockaddr *)(void *)&addr, length) != 0 ||
        chmod(ctrl_path, 0600) != 0 ||
        listen(listener, 1) != 0) goto done;
    puts("HANDOFF_RECEIVER_READY NONROOT AUTHORIZATION=DENIED");
    fflush(stdout);
    pending.fd = listener;
    pending.events = POLLIN;
    pending.revents = 0;
    if (poll(&pending, 1, 3000) != 1 ||
        !(pending.revents & POLLIN)) goto done;
    control_fd = accept(listener, NULL, NULL);
    if (control_fd < 0) goto done;
    timeout_for(control_fd);
    received_fd = receive_connected_fd(control_fd);
    if (received_fd < 0) goto done;
    timeout_for(received_fd);
    if (send(received_fd, "WRHELLO1", 8, 0) != 8 ||
        recv(received_fd, &response, 1, 0) != 1 ||
        response != 'R' ||
        send(control_fd, "K", 1, 0) != 1) goto done;
    /* Hold the transferred descriptor OPEN during A's third message:
       otherwise token changes could be caused by closing B's descriptor
       rather than by the process which actually wrote message 3. */
    if (hold_descriptor &&
        (recv(control_fd, &response, 1, 0) != 1 || response != 'D'))
        goto done;
    result = 0;
done:
    if (received_fd >= 0) (void)close(received_fd);
    if (control_fd >= 0) (void)close(control_fd);
    if (listener >= 0) (void)close(listener);
    (void)unlink(ctrl_path);
    if (result == 0) puts("HANDOFF_SENDER_COMPLETED NO_INSTALL");
    return result;
}


/* A -> B -> A on the SAME stream: sample the peer token immediately after
 * each WRHELLO1 read, before ACK, to distinguish per-write reassignment from
 * a one-time reassignment when SCM_RIGHTS transfers the descriptor.
 *
 * Every response is diagnostic-only. No identity grants permission.
 */
static int serve_three(const char *path, const char *expected_text) {
    struct sockaddr_un address;
    socklen_t length;
    unsigned char expected[20] = {0};
    int listener = -1, clientfd = -1, result = 8, i;
    struct pollfd pending;
    char incoming[8];
    const char *observations[3] = {
        "TRANSPORT_FAILED", "TRANSPORT_FAILED", "TRANSPORT_FAILED"
    };
    if (!parse_hex(expected_text, expected)) {
        puts("FINAL_INSTALL_AUTHORIZATION=DENIED");
        return 5;
    }
    if (!address_for(path, &address, &length)) return 6;
    listener = socket(AF_UNIX, SOCK_STREAM, 0);
    if (listener < 0) goto done;
    timeout_for(listener);
    if (bind(listener, (struct sockaddr *)(void *)&address, length) != 0 ||
        chmod(path, 0600) != 0 || listen(listener, 1) != 0) goto done;
    puts("READY NONROOT THREE_MESSAGES AUTHORIZATION=DENIED");
    fflush(stdout);
    pending.fd = listener;
    pending.events = POLLIN;
    pending.revents = 0;
    if (poll(&pending, 1, 3000) != 1 ||
        !(pending.revents & POLLIN)) goto done;
    clientfd = accept(listener, NULL, NULL);
    if (clientfd < 0) goto done;
    timeout_for(clientfd);
    for (i = 0; i < 3; ++i) {
        if (recv(clientfd, incoming, sizeof(incoming), MSG_WAITALL) != 8 ||
            memcmp(incoming, "WRHELLO1", 8) != 0) {
            observations[i] = "PROTOCOL_REJECTED";
            goto done;
        }
        observations[i] = classify_peer(clientfd, expected);
        if (send(clientfd, "R", 1, 0) != 1) goto done;
    }
    result = 0;
done:
    if (clientfd >= 0) (void)close(clientfd);
    if (listener >= 0) (void)close(listener);
    (void)unlink(path);
    for (i = 0; i < 3; ++i) {
        printf("RESULT STEP%d=%s AUTHORIZATION=DENIED\n",
               i + 1, observations[i]);
    }
    puts("FINAL_INSTALL_AUTHORIZATION=DENIED");
    return result;
}

int main(int argc, char **argv) {
    /* Neither client nor server can run as root. */
    if (geteuid() == 0) return 20;
    (void)signal(SIGPIPE, SIG_IGN);
    (void)umask(0077);
    if (argc == 3 && strcmp(argv[1], "client-once") == 0)
        return client(argv[2]);
    if (argc == 4 && strcmp(argv[1], "serve-once") == 0)
        return serve(argv[2], argv[3]);
    if (argc == 4 && strcmp(argv[1], "origin-pass") == 0)
        return handoff_origin(argv[2], argv[3], 0);
    if (argc == 4 && strcmp(argv[1], "origin-three") == 0)
        return handoff_origin(argv[2], argv[3], 1);
    if (argc == 4 && strcmp(argv[1], "serve-three") == 0)
        return serve_three(argv[2], argv[3]);
    if (argc == 3 && strcmp(argv[1], "receiver-once") == 0)
        return handoff_receiver(argv[2], 0);
    if (argc == 3 && strcmp(argv[1], "receiver-hold") == 0)
        return handoff_receiver(argv[2], 1);
    fputs("Usage: separate peer identity lab (no installation)\n", stderr);
    return 2;
}
