#!/usr/bin/env python3
"""Build70/CZ: nonprivileged, synthetic check-worker wiring for CY native C.

NO real update, URL, network, filesystem traversal, listener, installation,
appinst, IPA, entitlement, signed publisher or real iPad interaction.

The "service clock", recovery mode and synthetic worker behavior come only
from a HOST TEST HARNESS. This is not a secure IPC implementation. A remote
client may only supply 7-byte WRCHK2 newline, never these host controls.
The worker voluntarily exits on cancellation; a stuck worker is not killed.
A worker ACK is passed to CY only AFTER the Python thread has terminated.
"""
from __future__ import annotations
import ctypes
from dataclasses import dataclass
import threading

MAX64 = (1 << 64) - 1
FRAME = b"WRCHK2\n"
STARTED, COMPLETED, STOPPED, TIMEOUT, ACK, BACKOFF, FAILURE = (1, 5, 6, 9, 11, 12, 13)


class SyntheticServiceRejected(ValueError):
    pass


class NativeReceipt(ctypes.Structure):
    _fields_ = [
        ("status", ctypes.c_int),
        ("trusted_worker_ticket", ctypes.c_uint64),
        ("retry_after_ms", ctypes.c_uint64),
        ("pending_count", ctypes.c_uint8),
        ("failure_streak", ctypes.c_uint8),
        ("worker_may_still_be_running", ctypes.c_bool),
        ("cancel_requested", ctypes.c_bool),
        ("caller_authenticated", ctypes.c_bool),
        ("publisher_verified", ctypes.c_bool),
        ("ipa_bytes_authenticated", ctypes.c_bool),
        ("owner_consent_verified", ctypes.c_bool),
        ("installation_authorized", ctypes.c_bool),
        ("installation_performed", ctypes.c_bool)
    ]


def configure_native(lib):
    """Bind a test-only CY shared library compiled independently by tests."""
    lib.wr_cy_new.argtypes = ()
    lib.wr_cy_new.restype = ctypes.c_void_p
    signatures = {
        "wr_cy_offer": (ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.c_uint64),
        "wr_cy_poll": (ctypes.c_void_p, ctypes.c_uint64),
        "wr_cy_watchdog": (ctypes.c_void_p, ctypes.c_uint64),
        "wr_cy_complete": (ctypes.c_void_p, ctypes.c_uint64, ctypes.c_bool, ctypes.c_uint64),
        "wr_cy_ack_cancel": (ctypes.c_void_p, ctypes.c_uint64, ctypes.c_uint64),
        "wr_cy_cancel_pending": (ctypes.c_void_p, ctypes.c_uint64),
        "wr_cy_shutdown": (ctypes.c_void_p,),
    }
    for name, args in signatures.items():
        fn = getattr(lib, name)
        fn.argtypes = args
        fn.restype = NativeReceipt
    lib.wr_cy_free.argtypes = (ctypes.c_void_p,)
    lib.wr_cy_free.restype = None


@dataclass
class _SyntheticWorker:
    ticket: int
    blocked_until_released: bool
    started: threading.Event
    release: threading.Event
    cancelled: threading.Event
    finished: threading.Event
    success: bool = True
    result: bool = False
    thread: threading.Thread | None = None


class SyntheticCheckRuntime:
    """HOST fixture with exactly one scheduler and one worker at any moment.

    Clock, worker release and recovery calls must be harness-only controls.
    This deliberately does not accept any of them from the untrusted frame.
    Crash recovery is merely an explicitly injected quarantine flag; there
    is NO durable restart protection, true root isolation or authentication.
    """

    def __init__(self, native_lib, *, recovery_required=False, block_worker=False):
        configure_native(native_lib)
        if type(recovery_required) is not bool or type(block_worker) is not bool:
            raise SyntheticServiceRejected("host configuration must be explicit")
        self.lib = native_lib
        self.handle = self.lib.wr_cy_new()
        if not self.handle:
            raise SyntheticServiceRejected("native supervisor unavailable")
        self._lock = threading.RLock()
        self.now_ms = 0
        self.recovery_required = recovery_required
        self.block_worker = block_worker
        self.closed = False
        self.worker = None
        self.started_count = 0
        self.completed_count = 0
        self.acked_count = 0
        self.history = []

    def _inspect(self, receipt):
        for field in ("caller_authenticated", "publisher_verified",
                      "ipa_bytes_authenticated", "owner_consent_verified",
                      "installation_authorized", "installation_performed"):
            if getattr(receipt, field):
                raise SyntheticServiceRejected("native receipt tried to grant authority")
        if receipt.pending_count > 1:
            raise SyntheticServiceRejected("native queue expanded beyond one")
        self.history.append((self.now_ms, receipt.status,
                             receipt.pending_count, receipt.cancel_requested))
        if receipt.status == STARTED:
            self._start_worker(receipt.trusted_worker_ticket)
        if receipt.cancel_requested and self.worker:
            self.worker.cancelled.set()
        return receipt

    def _start_worker(self, ticket):
        if not ticket or self.worker is not None or self.closed:
            raise SyntheticServiceRejected("overlapping worker or invalid ticket")
        w = _SyntheticWorker(
            ticket=ticket, blocked_until_released=self.block_worker,
            started=threading.Event(), release=threading.Event(),
            cancelled=threading.Event(), finished=threading.Event()
        )

        def task():
            w.started.set()
            while True:
                if w.release.wait(0.005):
                    w.result = bool(w.success and not w.cancelled.is_set())
                    break
                if w.cancelled.is_set() and not w.blocked_until_released:
                    w.result = False
                    break
            w.finished.set()

        w.thread = threading.Thread(target=task, name="CZ-SYNTHETIC-NOT-NETWORK")
        self.worker = w
        self.started_count += 1
        w.thread.start()

    def offer_untrusted(self, packet: bytes):
        """The only simulated client-controlled input is the exact packet."""
        if type(packet) is not bytes:
            raise SyntheticServiceRejected("client frame must be bytes")
        with self._lock:
            if self.closed or self.recovery_required:
                raise SyntheticServiceRejected("service unavailable or quarantined")
            b = ctypes.create_string_buffer(packet)
            return self._inspect(
                self.lib.wr_cy_offer(self.handle, b, len(packet), self.now_ms)
            )

    def advance_host_clock(self, delta_ms: int):
        """Trusted host test control only; must never become an IPC parameter."""
        if type(delta_ms) is not int or delta_ms < 0 or self.now_ms > MAX64 - delta_ms:
            raise SyntheticServiceRejected("invalid synthetic monotonic advance")
        with self._lock:
            if self.closed:
                raise SyntheticServiceRejected("closed synthetic service")
            self.now_ms += delta_ms
            return self._inspect(self.lib.wr_cy_watchdog(self.handle, self.now_ms))

    def poll_host_queue(self):
        """Trusted host test control only; cannot start while worker is alive."""
        with self._lock:
            if self.closed or self.recovery_required:
                raise SyntheticServiceRejected("service unavailable or quarantined")
            return self._inspect(self.lib.wr_cy_poll(self.handle, self.now_ms))

    def release_synthetic_worker(self, *, success=True):
        """Trusted host test control. A real worker must signal independently."""
        if type(success) is not bool:
            raise SyntheticServiceRejected("invalid synthetic outcome")
        with self._lock:
            if not self.worker:
                raise SyntheticServiceRejected("no synthetic worker")
            self.worker.success = success
            self.worker.release.set()

    def reap_finished_worker(self):
        """Return None while thread lives; NEVER ACK a still-running thread."""
        with self._lock:
            if self.closed:
                raise SyntheticServiceRejected("closed synthetic service")
            w = self.worker
            if w is None or not w.finished.is_set():
                return None
            w.thread.join(timeout=2.0)
            if w.thread.is_alive():
                return None
            watch = self._inspect(self.lib.wr_cy_watchdog(self.handle, self.now_ms))
            if watch.cancel_requested or w.cancelled.is_set():
                outcome = self._inspect(
                    self.lib.wr_cy_ack_cancel(self.handle, w.ticket, self.now_ms)
                )
            else:
                outcome = self._inspect(
                    self.lib.wr_cy_complete(self.handle, w.ticket, w.result, self.now_ms)
                )
                if outcome.status == TIMEOUT:
                    outcome = self._inspect(
                        self.lib.wr_cy_ack_cancel(self.handle, w.ticket, self.now_ms)
                    )
            if outcome.status == ACK:
                self.acked_count += 1
            elif outcome.status in (COMPLETED, FAILURE):
                self.completed_count += 1
            else:
                raise SyntheticServiceRejected("cannot safely retire worker")
            self.worker = None
            return outcome

    def reconcile_quarantine_host_only(self):
        """A deliberately NON-AUTHENTICATED host fixture reset, NOT a device API.

        The caller MUST separately prove no old processes or worker remain,
        with durable state protected from rollback. This lab cannot do that.
        """
        with self._lock:
            if self.closed or self.worker:
                raise SyntheticServiceRejected("cannot reconcile active fixture")
            self.recovery_required = False

    def close(self):
        with self._lock:
            if self.closed:
                return
            self.closed = True
            if self.worker:
                self.worker.cancelled.set()
                self.worker.release.set()
                w = self.worker
            else:
                w = None
        if w:
            w.thread.join(timeout=2.0)
            if w.thread.is_alive():
                raise SyntheticServiceRejected("worker did not exit; cannot free native state")
        with self._lock:
            self.lib.wr_cy_shutdown(self.handle)
            self.lib.wr_cy_free(self.handle)
            self.handle = None
            self.worker = None


# Intentionally no executable main, no socket, no network and no installer.
