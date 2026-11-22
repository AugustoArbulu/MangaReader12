// Read-only Darwin capability probe. It can only inspect its own descriptors.
#include <dlfcn.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <unistd.h>

// XNU bsd/sys/proc_info.h: PROC_PIDLISTFDS and struct proc_fdinfo.
enum { pid_list_fds = 1, capacity = 1024 };
struct fd_record {
    int32_t fd;
    uint32_t type;
};
_Static_assert(sizeof(struct fd_record) == 8, "unexpected XNU record layout");

typedef int (*pid_info_fn)(int, int, uint64_t, void *, int);

const char *wr_self_fd_status(void) {
    pid_info_fn query = (pid_info_fn)dlsym(RTLD_DEFAULT, "proc_pidinfo");
    if (query == NULL) {
        return "WR_SELF_FD=API_UNAVAILABLE";
    }

    int control = open("/dev/null", O_RDONLY);
    if (control < 0) {
        return "WR_SELF_FD=CONTROL_UNAVAILABLE";
    }

    struct fd_record records[capacity];
    int bytes = query(getpid(), pid_list_fds, 0, records, sizeof(records));
    close(control);
    if (bytes <= 0 || bytes > (int)sizeof(records) ||
        bytes % (int)sizeof(records[0]) != 0) {
        return "WR_SELF_FD=QUERY_UNAVAILABLE";
    }

    for (int i = 0; i < bytes / (int)sizeof(records[0]); i++) {
        if (records[i].fd == control) {
            return "WR_SELF_FD=CONTROL_LISTED";
        }
    }
    return "WR_SELF_FD=CONTROL_NOT_OBSERVED";
}

#ifndef WR_SELF_FD_APP
int main(void) {
    puts(wr_self_fd_status());
    return 0;
}
#endif
