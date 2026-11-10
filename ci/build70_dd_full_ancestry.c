/*
 * WebReader Build70/DD — read-only full host path ancestry audit.
 * Anchors at "/" and walks every component via openat(O_NOFOLLOW). It
 * inspects host metadata at one instant ONLY. A future iOS12 helper must
 * independently prove its own identity, app access denial and storage
 * provenance. Claiming another UID is NEVER sufficient authorization.
 *
 * No socket, install, appinst, TLS, file creation, chmod, network or IPC.
 */
#if defined(__APPLE__)
#define _DARWIN_C_SOURCE 1
#else
#define _POSIX_C_SOURCE 200809L
#endif
#include "build70_dd_full_ancestry.h"
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <unistd.h>

#ifndef O_NOFOLLOW
#error "DD requires O_NOFOLLOW: fail closed if unavailable"
#endif
#ifndef O_DIRECTORY
#error "DD requires O_DIRECTORY: fail closed if unavailable"
#endif
#ifndef O_CLOEXEC
#error "DD requires O_CLOEXEC: fail closed if unavailable"
#endif
#ifndef AT_SYMLINK_NOFOLLOW
#error "DD requires AT_SYMLINK_NOFOLLOW: fail closed if unavailable"
#endif

static WR_DD_Receipt denied(void) {
    WR_DD_Receipt out = {0};
    out.status = WR_DD_REJECTED;
    return out;
}
static int safe_path(const char *s) {
    if (!s || s[0] != '/') return 0;
    size_t n = strnlen(s, 1025u);
    if (n < 2u || n >= 1025u || s[n - 1] == '/') return 0;
    size_t part = 0u;
    for (size_t i = 1; i <= n; i++) {
        if (s[i] == '/' || s[i] == '\0') {
            if (!part || part > 255u) return 0;
            const char *start = s + i - part;
            if ((part == 1u && start[0] == '.') ||
                (part == 2u && start[0] == '.' && start[1] == '.')) {
                return 0;
            }
            part = 0u;
        } else {
            part++;
        }
    }
    return 1;
}
static int same_inode(int parent, const char *name, int fd) {
    struct stat opened, named;
    if (fstat(fd, &opened) != 0 ||
        fstatat(parent, name, &named, AT_SYMLINK_NOFOLLOW) != 0) return 0;
    return opened.st_dev == named.st_dev && opened.st_ino == named.st_ino;
}
static int acceptable_host_ancestor(int fd, uid_t self) {
    struct stat st;
    if (fstat(fd, &st) != 0 || !S_ISDIR(st.st_mode)) return 0;
    if (st.st_uid != 0 && st.st_uid != self) return 0;
    /* Group/world writable, even sticky directories, are not a trusted
     * host ancestry in this lab. Owner write by the app UID remains a risk
     * if the app and helper happen to share the same UID.
     */
    return (st.st_mode & 0022) == 0;
}
static int private_host_dir(int fd, uid_t self) {
    struct stat st;
    return fstat(fd, &st) == 0 &&
        S_ISDIR(st.st_mode) && st.st_uid == self &&
        (st.st_mode & 07777) == 0700;
}
static int open_child(int parent, const char *component, int is_private,
                      uid_t self) {
    int fd = openat(parent, component,
                    O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (fd < 0) return -1;
    int ok = same_inode(parent, component, fd) &&
        (is_private ? private_host_dir(fd, self)
                    : acceptable_host_ancestor(fd, self));
    if (!ok) { close(fd); return -1; }
    return fd;
}
WR_DD_Receipt wr_dd_inspect_host_ancestors(const char *base,
                                          uint32_t client_uid_claim) {
    WR_DD_Receipt r = denied();
    uid_t self = geteuid();
    if (!safe_path(base) || client_uid_claim == 0u ||
        (uint64_t)client_uid_claim == (uint64_t)self) return r;

    int parent = open("/", O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
    if (parent < 0) return r;
    int fd = -1;
    if (!acceptable_host_ancestor(parent, self)) goto done;

    size_t n = strlen(base);
    size_t start = 1u;
    for (size_t i = 1u; i <= n; i++) {
        if (base[i] != '/' && base[i] != '\0') continue;
        char component[256];
        size_t k = i - start;
        if (k == 0u || k > 255u) goto done;
        memcpy(component, base + start, k);
        component[k] = '\0';
        fd = open_child(parent, component, 0, self);
        if (fd < 0) goto done;
        close(parent);
        parent = fd;
        fd = -1;
        start = i + 1u;
    }
    r.complete_host_ancestor_chain_observed = true;
    r.host_ancestors_without_group_or_other_write = true;
    r.claimed_client_uid_differs = true;

    fd = open_child(parent, WR_DD_PRIVATE, 1, self);
    if (fd < 0) goto done;
    close(parent);
    parent = fd;
    fd = -1;

    fd = open_child(parent, WR_DD_STATE, 1, self);
    if (fd < 0) goto done;
    close(parent);
    parent = fd;
    fd = -1;
    r.host_descendant_dirs_owner_0700 = true;

    int lock = openat(parent, WR_DD_LOCK,
                      O_RDONLY | O_NOFOLLOW | O_CLOEXEC);
    if (lock < 0) goto done;
    struct stat st;
    int good = fstat(lock, &st) == 0 && S_ISREG(st.st_mode) &&
        st.st_uid == self && st.st_nlink == 1 &&
        (st.st_mode & 07777) == 0600 && st.st_size == 0 &&
        same_inode(parent, WR_DD_LOCK, lock);
    close(lock);
    if (!good) goto done;
    r.host_lock_owner_0600_singlelink = true;

    struct stat marker;
    if (fstatat(parent, WR_DD_PENDING, &marker,
                AT_SYMLINK_NOFOLLOW) == 0) {
        r.marker_present = true;
        r.status = WR_DD_QUARANTINED;
    } else if (errno == ENOENT) {
        r.status = WR_DD_HOST_METADATA_REVIEWED;
    }
done:
    if (fd >= 0) close(fd);
    close(parent);
    return r;
}
