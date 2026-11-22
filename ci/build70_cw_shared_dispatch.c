/* Phase CW — host/native, nonprivileged CHECK_ONLY in-process coordinator.
 * This is NOT a launch daemon, an IPC server, or install permission.
 * It has NO network, filesystem, appinst, updater, or privileged calls.
 */
#include "build70_cw_shared_dispatch.h"
#include <pthread.h>
#include <stdlib.h>

struct WR_CW_Dispatcher {
    pthread_mutex_t lock;
    WR_CW_Gate gate;
};

WR_CW_Dispatcher *wr_cw_dispatch_new(void) {
    WR_CW_Dispatcher *dispatcher = calloc(1, sizeof(*dispatcher));
    if (!dispatcher) return NULL;
    if (pthread_mutex_init(&dispatcher->lock, NULL) != 0) {
        free(dispatcher);
        return NULL;
    }
    return dispatcher;
}

WR_CW_Decision wr_cw_dispatch_offer(WR_CW_Dispatcher *dispatcher,
                                   const uint8_t *packet, size_t length,
                                   uint64_t monotonic_ms) {
    WR_CW_Decision denied = {0};
    denied.status = WR_CW_REJECTED;
    if (!dispatcher) return denied;
    if (pthread_mutex_lock(&dispatcher->lock) != 0) return denied;
    WR_CW_Decision decision = wr_cw_offer(&dispatcher->gate, packet, length, monotonic_ms);
    if (pthread_mutex_unlock(&dispatcher->lock) != 0) {
        return denied; /* Fail closed on synchronization error. */
    }
    return decision;
}

void wr_cw_dispatch_free(WR_CW_Dispatcher *dispatcher) {
    if (!dispatcher) return;
    /* Caller must join all workers before freeing a dispatcher. */
    if (pthread_mutex_destroy(&dispatcher->lock) != 0) return;
    free(dispatcher);
}
