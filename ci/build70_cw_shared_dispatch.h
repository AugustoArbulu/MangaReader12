#ifndef WEBREADER_CW_SHARED_DISPATCH_H
#define WEBREADER_CW_SHARED_DISPATCH_H
#include "build70_cw_checkonly_core.h"
#ifdef __cplusplus
extern "C" {
#endif
typedef struct WR_CW_Dispatcher WR_CW_Dispatcher;
/* A single dispatcher shared by threads within one process. The caller MUST
 * join all workers before free; cross-process/global persistence not provided.
 */
WR_CW_Dispatcher *wr_cw_dispatch_new(void);
WR_CW_Decision wr_cw_dispatch_offer(WR_CW_Dispatcher *dispatcher,
                                   const uint8_t *packet, size_t length,
                                   uint64_t monotonic_ms);
void wr_cw_dispatch_free(WR_CW_Dispatcher *dispatcher);
#ifdef __cplusplus
}
#endif
#endif
