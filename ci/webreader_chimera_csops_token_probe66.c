/*
 * WebReader Build66 Phase E — non-root, ONE-SHOT audit-token-bound csops capability.
 *
 * Reports only whether a kernel-origin peer audit token could be retrieved
 * on a newly accepted AF_UNIX connection from a controlled child process.
 * It NEVER authenticates WebReader. No appinst, IPA, network download, helper,
 * listener after exit, launchd, installation, code-signature check or root.
 *
 * Security-framework probes use dlsym only (presence, not invocation). They
 * DO NOT prove that an API is usable or supported on iOS 12.5.8/Chimera.
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
#include <sys/wait.h>
#include <sys/time.h>
#include <unistd.h>

#ifndef LOCAL_PEERTOKEN
#define WR_LOCAL_PEERTOKEN 0x006
#else
#define WR_LOCAL_PEERTOKEN LOCAL_PEERTOKEN
#endif

#define WR_RESULT_AUTHZ "AUTHORIZATION=DENIED"
#define WR_CS_OPS_CDHASH 5
typedef int (*wr_csops_audittoken_t)(
    pid_t, unsigned int, void *, size_t, audit_token_t *
);
/* All results are observations about a controlled test child, not app ID.
 * Even MUTATED_TOKEN_REJECTED is not sufficient to authenticate WebReader.
 */
static void inspect_csops_binding(const audit_token_t *original,
                                  char *status, size_t status_len) {
    wr_csops_audittoken_t method =
        (wr_csops_audittoken_t)dlsym(RTLD_DEFAULT, "csops_audittoken");
    uint8_t cdhash[20] = {0};
    /* Host-only reference comparison never ships in the iOS diagnostic. */
#if defined(WEBREADER_HOST_CDHASH_REF)
    uint8_t kernel_hash[20] = {0};
    const char *expected_hex;
    size_t index;
#endif
    audit_token_t corrupted = *original;
    int good, bad;
    if (!method) {
        (void)snprintf(status, status_len, "SYMBOL_MISSING");
        return;
    }
    /* XNU audit_token_t field positions are observed only, never emitted. */
    if (original->val[5] == 0 || original->val[7] == 0) {
        (void)snprintf(status, status_len, "TOKEN_FIELDS_UNAVAILABLE");
        return;
    }
    good = method((pid_t)original->val[5], WR_CS_OPS_CDHASH,
                  cdhash, sizeof(cdhash), (audit_token_t *)(void *)original);
    if (good != 0) {
        (void)snprintf(status, status_len, "CALL_DENIED");
        return;
    }
#if defined(WEBREADER_HOST_CDHASH_REF)
    memcpy(kernel_hash, cdhash, sizeof(kernel_hash));
#endif
    corrupted.val[7] ^= 1u; /* mutate pidversion; do not execute mutated token */
    bad = method((pid_t)original->val[5], WR_CS_OPS_CDHASH,
                 cdhash, sizeof(cdhash), &corrupted);
    if (bad == 0) {
        (void)snprintf(status, status_len, "MUTATION_ACCEPTED_UNSAFE");
        return;
    }
    /* Wrong PID is this controlled parent process, never an unrelated app. */
    bad = method(getpid(), WR_CS_OPS_CDHASH, cdhash, sizeof(cdhash),
                 (audit_token_t *)(void *)original);
    if (bad == 0) {
        (void)snprintf(status, status_len, "CROSS_PID_ACCEPTED_UNSAFE");
        return;
    }
#if defined(WEBREADER_HOST_CDHASH_REF)
    /* Test harness computes the reference from THIS OWN signed executable.
     * This is not an identity policy. An env var is attacker-controlled.
     * The iOS build never compiles this block.
     */
    expected_hex = getenv("WR66_HOST_EXPECTED_CDHASH");
    if (!expected_hex || strlen(expected_hex) != 40) {
        (void)snprintf(status, status_len, "HOST_REFERENCE_ABSENT");
        return;
    }
    for (index = 0; index < 20; ++index) {
        unsigned int octet = 0;
        char pair[3] = {expected_hex[index * 2], expected_hex[index * 2 + 1], 0};
        if (sscanf(pair, "%2x", &octet) != 1) {
            (void)snprintf(status, status_len, "HOST_REFERENCE_INVALID");
            return;
        }
        if (kernel_hash[index] != (uint8_t)octet) {
            (void)snprintf(status, status_len, "HOST_CDHASH_MISMATCH");
            return;
        }
    }
    (void)snprintf(status, status_len, "HOST_CDHASH_MATCH");
#else
    (void)snprintf(status, status_len, "MUTATION_REJECTED");
#endif
}
static void set_timeout(int fd) {
    struct timeval duration = {3, 0};
    (void)setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &duration, sizeof(duration));
    (void)setsockopt(fd, SOL_SOCKET, SO_SNDTIMEO, &duration, sizeof(duration));
}

static int child_connect(const struct sockaddr_un *address, socklen_t length) {
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    char ping = 'Q', response = 0;
    if (fd < 0) return 61;
    set_timeout(fd);
    if (connect(fd, (const struct sockaddr *)(const void *)address, length) != 0) {
        (void)close(fd); return 62;
    }
    if (send(fd, &ping, 1, 0) != 1 || recv(fd, &response, 1, 0) != 1 ||
        response != 'R') {
        (void)close(fd); return 63;
    }
    (void)close(fd);
    return 0;
}

static int token_nonzero(const audit_token_t *token) {
    const unsigned char *bytes = (const unsigned char *)(const void *)token;
    size_t index;
    for (index = 0; index < sizeof(*token); index++) {
        if (bytes[index] != 0) return 1;
    }
    return 0;
}

/* No PID, UID, token bytes or personal paths are printed or stored. */
static int probe_local_token(char *binding, size_t binding_size) {
    char directory[] = "/tmp/wr-audit66-XXXXXX";
    struct sockaddr_un addr;
    socklen_t addrlen;
    int listener = -1, client = -1, result = 0, child_result = 0;
    pid_t child = -1;
    int wait_status = 0;
    struct pollfd pending;
    audit_token_t token;
    socklen_t tokenlen;
    char recv_byte = 0, response = 'R';
    int rc = -1;
    if (!mkdtemp(directory)) {
        puts("PROBE UNIX_PEERTOKEN=TRANSPORT_FAILED AUTHORIZATION=DENIED");
        return 10;
    }
    memset(&addr, 0, sizeof(addr));
    addr.sun_family = AF_UNIX;
    if (snprintf(addr.sun_path, sizeof(addr.sun_path), "%s/s", directory) < 0 ||
        strlen(addr.sun_path) >= sizeof(addr.sun_path) - 1) {
        result = 11; goto done;
    }
    addrlen = (socklen_t)(offsetof(struct sockaddr_un, sun_path) +
                          strlen(addr.sun_path) + 1);
    addr.sun_len = (uint8_t)addrlen;
    listener = socket(AF_UNIX, SOCK_STREAM, 0);
    if (listener < 0) { result = 12; goto done; }
    set_timeout(listener);
    if (bind(listener, (struct sockaddr *)(void *)&addr, addrlen) != 0 ||
        listen(listener, 1) != 0) { result = 13; goto done; }
    child = fork();
    if (child < 0) { result = 14; goto done; }
    if (child == 0) {
        (void)close(listener);
        child_result = child_connect(&addr, addrlen);
        _exit(child_result);
    }
    pending.fd = listener;
    pending.events = POLLIN;
    pending.revents = 0;
    if (poll(&pending, 1, 3000) <= 0 || !(pending.revents & POLLIN)) {
        result = 15; goto done;
    }
    client = accept(listener, NULL, NULL);
    if (client < 0) { result = 16; goto done; }
    set_timeout(client);
    if (recv(client, &recv_byte, 1, 0) != 1 || recv_byte != 'Q') {
        result = 17; goto done;
    }
    memset(&token, 0, sizeof(token));
    tokenlen = (socklen_t)sizeof(token);
    rc = getsockopt(client, SOL_LOCAL, WR_LOCAL_PEERTOKEN, &token, &tokenlen);
    if (rc == 0 && tokenlen == sizeof(token)) {
        printf("PROBE UNIX_PEERTOKEN=%s " WR_RESULT_AUTHZ "\n",
               token_nonzero(&token) ? "NONZERO" : "ZERO");
        if (token_nonzero(&token)) {
            inspect_csops_binding(&token, binding, binding_size);
        }
    } else {
        puts("PROBE UNIX_PEERTOKEN=UNAVAILABLE AUTHORIZATION=DENIED");
    }
    if (send(client, &response, 1, 0) != 1) result = 18;
done:
    if (client >= 0) (void)close(client);
    if (listener >= 0) (void)close(listener);
    if (child > 0) {
        if (result != 0) (void)kill(child, SIGTERM);
        if (waitpid(child, &wait_status, 0) != child ||
            !WIFEXITED(wait_status) || WEXITSTATUS(wait_status) != 0)
            result = result ? result : 19;
    }
    (void)unlink(addr.sun_path);
    (void)rmdir(directory);
    if (result) {
        puts("PROBE UNIX_PEERTOKEN=TRANSPORT_FAILED AUTHORIZATION=DENIED");
    }
    /* The probe intentionally reports *availability*, not process identity. */
    return result;
}

static void probe_symbol(void *handle, const char *symbol, const char *label) {
    const char *status = "FRAMEWORK_UNAVAILABLE";
    if (handle != NULL) {
        status = dlsym(handle, symbol) ? "PRESENT" : "MISSING";
    }
    printf("PROBE SECURITY_%s=%s " WR_RESULT_AUTHZ "\n", label, status);
}

int main(int argc, char **argv) {
    void *security;
    int token_status;
    char binding_status[48] = "NOT_TESTED";
    if (argc != 2 || strcmp(argv[1], "selftest") != 0) {
        fputs("Usage: webreader-csopsprobe66 selftest\n", stderr);
        return 2;
    }
    if (geteuid() == 0) {
        fputs("REFUSE_ROOT: nonprivileged read-only diagnostic\n", stderr);
        return 3;
    }
    (void)signal(SIGPIPE, SIG_IGN);
    (void)umask(0077);
    puts("WEBREADER_BUILD66_CSOPS_AUDITTOKEN_CAPABILITY: non-root, read-only");
    token_status = probe_local_token(binding_status, sizeof(binding_status));
    printf("PROBE CSOPS_TOKEN_BINDING=%s " WR_RESULT_AUTHZ "\n",
           binding_status);
    security = dlopen("/System/Library/Frameworks/Security.framework/Security",
                      RTLD_LAZY | RTLD_LOCAL);
    probe_symbol(security, "SecCodeCreateWithAuditToken",
                 "SecCodeCreateWithAuditToken");
    probe_symbol(security, "SecCodeCopyGuestWithAttributes",
                 "SecCodeCopyGuestWithAttributes");
    probe_symbol(security, "SecCodeCreateWithPID",
                 "SecCodeCreateWithPID");
    if (security) (void)dlclose(security);
    puts("FINAL_INSTALL_AUTHORIZATION=DENIED");
    return token_status ? 4 : 0;
}
