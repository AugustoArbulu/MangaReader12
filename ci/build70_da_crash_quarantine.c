/*
 * Build70 / Phase DA — no installation. Strict one-shot host crash evidence.
 *
 * The marker is intentionally never removed by this code. A restarted process
 * that sees it must refuse work until a future, separately reviewed and
 * independently trusted procedure can prove old tasks terminated. No such
 * procedure exists here. A same-UID writer or root can edit/delete the host
 * directory: 0700 + flock is NOT a privilege boundary or anti-rollback seal.
 *
 * No download, no URL, no socket, no appinst, no LSApplicationWorkspace.
 */
#define _POSIX_C_SOURCE 200809L
#include "build70_da_crash_quarantine.h"
#include <errno.h>
#include <fcntl.h>
#include <stdlib.h>
#include <string.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef O_DIRECTORY
#error "DA needs O_DIRECTORY"
#endif
#ifndef O_NOFOLLOW
#error "DA needs O_NOFOLLOW"
#endif
#ifndef O_CLOEXEC
#error "DA needs O_CLOEXEC"
#endif
#ifndef AT_SYMLINK_NOFOLLOW
#error "DA needs AT_SYMLINK_NOFOLLOW"
#endif

#define WR_DA_LOCK "wr-da-review.lock"
#define WR_DA_PENDING "wr-da-check.pending"
#define WR_DA_PENDING_BODY "PENDING-READ-ONLY-CHECK\n"

struct WR_DA_Journal {
    int directory_fd;
    int lock_fd;
    bool spent;
    bool quarantined;
};

static WR_DA_Receipt report(WR_DA_Status status, bool marker) {
    WR_DA_Receipt result = {0}; /* All authority fields false. */
    result.status = status;
    result.crash_evidence_is_present = marker;
    return result;
}

static int fixed_frame(const uint8_t *packet, size_t count) {
    static const uint8_t expected[WR_DA_FRAME_BYTES] =
        {'W','R','C','H','K','2','\n'};
    return packet && count == sizeof(expected) &&
           memcmp(packet, expected, sizeof(expected)) == 0;
}

static int valid_dir_stat(const struct stat *s) {
    return S_ISDIR(s->st_mode) && s->st_uid == geteuid() &&
           (s->st_mode & 0777) == 0700;
}

static int valid_lock_stat(const struct stat *s) {
    return S_ISREG(s->st_mode) && s->st_uid == geteuid() &&
           s->st_nlink == 1 && (s->st_mode & 0077) == 0 && s->st_size == 0;
}

static int marker_present(int dirfd) {
    struct stat info;
    if (fstatat(dirfd, WR_DA_PENDING, &info, AT_SYMLINK_NOFOLLOW) == 0) {
        return 1; /* ANY object at the pending marker name means quarantine. */
    }
    return errno == ENOENT ? 0 : -1;
}

static int safe_host_path(const char *path) {
    if (!path || path[0] != '/') return 0;
    size_t len = strlen(path);
    if (len < 2 || len > 1024 || path[len - 1] == '/') return 0;
    /* This is only basic validation; ancestors are not independently attested. */
    const char *p = path;
    while (*p) {
        if ((p == path || p[-1] == '/') && p[0] == '.' &&
            (p[1] == '/' || p[1] == '\0' ||
             (p[1] == '.' && (p[2] == '/' || p[2] == '\0')))) {
            return 0;
        }
        ++p;
    }
    return 1;
}

WR_DA_Journal *wr_da_open(const char *directory, WR_DA_Receipt *observation) {
    if (observation) *observation = report(WR_DA_DENIED, false);
    if (!observation || !safe_host_path(directory)) return NULL;
    WR_DA_Journal *j = calloc(1, sizeof(*j));
    if (!j) return NULL;
    j->directory_fd = -1;
    j->lock_fd = -1;
    j->directory_fd = open(directory, O_RDONLY | O_DIRECTORY |
                          O_NOFOLLOW | O_CLOEXEC);
    if (j->directory_fd < 0) goto reject;
    struct stat dirinfo;
    if (fstat(j->directory_fd, &dirinfo) != 0 ||
        !valid_dir_stat(&dirinfo)) goto reject;

    j->lock_fd = openat(j->directory_fd, WR_DA_LOCK,
                        O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0600);
    if (j->lock_fd < 0) goto reject;
    struct stat lockinfo;
    struct stat byname;
    if (fstat(j->lock_fd, &lockinfo) != 0 ||
        fstatat(j->directory_fd, WR_DA_LOCK, &byname,
                AT_SYMLINK_NOFOLLOW) != 0 ||
        !valid_lock_stat(&lockinfo) ||
        lockinfo.st_dev != byname.st_dev ||
        lockinfo.st_ino != byname.st_ino) goto reject;

    if (flock(j->lock_fd, LOCK_EX | LOCK_NB) != 0) {
        *observation = report(WR_DA_BUSY, false);
        goto reject;
    }
    if (fsync(j->lock_fd) != 0 || fsync(j->directory_fd) != 0)
        goto reject;
    int seen = marker_present(j->directory_fd);
    if (seen < 0) goto reject;
    j->quarantined = seen == 1;
    *observation = report(j->quarantined ? WR_DA_QUARANTINED : WR_DA_READY,
                          j->quarantined);
    return j;

reject:
    if (j->lock_fd >= 0) {
        (void)flock(j->lock_fd, LOCK_UN);
        close(j->lock_fd);
    }
    if (j->directory_fd >= 0) close(j->directory_fd);
    free(j);
    return NULL;
}

WR_DA_Receipt wr_da_offer(WR_DA_Journal *j, const uint8_t *packet, size_t count) {
    if (!j || !fixed_frame(packet, count)) return report(WR_DA_DENIED, false);
    if (j->quarantined || j->spent) return report(WR_DA_QUARANTINED, true);
    int seen = marker_present(j->directory_fd);
    if (seen != 0) {
        j->quarantined = true;
        return report(seen == 1 ? WR_DA_QUARANTINED : WR_DA_DENIED, true);
    }

    /* Reserve before any synthetic operation. Never delete the tombstone. */
    int fd = openat(j->directory_fd, WR_DA_PENDING,
                    O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC,
                    0600);
    if (fd < 0) {
        j->quarantined = true;
        return report(WR_DA_QUARANTINED, true);
    }
    j->spent = true; /* Fail closed even if write/fsync below fails. */
    const char body[] = WR_DA_PENDING_BODY;
    size_t offset = 0;
    const size_t length = sizeof(body) - 1;
    while (offset < length) {
        ssize_t n = write(fd, body + offset, length - offset);
        if (n <= 0) {
            close(fd);
            j->quarantined = true;
            return report(WR_DA_DENIED, true);
        }
        offset += (size_t)n;
    }
    if (fsync(fd) != 0 || fsync(j->directory_fd) != 0) {
        close(fd);
        j->quarantined = true;
        return report(WR_DA_DENIED, true);
    }
    struct stat info;
    int ok = fstat(fd, &info) == 0 &&
             S_ISREG(info.st_mode) && info.st_uid == geteuid() &&
             info.st_nlink == 1 && (info.st_mode & 0077) == 0 &&
             info.st_size == (off_t)length;
    close(fd);
    if (!ok) {
        j->quarantined = true;
        return report(WR_DA_DENIED, true);
    }
    return report(WR_DA_MARKED, true);
}

WR_DA_Receipt wr_da_observe(WR_DA_Journal *j) {
    if (!j) return report(WR_DA_DENIED, false);
    int seen = marker_present(j->directory_fd);
    if (seen != 0) j->quarantined = true;
    return report(seen < 0 ? WR_DA_DENIED :
                  (j->quarantined || j->spent ? WR_DA_QUARANTINED : WR_DA_READY),
                  j->quarantined || j->spent);
}

void wr_da_close(WR_DA_Journal *j) {
    if (!j) return;
    if (j->lock_fd >= 0) {
        (void)flock(j->lock_fd, LOCK_UN);
        close(j->lock_fd);
    }
    if (j->directory_fd >= 0) close(j->directory_fd);
    free(j);
}
