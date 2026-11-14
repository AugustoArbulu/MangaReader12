#ifndef WEBREADER_DD_FULL_ANCESTRY_H
#define WEBREADER_DD_FULL_ANCESTRY_H
/*
 * Build70/DD — HOST-ONLY, read-only POSIX ancestry observation.
 * config_base is supplied by a trusted TEST HARNESS, NEVER by an IPC client.
 * claimed_client_uid is unauthenticated test input; it is NOT a peer credential.
 * The returned receipt can NEVER authorize downloads or installation.
 */
#include <stdbool.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define WR_DD_PRIVATE "wr-dd-private"
#define WR_DD_STATE "state"
#define WR_DD_LOCK "wr-da-review.lock"
#define WR_DD_PENDING "wr-da-check.pending"
typedef enum {
    WR_DD_REJECTED = 0,
    WR_DD_HOST_METADATA_REVIEWED = 1,
    WR_DD_QUARANTINED = 2
} WR_DD_Status;
typedef struct {
    WR_DD_Status status;
    bool complete_host_ancestor_chain_observed;
    bool host_ancestors_without_group_or_other_write;
    bool host_descendant_dirs_owner_0700;
    bool host_lock_owner_0600_singlelink;
    bool marker_present;
    bool claimed_client_uid_differs; /* claim is not authenticated */
    bool ios12_client_identity_proven;
    bool ios12_helper_identity_proven;
    bool ios12_app_write_access_denied;
    bool independently_protected_storage_attested;
    bool powerloss_or_rollback_safe;
    bool post_review_immutability_proven;
    bool editor_signature_trusted;
    bool owner_consent_verified;
    bool installation_authorized;
    bool installation_performed;
} WR_DD_Receipt;
/* Walk ROOT "/" -> every config_base ancestor, then fixed private/state/lock.
 * O_NOFOLLOW, fstat vs fstatat match at each hop. The system is not frozen
 * after the function returns; a writer/root can change the paths later.
 * No files created, altered, locked, removed, installed or downloaded.
 */
WR_DD_Receipt wr_dd_inspect_host_ancestors(const char *config_base,
                                          uint32_t claimed_client_uid);
#ifdef __cplusplus
}
#endif
#endif
