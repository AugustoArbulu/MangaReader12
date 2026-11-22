/*
 * WebReader Build70 — Phase DE: READ-ONLY self-identity diagnostic.
 *
 * Compiles to a minimal iOS12 ARM64 command-line *candidate*.
 * It does not test another process, identify an IPC peer, obtain
 * entitlements, manipulate files, connect to GitHub or install anything.
 * Role is a compile-time LABEL, not a signed or attested identity.
 *
 * NO argv paths or options; NO file writes, network, spawn, fork, sockets,
 * appinst, installation APIs or interactions with the WebReader library.
 */
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#include <mach-o/dyld.h>
#else
#define _POSIX_C_SOURCE 200809L
#endif

#include <stdio.h>
#include <stdint.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/utsname.h>
#include <unistd.h>

#if defined(WR_DE_MOBILE_ROLE) && defined(WR_DE_HELPER_ROLE)
#error "A DE probe may have only one synthetic role label"
#endif
#if defined(WR_DE_MOBILE_ROLE)
#define WR_DE_ROLE "MOBILE_CANDIDATE"
#elif defined(WR_DE_HELPER_ROLE)
#define WR_DE_ROLE "HELPER_CANDIDATE"
#else
#define WR_DE_ROLE "UNLABELED"
#endif

static void emit_binary_metadata(void) {
    char path[4096];
    int have_path = 0;
#if defined(__APPLE__)
    uint32_t size = (uint32_t)sizeof(path);
    if (_NSGetExecutablePath(path, &size) == 0) have_path = 1;
#elif defined(__linux__)
    ssize_t n = readlink("/proc/self/exe", path, sizeof(path)-1u);
    if (n > 0 && (size_t)n < sizeof(path)) {
        path[n] = '\0';
        have_path = 1;
    }
#endif
    struct stat binary;
    if (have_path && stat(path, &binary) == 0 && S_ISREG(binary.st_mode)) {
        printf("DE_SELF_BINARY_METADATA=AVAILABLE\n");
        printf("DE_SELF_BINARY_OWNER_UID=%lu\n", (unsigned long)binary.st_uid);
        printf("DE_SELF_BINARY_MODE=%04o\n", (unsigned int)(binary.st_mode & 07777u));
    } else {
        puts("DE_SELF_BINARY_METADATA=UNAVAILABLE");
        puts("DE_SELF_BINARY_OWNER_UID=UNAVAILABLE");
        puts("DE_SELF_BINARY_MODE=UNAVAILABLE");
    }
    /* Deliberately do NOT print an executable path or any file contents. */
}

static void emit_supplementary_groups(void) {
    gid_t groups[64];
    int count = getgroups(64, groups);
    if (count < 0) {
        puts("DE_SELF_GROUPS=UNAVAILABLE");
        return;
    }
    printf("DE_SELF_GROUPS=");
    for (int i = 0; i < count; ++i) {
        if (i) putchar(',');
        printf("%lu", (unsigned long)groups[i]);
    }
    putchar('\n');
}

int main(int argc, char **argv) {
    (void)argv;
    if (argc != 1) return 2; /* No user supplied options, paths or commands. */
    struct utsname u;
    if (uname(&u) != 0) return 3;

    puts("DE_SCHEMA=1");
    puts("DE_ROLE=" WR_DE_ROLE);
    printf("DE_SELF_UID=%lu\n", (unsigned long)getuid());
    printf("DE_SELF_EUID=%lu\n", (unsigned long)geteuid());
    printf("DE_SELF_GID=%lu\n", (unsigned long)getgid());
    printf("DE_SELF_EGID=%lu\n", (unsigned long)getegid());
    printf("DE_SELF_PID=%lu\n", (unsigned long)getpid());
    printf("DE_SELF_PPID=%lu\n", (unsigned long)getppid());
    emit_supplementary_groups();
    emit_binary_metadata();
    printf("DE_KERNEL_FAMILY=%s\n", u.sysname);
    puts("DE_PROCESS_IDENTITY_SCOPE=SELF_ONLY");
    puts("DE_SELF_BINARY_SIGNING_VERIFIED=NO");
    puts("DE_IPC_PEER_AUTHENTICATED=NO");
    puts("DE_IOS12_HELPER_ISOLATION_VERIFIED=NO");
    puts("DE_APP_WRITE_DENIAL_VERIFIED=NO");
    puts("DE_OWNER_INSTALL_CONSENT_VERIFIED=NO");
    puts("DE_INSTALLATION_AUTHORIZED=NO");
    puts("DE_INSTALLATION_ATTEMPTED=NO");
    return 0;
}
