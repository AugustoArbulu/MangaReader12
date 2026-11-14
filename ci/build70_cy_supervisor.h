#ifndef WEBREADER_CY_SUPERVISOR_H
#define WEBREADER_CY_SUPERVISOR_H
/* Build70/CY: host-only check-only watchdog. NEVER install authority. */
#include "build70_cx_bounded_scheduler.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define WR_CY_TIMEOUT_MS UINT64_C(15000)
#define WR_CY_INITIAL_BACKOFF_MS UINT64_C(30000)
#define WR_CY_MAX_BACKOFF_MS UINT64_C(240000)

typedef enum {
    WR_CY_DENIED=0, WR_CY_STARTED=1, WR_CY_COALESCED=2,
    WR_CY_PENDING_FULL=3, WR_CY_COOLDOWN=4, WR_CY_COMPLETED=5,
    WR_CY_STOPPED=6, WR_CY_IDLE=7, WR_CY_STALE=8,
    WR_CY_TIMEOUT_CANCEL_REQUESTED=9, WR_CY_WAITING_WORKER=10,
    WR_CY_CANCEL_ACKNOWLEDGED=11, WR_CY_BACKOFF=12,
    WR_CY_FAILURE_RECORDED=13, WR_CY_CANCELLED_PENDING=14
} WR_CY_Status;

typedef struct WR_CY_Supervisor WR_CY_Supervisor;
typedef struct {
    WR_CY_Status status;
    uint64_t trusted_worker_ticket; /* ONLY within trusted worker; NEVER IPC */
    uint64_t retry_after_ms; /* relative interval, NOT wall time */
    uint8_t pending_count;
    uint8_t failure_streak;
    bool worker_may_still_be_running;
    bool cancel_requested;
    bool caller_authenticated;
    bool publisher_verified;
    bool ipa_bytes_authenticated;
    bool owner_consent_verified;
    bool installation_authorized;
    bool installation_performed;
} WR_CY_Receipt;
WR_CY_Supervisor *wr_cy_new(void);
WR_CY_Receipt wr_cy_offer(WR_CY_Supervisor *, const uint8_t *,
                         size_t, uint64_t trusted_monotonic_ms);
WR_CY_Receipt wr_cy_poll(WR_CY_Supervisor *, uint64_t trusted_monotonic_ms);
WR_CY_Receipt wr_cy_watchdog(WR_CY_Supervisor *, uint64_t trusted_monotonic_ms);
WR_CY_Receipt wr_cy_complete(WR_CY_Supervisor *, uint64_t trusted_worker_ticket,
                             bool success, uint64_t trusted_monotonic_ms);
WR_CY_Receipt wr_cy_ack_cancel(WR_CY_Supervisor *, uint64_t trusted_worker_ticket,
                               uint64_t trusted_monotonic_ms);
WR_CY_Receipt wr_cy_cancel_pending(WR_CY_Supervisor *, uint64_t trusted_monotonic_ms);
WR_CY_Receipt wr_cy_shutdown(WR_CY_Supervisor *);
/* MUST join all workers and watchers before free; there is NO forced kill. */
void wr_cy_free(WR_CY_Supervisor *);
#ifdef __cplusplus
}
#endif
#endif
