/*
 * Host-only CLI harness for exactly the same C transport compiled into
 * the independent UIKit iOS app. Never part of the device IPA.
 */
#if defined(__APPLE__)
#include <TargetConditionals.h>
#if TARGET_OS_IPHONE
#error "Host harness must not be built or bundled for iOS"
#endif
#endif
#ifndef WR_DA_HOST_TEST
#error "Host harness requires WR_DA_HOST_TEST"
#endif
#include "cx_client.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main(int argc, char **argv) {
    char *end = NULL;
    unsigned long raw;
    WR_DA_Result status;
    if (argc != 2 || argv[1][0] == '\0') return 90;
    raw = strtoul(argv[1], &end, 10);
    if (*end != '\0' || raw == 0 || raw > 65535) return 90;
    status = wr_da_host_probe((uint16_t)raw);
    printf("WR_DA_HOST_RESULT=%d\n", (int)status);
    return 0;
}
