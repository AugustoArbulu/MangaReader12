#ifndef WEBREADER_DC_CUSTODY_LINEAGE_H
#define WEBREADER_DC_CUSTODY_LINEAGE_H
/*
 * Build70/DC — READ-ONLY host-only anchored directory custody inspection.
 *
 * The caller supplies a PRETRUSTED directory and a HYPOTHETICAL client UID.
 * This function neither authenticates the caller nor independently proves
 * the anchor's parents, iOS12 sandbox, entitlements, access policy or install
 * authority. DO NOT attach this function to an untrusted IPC endpoint.
 */
#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif
#define WR_DC_PRIVATE "wr-dc-private"
#define WR_DC_STATE "state"
#define WR_DC_LOCK "wr-da-review.lock"
#define WR_DC_PENDING "wr-da-check.pending"

typedef enum {
    WR_DC_REJECTED=0,
    WR_DC_HOST_METADATA_REVIEWED=1,
    WR_DC_QUARANTINED=2
} WR_DC_Status;

typedef struct {
    WR_DC_Status status;
    bool anchored_descendants_privately_owned_on_host;
    bool lock_file_privately_owned_on_host;
    bool marker_present;
    bool hypothetical_client_uid_differs_from_helper;
    /* The following cannot become true from a host filesystem stat: */
    bool anchor_ancestry_independently_attested;
    bool real_ios12_process_identity_attested;
    bool app_write_access_denied_on_ios12;
    bool helper_entitlements_checked_on_ios12;
    bool immune_to_root_or_same_uid_mutation;
    bool protected_from_journal_rollback;
    bool publisher_identity_verified;
    bool owner_install_consent_verified;
    bool installation_authorized;
    bool installation_performed;
} WR_DC_Receipt;

/* The base must be an existing, owner-private ABSOLUTE host folder.
 * Inspect fixed base/wr-dc-private/state/wr-da-review.lock.
 * The marker name must be absent for HOST_METADATA_REVIEWED; any object
 * at that name returns QUARANTINED, even a malformed or symlink marker.
 * Nothing is created/edited/unlinked. The process EUID comes from kernel;
 * asserted_client_uid is UNAUTHENTICATED fixture data, not IPC identity.
 */
WR_DC_Receipt wr_dc_inspect_host_only(const char *pretrusted_base,
                                     uint32_t asserted_client_uid);
#ifdef __cplusplus
}
#endif
#endif
