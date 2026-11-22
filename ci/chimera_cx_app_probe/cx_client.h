#ifndef WEBREADER_DA_CX_CLIENT_H
#define WEBREADER_DA_CX_CLIENT_H
#include <stdint.h>
typedef enum {
    WR_DA_UNAVAILABLE = 0,
    WR_DA_NOTE = 1,
    WR_DA_RATE = 2,
    WR_DA_DENY = 3,
    WR_DA_BAD_RESPONSE = 4,
    WR_DA_TRANSPORT_ERROR = 5
} WR_DA_Result;
/* Only check-only notice, never a real release check or install permission. */
WR_DA_Result wr_da_probe(void);
#if defined(WR_DA_HOST_TEST)
/* Host QA only; builds for iPhone expressly reject WR_DA_HOST_TEST. */
WR_DA_Result wr_da_host_probe(uint16_t port);
#endif
#endif
