/* WebReader Build70 / CX: check-only bounded scheduler, no installer.
 * A future privileged service must take monotonic_ms from its OWN trusted
 * clock and use exactly one scheduler per independently protected service.
 * The caller's packet is NEVER a source of URL, IPA, version, signing key,
 * publisher identity, process credentials or installation permission.
 * This is host-only test policy; it does not open sockets, files or network.
 */
#include "build70_cx_bounded_scheduler.h"
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>

struct WR_CX_Scheduler {
    pthread_mutex_t lock;
    bool inflight, pending, stopped, observed_clock, started_before;
    uint64_t last_clock_ms, last_started_ms, ticket_counter, active_ticket;
};

static WR_CX_Receipt receipt(const WR_CX_Scheduler *s, WR_CX_Status status) {
    WR_CX_Receipt r = {0}; /* ALL authority fields always false. */
    r.status = status;
    if (s) {
        r.pending_count = s->pending ? 1u : 0u;
        r.check_inflight = s->inflight;
        /* Not an IPC session ticket; it is used by trusted host test workers. */
        r.local_worker_ticket = s->inflight ? s->active_ticket : 0u;
    }
    return r;
}
static bool valid_frame(const uint8_t *frame, size_t len) {
    static const uint8_t exactly[WR_CX_FRAME_BYTES] = {
        'W','R','C','H','K','2','\n'
    };
    return frame && len == sizeof(exactly) &&
           memcmp(frame, exactly, sizeof(exactly)) == 0;
}
static bool track_clock(WR_CX_Scheduler *s, uint64_t now) {
    if (s->observed_clock && now < s->last_clock_ms) return false;
    s->observed_clock = true;
    s->last_clock_ms = now;
    return true;
}
static bool cooldown_elapsed(WR_CX_Scheduler *s, uint64_t now) {
    return !s->started_before ||
        (now >= s->last_started_ms &&
         now - s->last_started_ms >= WR_CX_MIN_START_INTERVAL_MS);
}
static WR_CX_Status start_check(WR_CX_Scheduler *s, uint64_t now) {
    if (s->ticket_counter == UINT64_MAX) return WR_CX_DENIED;
    s->ticket_counter++;
    s->active_ticket = s->ticket_counter;
    s->inflight = true;
    s->pending = false;
    s->started_before = true;
    s->last_started_ms = now;
    return WR_CX_STARTED;
}
WR_CX_Scheduler *wr_cx_new(void) {
    WR_CX_Scheduler *s = calloc(1, sizeof(*s));
    if (!s) return NULL;
    if (pthread_mutex_init(&s->lock, NULL) != 0) {
        free(s);
        return NULL;
    }
    return s;
}
WR_CX_Receipt wr_cx_offer(WR_CX_Scheduler *s, const uint8_t *frame,
                          size_t len, uint64_t now) {
    if (!s || !valid_frame(frame, len)) return receipt(NULL, WR_CX_DENIED);
    if (pthread_mutex_lock(&s->lock) != 0) return receipt(NULL, WR_CX_DENIED);
    WR_CX_Status status;
    if (s->stopped) status = WR_CX_STOPPED;
    else if (!track_clock(s, now)) status = WR_CX_STALE;
    else if (s->pending) status = WR_CX_ALREADY_PENDING;
    else if (s->inflight || !cooldown_elapsed(s, now)) {
        s->pending = true; /* bounded single coalesced notification */
        status = WR_CX_COALESCED;
    } else status = start_check(s, now);
    WR_CX_Receipt result = receipt(s, status);
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CX_DENIED);
    return result;
}
WR_CX_Receipt wr_cx_poll(WR_CX_Scheduler *s, uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0)
        return receipt(NULL, WR_CX_DENIED);
    WR_CX_Status status;
    if (s->stopped) status = WR_CX_STOPPED;
    else if (!track_clock(s, now)) status = WR_CX_STALE;
    else if (s->inflight) status = WR_CX_BUSY;
    else if (!s->pending) status = WR_CX_IDLE;
    else if (!cooldown_elapsed(s, now)) status = WR_CX_RATE_LIMITED;
    else status = start_check(s, now);
    WR_CX_Receipt result = receipt(s, status);
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CX_DENIED);
    return result;
}
WR_CX_Receipt wr_cx_finish(WR_CX_Scheduler *s, uint64_t ticket,
                           uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0)
        return receipt(NULL, WR_CX_DENIED);
    WR_CX_Status status;
    if (s->stopped) status = WR_CX_STOPPED;
    else if (!track_clock(s, now)) status = WR_CX_STALE;
    else if (!s->inflight || ticket == 0 || ticket != s->active_ticket)
        status = WR_CX_STALE;
    else {
        s->inflight = false;
        s->active_ticket = 0;
        status = WR_CX_FINISHED; /* No external side effect; pending not started. */
    }
    WR_CX_Receipt result = receipt(s, status);
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CX_DENIED);
    return result;
}
WR_CX_Receipt wr_cx_cancel_pending(WR_CX_Scheduler *s, uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0)
        return receipt(NULL, WR_CX_DENIED);
    WR_CX_Status status;
    if (s->stopped) status = WR_CX_STOPPED;
    else if (!track_clock(s, now)) status = WR_CX_STALE;
    else if (!s->pending) status = WR_CX_IDLE;
    else {
        s->pending = false;
        status = WR_CX_CANCELLED;
    }
    WR_CX_Receipt result = receipt(s, status);
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CX_DENIED);
    return result;
}
WR_CX_Receipt wr_cx_cancel_active(WR_CX_Scheduler *s, uint64_t ticket,
                                  uint64_t now) {
    if (!s || pthread_mutex_lock(&s->lock) != 0)
        return receipt(NULL, WR_CX_DENIED);
    WR_CX_Status status;
    if (s->stopped) status = WR_CX_STOPPED;
    else if (!track_clock(s, now)) status = WR_CX_STALE;
    else if (!s->inflight || ticket == 0 || ticket != s->active_ticket)
        status = WR_CX_STALE;
    else {
        s->inflight = false;
        s->active_ticket = 0;
        s->pending = false;
        status = WR_CX_CANCELLED; /* Does not stop an external running task. */
    }
    WR_CX_Receipt result = receipt(s, status);
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CX_DENIED);
    return result;
}
WR_CX_Receipt wr_cx_shutdown(WR_CX_Scheduler *s) {
    if (!s || pthread_mutex_lock(&s->lock) != 0)
        return receipt(NULL, WR_CX_DENIED);
    s->stopped = true;
    s->inflight = false;
    s->pending = false;
    s->active_ticket = 0;
    WR_CX_Receipt result = receipt(s, WR_CX_STOPPED);
    if (pthread_mutex_unlock(&s->lock) != 0) return receipt(NULL, WR_CX_DENIED);
    return result;
}
void wr_cx_free(WR_CX_Scheduler *s) {
    if (!s) return;
    /* Client MUST join all workers before teardown. */
    if (pthread_mutex_destroy(&s->lock) != 0) return;
    free(s);
}
