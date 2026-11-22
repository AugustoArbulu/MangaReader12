#ifndef WEBREADER_DA_CRASH_QUARANTINE_H
#define WEBREADER_DA_CRASH_QUARANTINE_H
/*
 * Build70 / DA — one-shot, host-tested crash evidence journal.
 * This is NOT an update service, nor authenticated IPC, nor an installer.
 * The directory path comes from a trusted HOST HARNESS, never an app packet.
 * The marker causes permanent quarantine after any restart; there is no
 * in-product override, deletion or reconciliation API.
 */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define WR_DA_FRAME_BYTES 7u

typedef enum {
    WR_DA_DENIED = 0,
    WR_DA_READY = 1,
    WR_DA_MARKED = 2,
    WR_DA_QUARANTINED = 3,
    WR_DA_BUSY = 4
} WR_DA_Status;

typedef struct WR_DA_Journal WR_DA_Journal;

typedef struct {
    WR_DA_Status status;
    bool crash_evidence_is_present;
    bool caller_authenticated;
    bool publisher_verified;
    bool editor_pin_provisioned;
    bool ipad_uid_isolation_proven;
    bool protected_against_same_uid_tamper;
    bool can_reconcile_pending_install;
    bool installation_authorized;
    bool installation_performed;
} WR_DA_Receipt;

/* Requires existing host-owned 0700 directory. Acquires nonblocking flock.
 * Invalid/unknown pending-marker file -> quarantine/fail closed.
 * This does not validate parent directory components or iOS helper entitlements.
 */
WR_DA_Journal *wr_da_open(const char *pretrusted_host_directory,
                          WR_DA_Receipt *observation);
/* Accepts only WRCHK2 newline and, on first valid notice, atomically creates
 * a pending marker and fsyncs marker + directory BEFORE returning MARKED.
 * After a marker exists, no further notice is ever accepted by this module.
 */
WR_DA_Receipt wr_da_offer(WR_DA_Journal *, const uint8_t *, size_t);
WR_DA_Receipt wr_da_observe(WR_DA_Journal *);
void wr_da_close(WR_DA_Journal *);

#ifdef __cplusplus
}
#endif
#endif
