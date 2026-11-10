#ifndef WEBREADER_CW_CHECKONLY_CORE_H
#define WEBREADER_CW_CHECKONLY_CORE_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define WR_CW_FRAME_BYTES 7u
#define WR_CW_MIN_INTERVAL_MS UINT64_C(60000)
typedef enum {
    WR_CW_REJECTED = 0,
    WR_CW_CHECK_NOTICE_ACCEPTED = 1,
    WR_CW_RATE_LIMITED = 2
} WR_CW_Status;
typedef struct {
    bool seen;
    uint64_t last_accepted_ms;
} WR_CW_Gate;
typedef struct {
    WR_CW_Status status;
    bool caller_authenticated;
    bool publisher_verified;
    bool artifact_selected_by_client;
    bool installer_authorized;
    bool installation_performed;
} WR_CW_Decision;
WR_CW_Decision wr_cw_offer(WR_CW_Gate *gate, const uint8_t *packet,
                            size_t length, uint64_t monotonic_ms);
#ifdef __cplusplus
}
#endif
#endif
