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

int main(void) {
    pid_info_fn query = (pid_info_fn)dlsym(RTLD_DEFAULT, "proc_pidinfo");
    if (query == NULL) {
        puts("WR_SELF_FD=API_UNAVAILABLE");
        return 0;
    }

    int control = open("/dev/null", O_RDONLY);
    if (control < 0) {
        puts("WR_SELF_FD=CONTROL_UNAVAILABLE");
        return 0;
    }

    struct fd_record records[capacity];
    int bytes = query(getpid(), pid_list_fds, 0, records, sizeof(records));
    close(control);
    if (bytes <= 0 || bytes > (int)sizeof(records) ||
        bytes % (int)sizeof(records[0]) != 0) {
        puts("WR_SELF_FD=QUERY_UNAVAILABLE");
        return 0;
    }

    for (int i = 0; i < bytes / (int)sizeof(records[0]); i++) {
        if (records[i].fd == control) {
            puts("WR_SELF_FD=CONTROL_LISTED");
            return 0;
        }
    }
    puts("WR_SELF_FD=CONTROL_NOT_OBSERVED");
    return 0;
}
