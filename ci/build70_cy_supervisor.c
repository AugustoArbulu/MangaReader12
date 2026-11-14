/* Build70/CY: non-privileged *supervision policy only*.
 * Timeout requests cooperative worker cancellation; it NEVER assumes the
 * worker stopped. No replacement work runs until trusted worker ACK.
 * One object per protected supervisor is REQUIRED, but not proven here.
 * No IPC, launchd, network, files, appinst, IPA, publisher key or installer.
 */
#include "build70_cy_supervisor.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>

struct WR_CY_Supervisor {
    pthread_mutex_t lock;
    WR_CX_Scheduler *queue;
    bool stopped, clock_seen, active, cancel_requested, backoff_seen;
    uint64_t last_clock, active_since, active_ticket, failure_since, backoff_ms;
    uint8_t failures;
    uint8_t pending_count;
};

static WR_CY_Receipt receipt(WR_CY_Supervisor *s, WR_CY_Status status) {
    WR_CY_Receipt r = {0}; /* all authority fields remain false */
    r.status = status;
    if (s) {
        r.pending_count = s->pending_count;
        r.trusted_worker_ticket = s->active ? s->active_ticket : 0;
        r.worker_may_still_be_running = s->active;
        r.cancel_requested = s->cancel_requested;
        r.failure_streak = s->failures;
        r.retry_after_ms = s->backoff_ms;
    }
    return r;
}
static WR_CY_Receipt snapshot(WR_CY_Supervisor *s, WR_CY_Status status,
                               uint8_t pending) {
    s->pending_count = pending;
    WR_CY_Receipt r = receipt(s, status);
    return r;
}
static bool valid_clock(WR_CY_Supervisor *s, uint64_t now) {
    if (s->clock_seen && now < s->last_clock) return false;
    s->last_clock = now;
    s->clock_seen = true;
    return true;
}
static bool valid_frame(const uint8_t *packet, size_t n) {
    static const uint8_t exact[WR_CX_FRAME_BYTES] =
        {'W','R','C','H','K','2','\n'};
    return packet && n == sizeof(exact) &&
           memcmp(packet, exact, sizeof(exact)) == 0;
}
static bool overdue(WR_CY_Supervisor *s, uint64_t now) {
    return s->active && now >= s->active_since &&
           now - s->active_since >= WR_CY_TIMEOUT_MS;
}
static bool backed_off(WR_CY_Supervisor *s, uint64_t now) {
    return s->backoff_seen &&
        (now < s->failure_since ||
         now - s->failure_since < s->backoff_ms);
}
static void record_failure(WR_CY_Supervisor *s, uint64_t now) {
    if (s->failures < 4u) s->failures++;
    s->backoff_ms = WR_CY_INITIAL_BACKOFF_MS << (s->failures - 1u);
    s->backoff_seen = true;
    s->failure_since = now;
}
static WR_CY_Status translate(WR_CX_Status status) {
    switch (status) {
        case WR_CX_STARTED: return WR_CY_STARTED;
        case WR_CX_COALESCED: return WR_CY_COALESCED;
        case WR_CX_ALREADY_PENDING: return WR_CY_PENDING_FULL;
        case WR_CX_RATE_LIMITED: return WR_CY_COOLDOWN;
        case WR_CX_IDLE: return WR_CY_IDLE;
        case WR_CX_CANCELLED: return WR_CY_CANCELLED_PENDING;
        case WR_CX_STOPPED: return WR_CY_STOPPED;
        case WR_CX_STALE: return WR_CY_STALE;
        case WR_CX_BUSY: return WR_CY_WAITING_WORKER;
        default: return WR_CY_DENIED;
    }
}
static WR_CY_Receipt from_cx(WR_CY_Supervisor *s, WR_CX_Receipt q) {
    s->pending_count = q.pending_count;
    if (q.status == WR_CX_STARTED) {
        s->active = true;
        s->active_ticket = q.local_worker_ticket;
        s->active_since = s->last_clock;
        s->cancel_requested = false;
    }
    return snapshot(s, translate(q.status), q.pending_count);
}
WR_CY_Supervisor *wr_cy_new(void) {
    WR_CY_Supervisor *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    if (pthread_mutex_init(&s->lock, NULL) != 0) { free(s); return NULL; }
    s->queue = wr_cx_new();
    if (!s->queue) {
        pthread_mutex_destroy(&s->lock);
        free(s);
        return NULL;
    }
    return s;
}
WR_CY_Receipt wr_cy_offer(WR_CY_Supervisor *s, const uint8_t *frame,
                          size_t length, uint64_t now) {
    if (!s || !valid_frame(frame, length)) return receipt(NULL, WR_CY_DENIED);
    if (pthread_mutex_lock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    WR_CY_Receipt r;
    if (s->stopped) r = receipt(s, WR_CY_STOPPED);
    else if (!valid_clock(s, now)) r = receipt(s, WR_CY_STALE);
    else if (overdue(s, now)) {
        s->cancel_requested = true;
        r = receipt(s, WR_CY_TIMEOUT_CANCEL_REQUESTED);
    }
    else if (s->cancel_requested) r = receipt(s, WR_CY_WAITING_WORKER);
    else if (backed_off(s, now)) r = receipt(s, WR_CY_BACKOFF);
    else r = from_cx(s, wr_cx_offer(s->queue, frame, length, now));
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    return r;
}
WR_CY_Receipt wr_cy_poll(WR_CY_Supervisor *s, uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    WR_CY_Receipt r;
    if (s->stopped) r = receipt(s, WR_CY_STOPPED);
    else if (!valid_clock(s, now)) r = receipt(s, WR_CY_STALE);
    else if (overdue(s, now)) {
        s->cancel_requested = true;
        r = receipt(s, WR_CY_TIMEOUT_CANCEL_REQUESTED);
    }
    else if (s->cancel_requested || s->active) r = receipt(s, WR_CY_WAITING_WORKER);
    else if (backed_off(s, now)) r = receipt(s, WR_CY_BACKOFF);
    else r = from_cx(s, wr_cx_poll(s->queue, now));
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    return r;
}
WR_CY_Receipt wr_cy_watchdog(WR_CY_Supervisor *s, uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    WR_CY_Receipt r;
    if (s->stopped) r = receipt(s, WR_CY_STOPPED);
    else if (!valid_clock(s, now)) r = receipt(s, WR_CY_STALE);
    else if (!s->active) r = receipt(s, WR_CY_IDLE);
    else if (s->cancel_requested) r = receipt(s, WR_CY_WAITING_WORKER);
    else if (overdue(s, now)) {
        s->cancel_requested = true;
        r = receipt(s, WR_CY_TIMEOUT_CANCEL_REQUESTED);
    } else r = receipt(s, WR_CY_WAITING_WORKER);
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    return r;
}
WR_CY_Receipt wr_cy_complete(WR_CY_Supervisor *s, uint64_t ticket,
                             bool success, uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    WR_CY_Receipt r;
    if (s->stopped) r = receipt(s, WR_CY_STOPPED);
    else if (!valid_clock(s, now)) r = receipt(s, WR_CY_STALE);
    else if (!s->active || !ticket || ticket != s->active_ticket)
        r = receipt(s, WR_CY_STALE);
    else if (s->cancel_requested ||
             overdue(s, now)) {
        s->cancel_requested = true;
        r = receipt(s, WR_CY_TIMEOUT_CANCEL_REQUESTED);
    } else {
        WR_CX_Receipt q = wr_cx_finish(s->queue, ticket, now);
        if (q.status != WR_CX_FINISHED) r = receipt(s, WR_CY_DENIED);
        else {
            s->active = false;
            s->active_ticket = 0;
            if (success) {
                s->failures = 0;
                s->backoff_seen = false;
                s->backoff_ms = 0;
                r = snapshot(s, WR_CY_COMPLETED, q.pending_count);
            } else {
                (void)wr_cx_cancel_pending(s->queue, now);
                s->pending_count = 0;
                record_failure(s, now);
                r = receipt(s, WR_CY_FAILURE_RECORDED);
            }
        }
    }
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    return r;
}
WR_CY_Receipt wr_cy_ack_cancel(WR_CY_Supervisor *s, uint64_t ticket,
                               uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    WR_CY_Receipt r;
    if (s->stopped) r = receipt(s, WR_CY_STOPPED);
    else if (!valid_clock(s, now)) r = receipt(s, WR_CY_STALE);
    else if (!s->active || !s->cancel_requested || !ticket ||
             ticket != s->active_ticket) r = receipt(s, WR_CY_STALE);
    else {
        WR_CX_Receipt q = wr_cx_cancel_active(s->queue, ticket, now);
        if (q.status != WR_CX_CANCELLED) r = receipt(s, WR_CY_DENIED);
        else {
            s->active = false;
            s->active_ticket = 0;
            s->cancel_requested = false;
            s->pending_count = 0;
            record_failure(s, now);
            r = receipt(s, WR_CY_CANCEL_ACKNOWLEDGED);
        }
    }
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    return r;
}
WR_CY_Receipt wr_cy_cancel_pending(WR_CY_Supervisor *s, uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    WR_CY_Receipt r;
    if (s->stopped) r = receipt(s, WR_CY_STOPPED);
    else if (!valid_clock(s, now)) r = receipt(s, WR_CY_STALE);
    else r = from_cx(s, wr_cx_cancel_pending(s->queue, now));
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    return r;
}
WR_CY_Receipt wr_cy_shutdown(WR_CY_Supervisor *s) {
    if (!s || pthread_mutex_lock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    s->stopped = true;
    /* A blocked worker is NOT automatically interrupted by shutdown. */
    (void)wr_cx_shutdown(s->queue);
    s->pending_count = 0;
    WR_CY_Receipt r = receipt(s, WR_CY_STOPPED);
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CY_DENIED);
    return r;
}
void wr_cy_free(WR_CY_Supervisor *s) {
    if (!s) return;
    /* Caller must join ALL watchdog and worker threads before this call. */
    if (pthread_mutex_destroy(&s->lock) != 0) return;
    wr_cx_free(s->queue);
    free(s);
}
