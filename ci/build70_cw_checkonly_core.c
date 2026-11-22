/* Phase CW — native, platform-neutral CHECK-ONLY policy core.
 * It has NO network, file, process, IPC listener, appinst or install code.
 * All callers (including malicious ones) are untrusted: WRCHK2\n can at most
 * request a globally bounded, read-only version check by a future service.
 * This model has only in-memory, per-instance rate limits and therefore
 * MUST NOT be connected to a privileged endpoint as-is.
 */
#include "build70_cw_checkonly_core.h"
#include <string.h>

WR_CW_Decision wr_cw_offer(WR_CW_Gate *gate, const uint8_t *packet,
                            size_t length, uint64_t monotonic_ms) {
    WR_CW_Decision out = {0}; /* Every authority field stays false. */
    static const uint8_t frame[WR_CW_FRAME_BYTES] = {
        'W', 'R', 'C', 'H', 'K', '2', '\n'
    };
    out.status = WR_CW_REJECTED;
    if (!gate || !packet || length != sizeof(frame) ||
        memcmp(packet, frame, sizeof(frame)) != 0) {
        return out;
    }
    if (gate->seen) {
        /* Subtract ONLY after checking order to avoid underflow. */
        if (monotonic_ms < gate->last_accepted_ms ||
            monotonic_ms - gate->last_accepted_ms < WR_CW_MIN_INTERVAL_MS) {
            out.status = WR_CW_RATE_LIMITED;
            return out;
        }
    }
    gate->seen = true;
    gate->last_accepted_ms = monotonic_ms;
    out.status = WR_CW_CHECK_NOTICE_ACCEPTED;
    return out;
}
