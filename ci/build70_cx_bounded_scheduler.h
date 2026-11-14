#ifndef WEBREADER_CX_BOUNDED_SCHEDULER_H
#define WEBREADER_CX_BOUNDED_SCHEDULER_H
/* Build70/CX: synthetic, process-local, check-only scheduler. NOT an IPC service. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define WR_CX_FRAME_BYTES 7u
#define WR_CX_MIN_START_INTERVAL_MS UINT64_C(60000)
#define WR_CX_MAX_PENDING 1u
typedef enum {
    WR_CX_DENIED = 0,
    WR_CX_STARTED = 1,
    WR_CX_COALESCED = 2,
    WR_CX_ALREADY_PENDING = 3,
    WR_CX_RATE_LIMITED = 4,
    WR_CX_FINISHED = 5,
    WR_CX_CANCELLED = 6,
    WR_CX_IDLE = 7,
    WR_CX_STALE = 8,
    WR_CX_STOPPED = 9,
    WR_CX_BUSY = 10
} WR_CX_Status;
typedef struct WR_CX_Scheduler WR_CX_Scheduler;
typedef struct {
    WR_CX_Status status;
    uint64_t local_worker_ticket; /* trusted harness ONLY; never return to IPC clients */
    uint8_t pending_count;        /* always 0 or 1 */
    bool check_inflight;
    bool caller_authenticated;
    bool publisher_verified;
    bool client_can_choose_artifact;
    bool immutable_installer_input_proven;
    bool owner_consent_verified;
    bool installation_authorized;
    bool installation_performed;
} WR_CX_Receipt;
WR_CX_Scheduler *wr_cx_new(void);
WR_CX_Receipt wr_cx_offer(WR_CX_Scheduler *, const uint8_t *frame,
                          size_t frame_len, uint64_t trusted_monotonic_ms);
WR_CX_Receipt wr_cx_poll(WR_CX_Scheduler *, uint64_t trusted_monotonic_ms);
WR_CX_Receipt wr_cx_finish(WR_CX_Scheduler *, uint64_t local_worker_ticket,
                           uint64_t trusted_monotonic_ms);
WR_CX_Receipt wr_cx_cancel_pending(WR_CX_Scheduler *, uint64_t trusted_monotonic_ms);
WR_CX_Receipt wr_cx_cancel_active(WR_CX_Scheduler *, uint64_t local_worker_ticket,
                                  uint64_t trusted_monotonic_ms);
WR_CX_Receipt wr_cx_shutdown(WR_CX_Scheduler *);
/* The host harness MUST join all threads and finish all work before destroy.
 * Shutdown invalidates tickets but cannot abort an already running worker.
 */
void wr_cx_free(WR_CX_Scheduler *);
#ifdef __cplusplus
}
#endif
#endif
