/* Build70/DC native READ-ONLY filesystem lineage probe.
 * It does not use appinst, LSApplicationWorkspace, network, write syscalls,
 * file mutations, IPC or installer privileges.
 * No result can authorize installation. The "trusted" base is supplied by
 * a host fixture and its ancestry is NEVER independently authenticated.
 */
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "build70_dc_custody_lineage.h"
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef O_DIRECTORY
#error "DC requires O_DIRECTORY; never downgrade to pathname walk"
#endif
#ifndef O_NOFOLLOW
#error "DC requires O_NOFOLLOW; never downgrade to following symlinks"
#endif
#ifndef O_CLOEXEC
#error "DC requires O_CLOEXEC"
#endif
#ifndef AT_SYMLINK_NOFOLLOW
#error "DC requires AT_SYMLINK_NOFOLLOW"
#endif

static WR_DC_Receipt report(WR_DC_Status code) {
    WR_DC_Receipt r = {0}; /* Every production authority flag false. */
    r.status = code;
    return r;
}

static bool safe_anchor_literal(const char *s) {
    if (!s || s[0] != '/') return false;
    size_t n = strnlen(s, 1025u);
    if (n < 2u || n >= 1025u || s[n-1] == '/') return false;
    const char *p = s;
    while (*p) {
        if ((p == s || p[-1] == '/') &&
            p[0] == '.' && (p[1] == '/' || p[1] == '\0' ||
            (p[1] == '.' && (p[2] == '/' || p[2] == '\0')))) {
            return false;
        }
        ++p;
    }
    return true;
}

static bool private_dir(int fd, uid_t expected_uid) {
    struct stat st;
    return fstat(fd, &st) == 0 && S_ISDIR(st.st_mode) &&
           st.st_uid == expected_uid &&
           (st.st_mode & 07777) == 0700;
}

static bool inode_agrees(int parent_fd, const char *name, int fd) {
    struct stat seen, named;
    return fstat(fd, &seen) == 0 &&
           fstatat(parent_fd, name, &named, AT_SYMLINK_NOFOLLOW) == 0 &&
           seen.st_dev == named.st_dev && seen.st_ino == named.st_ino;
}

static int open_private_child(int parent_fd, const char *fixed_name,
                              uid_t expected_uid) {
    int fd = openat(parent_fd, fixed_name,
                    O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return -1;
    if (!private_dir(fd, expected_uid) ||
        !inode_agrees(parent_fd, fixed_name, fd)) {
        close(fd);
        return -1;
    }
    return fd;
}

WR_DC_Receipt wr_dc_inspect_host_only(const char *base,
                                     uint32_t asserted_client_uid) {
    WR_DC_Receipt result = report(WR_DC_REJECTED);
    if (!safe_anchor_literal(base) || asserted_client_uid == 0u ||
        (uint64_t)asserted_client_uid == (uint64_t)geteuid()) {
        return result;
    }
    const uid_t helper_uid = geteuid();
    int parent = -1, vault = -1, journal = -1, lock = -1;

    parent = open(base, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent < 0 || !private_dir(parent, helper_uid)) goto finish;
    vault = open_private_child(parent, WR_DC_PRIVATE, helper_uid);
    if (vault < 0) goto finish;
    journal = open_private_child(vault, WR_DC_STATE, helper_uid);
    if (journal < 0) goto finish;
    result.anchored_descendants_privately_owned_on_host = true;
    result.hypothetical_client_uid_differs_from_helper = true;

    lock = openat(journal, WR_DC_LOCK, O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (lock < 0) goto finish;
    struct stat lockinfo;
    if (fstat(lock, &lockinfo) != 0 ||
        !S_ISREG(lockinfo.st_mode) ||
        lockinfo.st_uid != helper_uid || lockinfo.st_nlink != 1 ||
        (lockinfo.st_mode & 07777) != 0600 || lockinfo.st_size != 0 ||
        !inode_agrees(journal, WR_DC_LOCK, lock)) {
        goto finish;
    }
    result.lock_file_privately_owned_on_host = true;

    struct stat markerinfo;
    if (fstatat(journal, WR_DC_PENDING, &markerinfo,
                AT_SYMLINK_NOFOLLOW) == 0) {
        result.marker_present = true;
        result.status = WR_DC_QUARANTINED;
    } else if (errno == ENOENT) {
        result.status = WR_DC_HOST_METADATA_REVIEWED;
    }
finish:
    if (lock >= 0) close(lock);
    if (journal >= 0) close(journal);
    if (vault >= 0) close(vault);
    if (parent >= 0) close(parent);
    return result;
}
