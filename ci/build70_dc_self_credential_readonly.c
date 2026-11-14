/*
 * WebReader Build70 / DC — read-only SELF credential diagnostic candidate.
 *
 * It does not establish the identity of IPC peers, the app, the helper,
 * an Apple installer process, nor any sandbox / entitlement permission.
 * No file path, user input, IPC, network, privileged calls or installation.
 * Cross-compilation is not execution on an iOS12 device.
 */
#include <stdio.h>
#include <sys/types.h>
#include <unistd.h>

int main(void) {
    printf("DC_SELF_REAL_UID=%lu\n", (unsigned long)getuid());
    printf("DC_SELF_EFFECTIVE_UID=%lu\n", (unsigned long)geteuid());
    printf("DC_SELF_REAL_GID=%lu\n", (unsigned long)getgid());
    printf("DC_SELF_EFFECTIVE_GID=%lu\n", (unsigned long)getegid());
    puts("DC_IDENTITY_SCOPE=SELF_PROCESS_ONLY");
    puts("DC_IPC_PEER_AUTHENTICATED=NO");
    puts("DC_IOS12_HELPER_ISOLATION_PROVEN=NO");
    puts("DC_INSTALLATION_AUTHORIZED=NO");
    puts("DC_INSTALLATION_ATTEMPTED=NO");
    return 0;
}
