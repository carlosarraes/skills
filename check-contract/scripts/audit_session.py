"""Authenticated local storage for immutable audit generations.

The HMAC chain detects accidental corruption, stale generations, and
token-only or unkeyed forgery. Because its key and data are owned by the same
effective user, it does not protect against deliberate coordinated filesystem
tampering by that same effective user.

Response creation is caller-owned at the exact issued path. Consumption claims
the generation first, then reads only the exact issued response name through
the verified inbox directory descriptor with O_NOFOLLOW and a fixed byte
limit.

Each claim is published only after its nonblocking exclusive lease is live.
The lease spans response validation through the successor commit and is
released by descriptor close, including on process exit. Forked children
invalidate inherited capabilities and lock registries. Every successor
decision also holds a fresh cross-process transaction-file lock. A fully
fsynced authenticated generation becomes the one successor at its atomic
directory rename; dot-prefixed staging directories are never children.
Recovery never waits for an active lease.
"""

import hashlib
import hmac
import json
import math
import os
import re
import secrets
import stat
import fcntl
import errno
import ctypes
import queue
import signal
import threading
import time
import weakref
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


TOKEN_RE = re.compile(r"([0-9a-f]{32})\.([0-9a-f]{64})")
RESPONSE_RE = re.compile(r"[0-9a-f]{32}\.json")
DIRECTORY_FLAGS = (
    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
)
READ_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
RESPONSE_BYTE_LIMIT = 2 * 1024 * 1024
RENAME_NOREPLACE = 1
CLAIM_MARKER = b"claim-v1\n"
TRANSACTION_MARKER = b"transaction-v1\n"
_SUCCESSOR_LOCKS_GUARD = threading.Lock()
_SUCCESSOR_LOCKS = {}
_TRACKED_LEASE_OWNERSHIPS = set()
_LEASE_REFS = {}
_TRACKED_TRANSACTION_OWNERSHIPS = set()
_PENDING_LEASE_CLOSE_FDS = set()
_PENDING_TRANSACTION_CLOSE_FDS = set()
_CONSUMED_DESCRIPTOR_OWNERSHIPS = set()
_QUARANTINED_DESCRIPTOR_OWNERSHIPS = set()
_CLEANUP_QUEUE = queue.SimpleQueue()
_CLEANUP_THREAD = None
_CLEANUP_SUPERVISOR_LOCK = threading.Lock()
_CLOSE_ATTEMPT_LOCAL = threading.local()
_LIBC = ctypes.CDLL(None, use_errno=True)
_CLOSE_RANGE = getattr(_LIBC, "close_range", None)
_KERNEL_FD_MAX = (
    1 << (ctypes.sizeof(ctypes.c_int) * 8 - 1)
) - 1
if _CLOSE_RANGE is not None:
    _CLOSE_RANGE.argtypes = (
        ctypes.c_uint,
        ctypes.c_uint,
        ctypes.c_int,
    )
    _CLOSE_RANGE.restype = ctypes.c_int


class _OneShotToken:
    """An idempotently releasable token that is never reacquired."""

    def __init__(self):
        self._released = False
        self._lock = threading.Lock()
        self._lock.acquire()

    def locked(self) -> bool:
        return not self._released

    def release(self) -> None:
        if self._released:
            return
        try:
            self._lock.release()
        except RuntimeError:
            self._released = True
            return
        self._released = True

    def wait(self) -> None:
        self._lock.acquire()
        self._lock.release()


class _ForkLifecycleGate:
    """Concurrent audit readers with an exclusive fork snapshot boundary."""

    def __init__(self):
        self._metadata = threading.Lock()
        self._drained = threading.Condition(self._metadata)
        self._readers = set()
        self._fork_pending = False

    def try_enter_audit(self):
        if not self._metadata.acquire(timeout=0.005):
            return None
        try:
            self._readers = {
                reader for reader in self._readers if reader.locked()
            }
            if self._fork_pending:
                return None
            reader = _OneShotToken()
            self._readers.add(reader)
            return reader
        finally:
            self._metadata.release()

    def exit_audit(self, reader) -> None:
        self.ensure_audit_released(reader)

    @staticmethod
    def ensure_audit_released(reader) -> None:
        reader.release()

    def before_fork(self) -> None:
        with self._metadata:
            while self._fork_pending:
                self._drained.wait()
            self._fork_pending = True
            readers = tuple(self._readers)
            for reader in readers:
                reader.wait()
            self._readers.clear()

    def after_parent_reopen(self) -> None:
        with self._metadata:
            self._fork_pending = False
            self._drained.notify_all()

_FORK_FD_LIFECYCLE_GATE = _ForkLifecycleGate()


class _DescriptorOwnershipGate:
    """Concurrent publishers with bounded exclusive cleanup admission."""

    def __init__(self):
        self._metadata = threading.Lock()
        self._publishers = set()
        self._cleanup = None
        self._writer_intents = {}

    def try_enter_publication(self):
        if not self._metadata.acquire(timeout=0.005):
            return None
        try:
            self._publishers = {
                publisher
                for publisher in self._publishers
                if publisher.locked()
            }
            if self._writer_intents:
                return None
            if self._cleanup is not None and self._cleanup.locked():
                return None
            publisher = threading.Lock()
            publisher.acquire()
            self._publishers.add(publisher)
            return publisher
        finally:
            self._metadata.release()

    def try_enter_cleanup(self, intent_key):
        if not self._metadata.acquire(timeout=0.005):
            return None
        try:
            self._publishers = {
                publisher
                for publisher in self._publishers
                if publisher.locked()
            }
            intent_token = self._writer_intents.get(intent_key)
            if intent_token is None:
                intent_token = object()
                self._writer_intents[intent_key] = intent_token
            if self._publishers:
                return None
            if self._cleanup is not None and self._cleanup.locked():
                return None
            cleanup = threading.Lock()
            cleanup.acquire()
            self._cleanup = cleanup
            return cleanup, intent_key, intent_token
        finally:
            self._metadata.release()

    @staticmethod
    def exit_publication(token) -> None:
        _DescriptorOwnershipGate.ensure_publication_released(token)

    @staticmethod
    def ensure_publication_released(token) -> None:
        if token.locked():
            token.release()

    def exit_cleanup(
        gate,
        cleanup,
        intent_key,
        writer_intent,
        *,
        retain_intent: bool,
    ) -> None:
        gate.ensure_cleanup_released(
            cleanup,
            intent_key,
            writer_intent,
            retain_intent=retain_intent,
        )

    def ensure_cleanup_released(
        gate,
        cleanup,
        intent_key,
        writer_intent,
        *,
        retain_intent: bool,
    ) -> None:
        if (
            not retain_intent
            and gate._writer_intents.get(intent_key) is writer_intent
        ):
            del gate._writer_intents[intent_key]
        if cleanup.locked():
            cleanup.release()


_DESCRIPTOR_OWNERSHIP_GATE = _DescriptorOwnershipGate()


def _close_owned_descriptor(descriptor: int) -> None:
    """Close one runtime-owned Linux fd slot without per-fd errors.

    Callers own either the cleanup token or the post-fork snapshot. Raw
    same-process close/rebind outside those boundaries is coordinated
    descriptor tampering under the documented same-UID threat-model limit.
    """
    _require_kernel_fd(descriptor)
    if _CLOSE_RANGE is None:
        raise OSError(
            errno.ENOSYS,
            "single-slot close_range is unavailable",
        )
    ctypes.set_errno(0)
    result = _CLOSE_RANGE(descriptor, descriptor, 0)
    if result != 0:
        number = ctypes.get_errno() or errno.EIO
        raise OSError(
            number,
            os.strerror(number),
            descriptor,
        )
    attempt = getattr(_CLOSE_ATTEMPT_LOCAL, "current", None)
    if attempt is not None and attempt.descriptor == descriptor:
        attempt.completed_successfully = True


def _require_kernel_fd(descriptor) -> None:
    if isinstance(descriptor, bool) or not isinstance(descriptor, int):
        raise TypeError("owned descriptor must be an integer fd")
    if descriptor < 0 or descriptor > _KERNEL_FD_MAX:
        raise ValueError("owned descriptor is outside the kernel fd range")


@contextmanager
def _ownership_publication():
    token = _DESCRIPTOR_OWNERSHIP_GATE.try_enter_publication()
    if token is None:
        raise SessionBusyError("descriptor ownership publication is active")
    try:
        yield
    finally:
        try:
            _DESCRIPTOR_OWNERSHIP_GATE.exit_publication(token)
        finally:
            (
                _DESCRIPTOR_OWNERSHIP_GATE
                .ensure_publication_released(token)
            )


class _CleanupAdmission:
    def __init__(self):
        self.retain_intent = False

    def retain(self) -> None:
        self.retain_intent = True


@contextmanager
def _ownership_cleanup(kind: str, ownership):
    intent_key = (kind, ownership)
    admission_tokens = _DESCRIPTOR_OWNERSHIP_GATE.try_enter_cleanup(
        intent_key
    )
    if admission_tokens is None:
        raise SessionBusyError("descriptor ownership registry is active")
    cleanup, intent_key, writer_intent = admission_tokens
    admission = _CleanupAdmission()
    try:
        yield admission
    except BaseException:
        admission.retain()
        raise
    finally:
        try:
            _DESCRIPTOR_OWNERSHIP_GATE.exit_cleanup(
                cleanup,
                intent_key,
                writer_intent,
                retain_intent=admission.retain_intent,
            )
        finally:
            _DESCRIPTOR_OWNERSHIP_GATE.ensure_cleanup_released(
                cleanup,
                intent_key,
                writer_intent,
                retain_intent=admission.retain_intent,
            )


def _ownership_state(kind: str):
    if kind == "lease":
        return (
            _PENDING_LEASE_CLOSE_FDS,
            _TRACKED_LEASE_OWNERSHIPS,
        )
    return (
        _PENDING_TRANSACTION_CLOSE_FDS,
        _TRACKED_TRANSACTION_OWNERSHIPS,
    )


def _close_owned_record(kind: str, ownership) -> bool:
    pending, tracked = _ownership_state(kind)
    pending.add(ownership)
    if ownership not in tracked:
        return _forget_owned_record(kind, ownership)
    if not _consume_owned_slot(ownership):
        return False
    return _forget_owned_record(kind, ownership)


class _DescriptorCloseAttempt:
    def __init__(self, descriptor: int):
        self.descriptor = descriptor
        self.completed_successfully = False


def _record_consumed_slot(ownership) -> None:
    _CONSUMED_DESCRIPTOR_OWNERSHIPS.add(ownership)
    _QUARANTINED_DESCRIPTOR_OWNERSHIPS.discard(ownership)


def _consume_owned_slot(ownership) -> bool:
    """Close an exact slot while preserving the syscall's known outcome."""
    if ownership in _CONSUMED_DESCRIPTOR_OWNERSHIPS:
        return True
    if ownership in _QUARANTINED_DESCRIPTOR_OWNERSHIPS:
        return False
    _QUARANTINED_DESCRIPTOR_OWNERSHIPS.add(ownership)
    attempt = _DescriptorCloseAttempt(ownership[0])
    previous_attempt = getattr(
        _CLOSE_ATTEMPT_LOCAL,
        "current",
        None,
    )
    _CLOSE_ATTEMPT_LOCAL.current = attempt
    try:
        _close_owned_descriptor(ownership[0])
    except OSError:
        if attempt.completed_successfully:
            _record_consumed_slot(ownership)
            raise
        _QUARANTINED_DESCRIPTOR_OWNERSHIPS.discard(ownership)
        return False
    except BaseException:
        if attempt.completed_successfully:
            _record_consumed_slot(ownership)
        else:
            _QUARANTINED_DESCRIPTOR_OWNERSHIPS.discard(
                ownership
            )
        raise
    else:
        _record_consumed_slot(ownership)
        return True
    finally:
        if previous_attempt is None:
            del _CLOSE_ATTEMPT_LOCAL.current
        else:
            _CLOSE_ATTEMPT_LOCAL.current = previous_attempt


def _forget_owned_record(kind: str, ownership) -> bool:
    pending, tracked = _ownership_state(kind)
    tracked.discard(ownership)
    pending.discard(ownership)
    if kind == "lease":
        _LEASE_REFS.pop(ownership[1], None)
    _CONSUMED_DESCRIPTOR_OWNERSHIPS.discard(ownership)
    _QUARANTINED_DESCRIPTOR_OWNERSHIPS.discard(ownership)
    return True


def _queue_cleanup(kind: str, ownership) -> None:
    _CLEANUP_QUEUE.put((kind, ownership))


def _block_all_blockable_signals():
    if not (
        hasattr(signal, "pthread_sigmask")
        and hasattr(signal, "valid_signals")
    ):
        raise RuntimeError("POSIX signal masking is unavailable")
    blocked = set(signal.valid_signals())
    blocked.discard(signal.SIGKILL)
    blocked.discard(signal.SIGSTOP)
    return signal.pthread_sigmask(signal.SIG_BLOCK, blocked)


def _background_pending_cleanup() -> None:
    try:
        _block_all_blockable_signals()
    except (OSError, RuntimeError, ValueError):
        return
    retry_delay = 0.001
    while True:
        kind, ownership = _CLEANUP_QUEUE.get()
        crashed = None
        closed = False
        try:
            reader = _FORK_FD_LIFECYCLE_GATE.try_enter_audit()
            if reader is not None:
                try:
                    try:
                        with _ownership_cleanup(
                            kind,
                            ownership,
                        ) as admission:
                            closed = _close_owned_record(
                                kind,
                                ownership,
                            )
                            if not closed:
                                admission.retain()
                    except Exception:
                        closed = False
                finally:
                    try:
                        _FORK_FD_LIFECYCLE_GATE.exit_audit(
                            reader
                        )
                    finally:
                        (
                            _FORK_FD_LIFECYCLE_GATE
                            .ensure_audit_released(reader)
                        )
        except BaseException as error:
            crashed = error
        if crashed is not None:
            _queue_cleanup(kind, ownership)
            if _handoff_cleanup_worker():
                raise crashed
            time.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 0.05)
            continue
        if closed:
            retry_delay = 0.001
            continue
        _queue_cleanup(kind, ownership)
        time.sleep(retry_delay)
        retry_delay = min(retry_delay * 2, 0.05)


def _schedule_pending_cleanup(kind: str, ownership) -> None:
    pending, _ = _ownership_state(kind)
    try:
        pending.add(ownership)
        _queue_cleanup(kind, ownership)
        _ensure_cleanup_worker()
    except BaseException:
        try:
            try:
                pending.add(ownership)
            finally:
                try:
                    _queue_cleanup(kind, ownership)
                finally:
                    _ensure_cleanup_worker()
        except BaseException:
            pass
        raise


def _ensure_cleanup_worker() -> bool:
    global _CLEANUP_THREAD
    if not _CLEANUP_SUPERVISOR_LOCK.acquire(timeout=0.005):
        return bool(
            _CLEANUP_THREAD is not None
            and _CLEANUP_THREAD.is_alive()
        )
    try:
        if (
            _CLEANUP_THREAD is not None
            and _CLEANUP_THREAD.is_alive()
        ):
            return True
        return _start_cleanup_worker_locked()
    finally:
        _CLEANUP_SUPERVISOR_LOCK.release()


def _start_cleanup_worker_locked() -> bool:
    global _CLEANUP_THREAD
    for _ in range(2):
        worker = threading.Thread(
            target=_background_pending_cleanup,
            daemon=True,
            name="audit-fd-cleanup",
        )
        _CLEANUP_THREAD = worker
        try:
            worker.start()
        except RuntimeError:
            _CLEANUP_THREAD = None
            continue
        return True
    return False


def _handoff_cleanup_worker() -> bool:
    global _CLEANUP_THREAD
    current = threading.current_thread()
    if not _CLEANUP_SUPERVISOR_LOCK.acquire(timeout=0.005):
        return False
    try:
        if _CLEANUP_THREAD is not current:
            return bool(
                _CLEANUP_THREAD is not None
                and _CLEANUP_THREAD.is_alive()
            )
        _CLEANUP_THREAD = None
        if _start_cleanup_worker_locked():
            return True
        _CLEANUP_THREAD = current
        return False
    finally:
        _CLEANUP_SUPERVISOR_LOCK.release()


@contextmanager
def _audit_fd_lifecycle():
    reader = _FORK_FD_LIFECYCLE_GATE.try_enter_audit()
    if reader is None:
        raise SessionBusyError("fork descriptor lifecycle is active")
    try:
        yield
    finally:
        try:
            _FORK_FD_LIFECYCLE_GATE.exit_audit(reader)
        finally:
            _FORK_FD_LIFECYCLE_GATE.ensure_audit_released(reader)


def _rename_noreplace(
    source_directory: int,
    source_name: str,
    target_directory: int,
    target_name: str,
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameat2 = libc.renameat2
    except AttributeError as error:
        raise SessionIntegrityError(
            "atomic no-replace claim publication is unavailable"
        ) from error
    renameat2.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    renameat2.restype = ctypes.c_int
    result = renameat2(
        source_directory,
        os.fsencode(source_name),
        target_directory,
        os.fsencode(target_name),
        RENAME_NOREPLACE,
    )
    if result != 0:
        number = ctypes.get_errno()
        raise OSError(number, os.strerror(number), target_name)


@contextmanager
def _successor_transition_lock(key):
    with _SUCCESSOR_LOCKS_GUARD:
        entry = _SUCCESSOR_LOCKS.get(key)
        if entry is None:
            entry = [threading.Lock(), 0]
            _SUCCESSOR_LOCKS[key] = entry
        entry[1] += 1
    lock = entry[0]
    acquired = lock.acquire(blocking=False)
    if not acquired:
        with _SUCCESSOR_LOCKS_GUARD:
            entry[1] -= 1
            if entry[1] == 0 and _SUCCESSOR_LOCKS.get(key) is entry:
                del _SUCCESSOR_LOCKS[key]
        raise SessionBusyError(
            "generation successor transition is active"
        )
    try:
        yield
    finally:
        lock.release()
        with _SUCCESSOR_LOCKS_GUARD:
            entry[1] -= 1
            if entry[1] == 0 and _SUCCESSOR_LOCKS.get(key) is entry:
                del _SUCCESSOR_LOCKS[key]


class SessionIntegrityError(RuntimeError):
    """Raised when a session component or generation is not trustworthy."""


class ClaimedResponseError(SessionIntegrityError):
    """Raised after a generation was irreversibly claimed for a bad response."""

    def __init__(self, message: str, lease=None):
        super().__init__(message)
        self.lease = lease


class GenerationConsumedError(SessionIntegrityError):
    """Raised when a generation claim already exists."""


class SessionBusyError(SessionIntegrityError):
    """Raised when another process owns the live claim transition."""


_ensure_cleanup_worker()


class ClaimLease:
    """Process-scoped capability proving ownership of one claimed transition."""

    def __init__(self, owner, run_id: str, digest: str, descriptor: int):
        cleanup_ownership = None
        try:
            self.closed = True
            self._descriptor = -1
            _require_kernel_fd(descriptor)
            self._owner = owner
            self._creator_pid = os.getpid()
            self.run_id = run_id
            self.digest = digest
            self._descriptor = descriptor
            cleanup_ownership = _claim_constructor_ownership(
                owner,
                descriptor,
            )
            with _audit_fd_lifecycle(), _ownership_publication():
                if not isinstance(owner, SessionStore):
                    raise SessionIntegrityError(
                        "claim lease owner is invalid"
                    )
                ownership = owner._tracked_claim_ownerships.get(
                    descriptor
                )
                if ownership is None:
                    raise SessionIntegrityError(
                        "claim descriptor was not opened by this store"
                    )
                if ownership is not cleanup_ownership:
                    raise SessionIntegrityError(
                        "claim descriptor ownership changed during binding"
                    )
                ownerships = [
                    candidate
                    for candidate in _TRACKED_LEASE_OWNERSHIPS
                    if candidate[0] == descriptor
                ]
                if ownerships != [ownership]:
                    raise SessionIntegrityError(
                        "claim descriptor ownership is ambiguous"
                    )
                self._tracking_token = ownership[1]
                cleanup_ownership = ownership
                _LEASE_REFS[self._tracking_token] = weakref.ref(self)
                owner._tracked_claim_ownerships.pop(
                    descriptor,
                    None,
                )
                self.closed = False
        except BaseException:
            if cleanup_ownership is None:
                cleanup_ownership = (
                    _exact_claim_store_ownership(
                        owner,
                        descriptor,
                    )
                )
            if cleanup_ownership is not None:
                self._descriptor = -1
                self.closed = True
                try:
                    try:
                        if (
                            owner._tracked_claim_ownerships.get(
                                descriptor
                            )
                            is cleanup_ownership
                        ):
                            owner._tracked_claim_ownerships.pop(
                                descriptor,
                                None,
                            )
                    finally:
                        _schedule_pending_cleanup(
                            "lease",
                            cleanup_ownership,
                        )
                except BaseException:
                    pass
            raise

    def close(self) -> None:
        if self.closed:
            return
        descriptor = self._descriptor
        token = self._tracking_token
        ownership = (descriptor, token)
        self._descriptor = -1
        self.closed = True
        _schedule_pending_cleanup("lease", ownership)

    def __del__(self):
        try:
            self.close()
        except BaseException:
            pass


def _claim_constructor_ownership(owner, descriptor):
    return _exact_claim_store_ownership(owner, descriptor)


def _exact_claim_store_ownership(owner, descriptor):
    if not isinstance(owner, SessionStore):
        return None
    try:
        ownership = owner._tracked_claim_ownerships.get(
            descriptor
        )
    except (AttributeError, TypeError):
        return None
    if ownership is None:
        return None
    try:
        if (
            ownership[0] != descriptor
            or ownership not in _TRACKED_LEASE_OWNERSHIPS
        ):
            return None
    except (IndexError, TypeError):
        return None
    return ownership


def _before_fork() -> None:
    _FORK_FD_LIFECYCLE_GATE.before_fork()


def _after_fork_parent() -> None:
    _FORK_FD_LIFECYCLE_GATE.after_parent_reopen()


def _close_child_snapshot(ownerships) -> set:
    failed = set()
    for ownership in ownerships:
        if ownership in _CONSUMED_DESCRIPTOR_OWNERSHIPS:
            continue
        if ownership in _QUARANTINED_DESCRIPTOR_OWNERSHIPS:
            failed.add(ownership)
            continue
        completed = False
        for _ in range(2):
            try:
                consumed = _consume_owned_slot(ownership)
            except BaseException:
                if (
                    ownership
                    in _CONSUMED_DESCRIPTOR_OWNERSHIPS
                ):
                    completed = True
                    break
                if (
                    ownership
                    in _QUARANTINED_DESCRIPTOR_OWNERSHIPS
                ):
                    break
                continue
            if consumed:
                completed = True
                break
        if not completed:
            failed.add(ownership)
    return failed


def _after_fork_child() -> None:
    global _SUCCESSOR_LOCKS_GUARD
    global _SUCCESSOR_LOCKS
    global _FORK_FD_LIFECYCLE_GATE
    global _DESCRIPTOR_OWNERSHIP_GATE
    global _TRACKED_LEASE_OWNERSHIPS
    global _LEASE_REFS
    global _TRACKED_TRANSACTION_OWNERSHIPS
    global _PENDING_LEASE_CLOSE_FDS
    global _PENDING_TRANSACTION_CLOSE_FDS
    global _CONSUMED_DESCRIPTOR_OWNERSHIPS
    global _QUARANTINED_DESCRIPTOR_OWNERSHIPS
    global _CLEANUP_QUEUE
    global _CLEANUP_THREAD
    global _CLEANUP_SUPERVISOR_LOCK
    global _CLOSE_ATTEMPT_LOCAL

    inherited_quarantines = set(
        _QUARANTINED_DESCRIPTOR_OWNERSHIPS
    )
    previous_signal_mask = None
    signals_blocked = False
    failed_leases = set(_TRACKED_LEASE_OWNERSHIPS)
    failed_transactions = set(
        _TRACKED_TRANSACTION_OWNERSHIPS
    )
    try:
        previous_signal_mask = _block_all_blockable_signals()
        signals_blocked = True
        failed_leases = _close_child_snapshot(
            _TRACKED_LEASE_OWNERSHIPS
        )
        failed_transactions = _close_child_snapshot(
            _TRACKED_TRANSACTION_OWNERSHIPS
        )
    finally:
        try:
            for reference in _LEASE_REFS.values():
                lease = reference()
                if lease is not None:
                    lease._descriptor = -1
                    lease._creator_pid = -1
                    lease.closed = True
            _SUCCESSOR_LOCKS_GUARD = threading.Lock()
            _SUCCESSOR_LOCKS = {}
            _FORK_FD_LIFECYCLE_GATE = _ForkLifecycleGate()
            _DESCRIPTOR_OWNERSHIP_GATE = (
                _DescriptorOwnershipGate()
            )
            _TRACKED_LEASE_OWNERSHIPS = failed_leases
            _LEASE_REFS = {}
            _TRACKED_TRANSACTION_OWNERSHIPS = (
                failed_transactions
            )
            _PENDING_LEASE_CLOSE_FDS = set(failed_leases)
            _PENDING_TRANSACTION_CLOSE_FDS = set(
                failed_transactions
            )
            _CONSUMED_DESCRIPTOR_OWNERSHIPS = set()
            _QUARANTINED_DESCRIPTOR_OWNERSHIPS = (
                inherited_quarantines
                & (failed_leases | failed_transactions)
            )
            _CLEANUP_QUEUE = queue.SimpleQueue()
            _CLEANUP_THREAD = None
            _CLEANUP_SUPERVISOR_LOCK = threading.Lock()
            _CLOSE_ATTEMPT_LOCAL = threading.local()
            for ownership in failed_leases:
                _queue_cleanup("lease", ownership)
            for ownership in failed_transactions:
                _queue_cleanup("transaction", ownership)
        finally:
            if signals_blocked:
                signal.pthread_sigmask(
                    signal.SIG_SETMASK,
                    previous_signal_mask,
                )


if hasattr(os, "register_at_fork"):
    os.register_at_fork(
        before=_before_fork,
        after_in_parent=_after_fork_parent,
        after_in_child=_after_fork_child,
    )


@dataclass(frozen=True)
class SessionGeneration:
    token: str
    packet_path: Path
    packet_sha256: str
    response_path: Path


def _canonical_json(value) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _owned(metadata, *, directory: bool) -> None:
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(metadata.st_mode):
        raise SessionIntegrityError("session component has the wrong type")
    if metadata.st_uid != os.geteuid():
        raise SessionIntegrityError("session component has the wrong owner")


class SessionStore:
    """Use owned no-follow directory descriptors for every trusted operation."""

    def __init__(self, root: Path):
        self.root = Path(os.path.abspath(root))
        self._creator_pid = os.getpid()
        self._tracked_claim_ownerships = {}

    def _require_current_process(self) -> None:
        if self._creator_pid != os.getpid():
            raise SessionIntegrityError(
                "session store cannot be used after fork"
            )

    def _parse_token(self, token: str) -> tuple[str, str]:
        if not isinstance(token, str):
            raise SessionIntegrityError("session token must be text")
        match = TOKEN_RE.fullmatch(token)
        if match is None:
            raise SessionIntegrityError("invalid session token")
        return match.groups()

    def _open_directory(self, name, *, dir_fd=None) -> int:
        try:
            descriptor = os.open(name, DIRECTORY_FLAGS, dir_fd=dir_fd)
        except OSError as error:
            raise SessionIntegrityError(
                "session directory is unavailable or unsafe"
            ) from error
        try:
            _owned(os.fstat(descriptor), directory=True)
            return descriptor
        except Exception:
            os.close(descriptor)
            raise

    def _open_tracked_claim_directory(self, name, *, dir_fd) -> int:
        ownership = None
        try:
            with _audit_fd_lifecycle():
                if not _ensure_cleanup_worker():
                    raise SessionBusyError(
                        "descriptor cleanup executor is unavailable"
                    )
                with _ownership_publication():
                    descriptor = self._open_directory(
                        name,
                        dir_fd=dir_fd,
                    )
                    ownership = (descriptor, object())
                    _TRACKED_LEASE_OWNERSHIPS.add(ownership)
                    self._tracked_claim_ownerships[
                        descriptor
                    ] = ownership
                    return descriptor
        except BaseException:
            if ownership is not None:
                if (
                    self._tracked_claim_ownerships.get(descriptor)
                    == ownership
                ):
                    self._tracked_claim_ownerships.pop(
                        descriptor,
                        None,
                    )
                _schedule_pending_cleanup("lease", ownership)
            raise

    def _close_tracked_claim_descriptor(self, descriptor: int) -> None:
        ownership = self._tracked_claim_ownerships.pop(
            descriptor,
            None,
        )
        if ownership is None:
            return
        _schedule_pending_cleanup("lease", ownership)

    def _open_base(self, *, create: bool) -> int:
        self._require_current_process()
        if create:
            try:
                self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
            except OSError as error:
                raise SessionIntegrityError(
                    "cannot create session base"
                ) from error
        return self._open_directory(self.root)

    @contextmanager
    def _run_directories(self, run_id: str):
        descriptors = []
        try:
            root = self._open_base(create=False)
            descriptors.append(root)
            run = self._open_directory(run_id, dir_fd=root)
            descriptors.append(run)
            generations = self._open_directory(
                "generations",
                dir_fd=run,
            )
            descriptors.append(generations)
            claims = self._open_directory("claims", dir_fd=run)
            descriptors.append(claims)
            inbox = self._open_directory("inbox", dir_fd=run)
            descriptors.append(inbox)
            values = {
                "root": root,
                "run": run,
                "generations": generations,
                "claims": claims,
                "inbox": inbox,
            }
            root_path = Path(f"/proc/self/fd/{root}").resolve()
            run_path = Path(f"/proc/self/fd/{run}").resolve()
            if run_path.parent != root_path:
                raise SessionIntegrityError(
                    "session run escaped the session base"
                )
            for name in ("generations", "claims", "inbox"):
                child = Path(f"/proc/self/fd/{values[name]}").resolve()
                if child.parent != run_path:
                    raise SessionIntegrityError(
                        "session directory escaped the run root"
                    )
            yield values
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)

    def _new_run(self) -> str:
        root = self._open_base(create=True)
        try:
            for _ in range(100):
                run_id = secrets.token_hex(16)
                try:
                    os.mkdir(run_id, mode=0o700, dir_fd=root)
                except FileExistsError:
                    continue
                run = self._open_directory(run_id, dir_fd=root)
                try:
                    os.fchmod(run, 0o700)
                    for name in ("generations", "claims", "inbox"):
                        os.mkdir(name, mode=0o700, dir_fd=run)
                    key_descriptor = os.open(
                        "key",
                        os.O_WRONLY
                        | os.O_CREAT
                        | os.O_EXCL
                        | os.O_NOFOLLOW
                        | os.O_CLOEXEC,
                        0o400,
                        dir_fd=run,
                    )
                    try:
                        os.fchmod(key_descriptor, 0o400)
                        key = secrets.token_bytes(32)
                        position = 0
                        while position < len(key):
                            position += os.write(
                                key_descriptor,
                                key[position:],
                            )
                        os.fsync(key_descriptor)
                    finally:
                        os.close(key_descriptor)
                finally:
                    os.close(run)
                return run_id
        except OSError as error:
            raise SessionIntegrityError("cannot allocate audit run") from error
        finally:
            os.close(root)
        raise SessionIntegrityError("cannot allocate audit run")

    def _read_file(
        self,
        directory: int,
        name: str,
        *,
        expected_mode: int | None = None,
        byte_limit: int | None = None,
        nonblocking: bool = False,
    ) -> bytes:
        try:
            descriptor = os.open(
                name,
                READ_FLAGS | (os.O_NONBLOCK if nonblocking else 0),
                dir_fd=directory,
            )
        except OSError as error:
            raise SessionIntegrityError(
                "generation file is unavailable or unsafe"
            ) from error
        try:
            metadata = os.fstat(descriptor)
            _owned(metadata, directory=False)
            if (
                expected_mode is not None
                and stat.S_IMODE(metadata.st_mode) != expected_mode
            ):
                raise SessionIntegrityError(
                    "session file permissions are invalid"
                )
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, 65536)
                if not chunk:
                    return b"".join(chunks)
                total += len(chunk)
                if byte_limit is not None and total > byte_limit:
                    raise SessionIntegrityError(
                        "session response exceeds the byte limit"
                    )
                chunks.append(chunk)
        finally:
            os.close(descriptor)

    def _write_file(
        self,
        directory: int,
        name: str,
        value: bytes,
    ) -> None:
        descriptor = os.open(
            name,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o400,
            dir_fd=directory,
        )
        try:
            os.fchmod(descriptor, 0o400)
            position = 0
            while position < len(value):
                position += os.write(descriptor, value[position:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def _key(self, run: int) -> bytes:
        key = self._read_file(run, "key", expected_mode=0o400)
        if len(key) != 32:
            raise SessionIntegrityError("run authentication key is invalid")
        return key

    def _manifest_value(
        self,
        key: bytes,
        state_bytes: bytes,
        packet_bytes: bytes,
        state_digest: str,
        packet_digest: str,
        previous_digest: str | None,
    ) -> dict[str, object]:
        chain = {
            "schema_version": 1,
            "state_sha256": state_digest,
            "packet_sha256": packet_digest,
            "previous_generation_sha256": previous_digest,
        }
        signature = hmac.new(
            key,
            _canonical_json(chain) + state_bytes + packet_bytes,
            hashlib.sha256,
        ).hexdigest()
        return {**chain, "hmac_sha256": signature}

    def _validate_values(self, state, packet) -> None:
        if (
            not isinstance(state, dict)
            or state.get("schema_version") != 1
            or not isinstance(state.get("phase"), str)
            or not state["phase"]
            or not isinstance(state.get("target"), str)
            or not state["target"]
            or isinstance(state.get("absolute_deadline"), bool)
            or not isinstance(state.get("absolute_deadline"), (int, float))
            or not math.isfinite(state["absolute_deadline"])
            or not isinstance(state.get("nonce"), str)
            or re.fullmatch(r"[0-9a-f]{32}", state["nonce"]) is None
            or not isinstance(state.get("packet_sha256"), str)
            or re.fullmatch(
                r"[0-9a-f]{64}",
                state["packet_sha256"],
            )
            is None
        ):
            raise SessionIntegrityError("state schema is invalid")
        if (
            not isinstance(packet, dict)
            or packet.get("schema_version") != 1
            or not isinstance(packet.get("kind"), str)
            or not packet["kind"]
        ):
            raise SessionIntegrityError("packet schema is invalid")
        request_id = state.get("request_id")
        request_digest = state.get("request_manifest_sha256")
        if (request_id is None) != (request_digest is None):
            raise SessionIntegrityError("request binding is incomplete")
        if request_id is not None:
            if (
                not isinstance(request_id, str)
                or re.fullmatch(r"[0-9a-f]{64}", request_id) is None
                or not isinstance(request_digest, str)
                or re.fullmatch(r"[0-9a-f]{64}", request_digest) is None
            ):
                raise SessionIntegrityError("request binding is invalid")
            packet_request = packet.get("request")
            if packet.get("kind") != "terminal" and packet_request != {
                "id": request_id,
                "manifest_sha256": request_digest,
            }:
                raise SessionIntegrityError(
                    "packet request binding does not match session state"
                )

    def _response_name(self, state: Mapping[str, object]) -> str:
        response_name = state.get("response_name")
        if (
            not isinstance(response_name, str)
            or RESPONSE_RE.fullmatch(response_name) is None
        ):
            raise SessionIntegrityError("state has an invalid response name")
        return response_name

    def _require_response_absent(
        self,
        inbox: int,
        response_name: str,
    ) -> None:
        try:
            os.stat(
                response_name,
                dir_fd=inbox,
                follow_symlinks=False,
            )
        except FileNotFoundError:
            return
        except OSError as error:
            raise SessionIntegrityError(
                "cannot verify issued response path"
            ) from error
        raise SessionIntegrityError(
            "issued response name already exists in the inbox"
        )

    def _resolved_run_paths(
        self,
        directories,
        generation_digest: str,
        response_name: str,
    ) -> tuple[Path, Path]:
        run = Path(f"/proc/self/fd/{directories['run']}").resolve()
        generations = Path(
            f"/proc/self/fd/{directories['generations']}"
        ).resolve()
        inbox = Path(f"/proc/self/fd/{directories['inbox']}").resolve()
        if generations.parent != run or inbox.parent != run:
            raise SessionIntegrityError(
                "session directories escaped the resolved run root"
            )
        packet = generations / generation_digest / "packet.json"
        response = inbox / response_name
        if not packet.is_relative_to(run) or not response.is_relative_to(run):
            raise SessionIntegrityError(
                "session result path escaped the resolved run root"
            )
        return packet, response

    def _write_generation(
        self,
        run_id: str,
        state: Mapping[str, object],
        packet: Mapping[str, object],
        previous_digest: str | None,
    ) -> SessionGeneration:
        (
            state_value,
            packet_value,
            state_bytes,
            packet_bytes,
            state_digest,
            packet_digest,
            response_name,
        ) = self._prepared_generation(state, packet)
        temporary_name = f".{state_digest}-{secrets.token_hex(8)}"
        issued_response_names = set()
        if previous_digest is not None:
            self._load_verified(
                run_id,
                previous_digest,
                verify_previous=True,
                response_names=issued_response_names,
            )
        if response_name in issued_response_names:
            raise SessionIntegrityError(
                "response name was already issued in this generation chain"
            )
        with self._run_directories(run_id) as directories:
            self._require_response_absent(
                directories["inbox"],
                response_name,
            )
            key = self._key(directories["run"])
            manifest = self._manifest_value(
                key,
                state_bytes,
                packet_bytes,
                state_digest,
                packet_digest,
                previous_digest,
            )
            try:
                os.mkdir(
                    temporary_name,
                    mode=0o700,
                    dir_fd=directories["generations"],
                )
                temporary = self._open_directory(
                    temporary_name,
                    dir_fd=directories["generations"],
                )
                try:
                    os.fchmod(temporary, 0o700)
                    self._write_file(temporary, "state.json", state_bytes)
                    self._write_file(temporary, "packet.json", packet_bytes)
                    self._write_file(
                        temporary,
                        "manifest.json",
                        _canonical_json(manifest),
                    )
                    os.fsync(temporary)
                finally:
                    os.close(temporary)
                os.rename(
                    temporary_name,
                    state_digest,
                    src_dir_fd=directories["generations"],
                    dst_dir_fd=directories["generations"],
                )
                os.fsync(directories["generations"])
            except OSError as error:
                raise SessionIntegrityError(
                    "cannot append immutable generation"
                ) from error
            packet_path, response_path = self._resolved_run_paths(
                directories,
                state_digest,
                response_name,
            )
        return SessionGeneration(
            token=f"{run_id}.{state_digest}",
            packet_path=packet_path,
            packet_sha256=packet_digest,
            response_path=response_path,
        )

    def _prepared_generation(self, state, packet):
        packet_value = dict(packet)
        if packet_value.get("schema_version") != 1:
            raise SessionIntegrityError("packet schema version is invalid")
        packet_bytes = _canonical_json(packet_value)
        packet_digest = _digest(packet_bytes)
        state_value = dict(state)
        if state_value.get("schema_version") != 1:
            raise SessionIntegrityError("state schema version is invalid")
        state_value["packet_sha256"] = packet_digest
        response_name = self._response_name(state_value)
        self._validate_values(state_value, packet_value)
        state_bytes = _canonical_json(state_value)
        state_digest = _digest(state_bytes)
        return (
            state_value,
            packet_value,
            state_bytes,
            packet_bytes,
            state_digest,
            packet_digest,
            response_name,
        )

    def create(
        self,
        state: Mapping[str, object],
        packet: Mapping[str, object],
    ) -> SessionGeneration:
        run_id = self._new_run()
        return self._write_generation(run_id, state, packet, None)

    def _load_verified(
        self,
        run_id: str,
        expected_digest: str,
        *,
        verify_previous: bool,
        response_names: set[str] | None = None,
    ) -> dict:
        if response_names is None:
            response_names = set()
        with self._run_directories(run_id) as directories:
            generation = self._open_directory(
                expected_digest,
                dir_fd=directories["generations"],
            )
            try:
                state_bytes = self._read_file(
                    generation,
                    "state.json",
                    expected_mode=0o400,
                )
                packet_bytes = self._read_file(
                    generation,
                    "packet.json",
                    expected_mode=0o400,
                )
                manifest_bytes = self._read_file(
                    generation,
                    "manifest.json",
                    expected_mode=0o400,
                )
            finally:
                os.close(generation)
            key = self._key(directories["run"])
            try:
                state = json.loads(state_bytes)
                packet = json.loads(packet_bytes)
                manifest = json.loads(manifest_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise SessionIntegrityError(
                    "generation JSON is invalid"
                ) from error
            if not isinstance(manifest, dict):
                raise SessionIntegrityError(
                    "generation manifest is invalid"
                )
            if (
                not isinstance(state, dict)
                or not isinstance(packet, dict)
                or state.get("schema_version") != 1
                or packet.get("schema_version") != 1
                or state_bytes != _canonical_json(state)
                or packet_bytes != _canonical_json(packet)
            ):
                raise SessionIntegrityError(
                    "generation state or packet is noncanonical"
                )
            self._validate_values(state, packet)
            state_digest = _digest(state_bytes)
            packet_digest = _digest(packet_bytes)
            if (
                state_digest != expected_digest
                or state.get("packet_sha256") != packet_digest
            ):
                raise SessionIntegrityError("generation digest mismatch")
            previous = manifest.get("previous_generation_sha256")
            if previous is not None and (
                not isinstance(previous, str)
                or re.fullmatch(r"[0-9a-f]{64}", previous) is None
            ):
                raise SessionIntegrityError(
                    "previous generation digest is invalid"
                )
            expected_manifest = self._manifest_value(
                key,
                state_bytes,
                packet_bytes,
                state_digest,
                packet_digest,
                previous,
            )
            if (
                manifest != expected_manifest
                or manifest_bytes != _canonical_json(expected_manifest)
            ):
                raise SessionIntegrityError(
                    "generation authentication failed"
                )
            response_name = self._response_name(state)
            if response_name in response_names:
                raise SessionIntegrityError(
                    "generation chain reuses an issued response name"
                )
            response_names.add(response_name)
            self._resolved_run_paths(
                directories,
                expected_digest,
                response_name,
            )
        if verify_previous and previous is not None:
            self._load_verified(
                run_id,
                previous,
                verify_previous=True,
                response_names=response_names,
            )
        return state

    def load(self, token: str) -> dict:
        run_id, digest = self._parse_token(token)
        return self._load_verified(run_id, digest, verify_previous=True)

    def load_packet(self, token: str) -> dict:
        run_id, digest = self._parse_token(token)
        state = self._load_verified(
            run_id,
            digest,
            verify_previous=True,
        )
        with self._run_directories(run_id) as directories:
            generation = self._open_directory(
                digest,
                dir_fd=directories["generations"],
            )
            try:
                packet_bytes = self._read_file(
                    generation,
                    "packet.json",
                    expected_mode=0o400,
                )
            finally:
                os.close(generation)
        try:
            packet = json.loads(packet_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SessionIntegrityError(
                "generation packet JSON is invalid"
            ) from error
        if (
            not isinstance(packet, dict)
            or packet_bytes != _canonical_json(packet)
            or _digest(packet_bytes) != state["packet_sha256"]
        ):
            raise SessionIntegrityError(
                "generation packet digest mismatch"
            )
        return packet

    def _new_claim_lease(self, run_id: str, digest: str) -> ClaimLease:
        temporary_name = f".{digest}-{secrets.token_hex(8)}"
        claim = None
        published = False
        with self._run_directories(run_id) as directories:
            try:
                os.mkdir(
                    temporary_name,
                    mode=0o700,
                    dir_fd=directories["claims"],
                )
                claim = self._open_tracked_claim_directory(
                    temporary_name,
                    dir_fd=directories["claims"],
                )
                os.fchmod(claim, 0o700)
                self._write_file(claim, "lease", CLAIM_MARKER)
                self._write_file(
                    claim,
                    "transaction",
                    TRANSACTION_MARKER,
                )
                os.fsync(claim)
                fcntl.flock(claim, fcntl.LOCK_EX | fcntl.LOCK_NB)
                try:
                    _rename_noreplace(
                        directories["claims"],
                        temporary_name,
                        directories["claims"],
                        digest,
                    )
                except OSError as error:
                    if error.errno in (errno.EEXIST, errno.ENOTEMPTY):
                        raise GenerationConsumedError(
                            "generation was already consumed"
                        ) from error
                    raise
                published = True
                os.fsync(directories["claims"])
                lease = ClaimLease(self, run_id, digest, claim)
                claim = None
                return lease
            except GenerationConsumedError:
                raise
            except OSError as error:
                raise SessionIntegrityError(
                    "cannot claim generation"
                ) from error
            finally:
                if not published:
                    if claim is not None:
                        for marker_name in ("lease", "transaction"):
                            try:
                                os.unlink(marker_name, dir_fd=claim)
                            except FileNotFoundError:
                                pass
                        self._close_tracked_claim_descriptor(claim)
                    try:
                        os.rmdir(
                            temporary_name,
                            dir_fd=directories["claims"],
                        )
                    except FileNotFoundError:
                        pass
                elif claim is not None:
                    self._close_tracked_claim_descriptor(claim)

    def _existing_claim_lease(
        self,
        run_id: str,
        digest: str,
    ) -> ClaimLease:
        with self._run_directories(run_id) as directories:
            claim = self._open_tracked_claim_directory(
                digest,
                dir_fd=directories["claims"],
            )
            try:
                try:
                    fcntl.flock(
                        claim,
                        fcntl.LOCK_EX | fcntl.LOCK_NB,
                    )
                except BlockingIOError as error:
                    raise SessionBusyError(
                        "generation transition is active"
                    ) from error
                marker = self._read_file(
                    claim,
                    "lease",
                    expected_mode=0o400,
                )
                if marker != CLAIM_MARKER:
                    raise SessionIntegrityError(
                        "claim lease marker is invalid"
                    )
                transaction_marker = self._read_file(
                    claim,
                    "transaction",
                    expected_mode=0o400,
                )
                if transaction_marker != TRANSACTION_MARKER:
                    raise SessionIntegrityError(
                        "claim transaction marker is invalid"
                    )
                return ClaimLease(self, run_id, digest, claim)
            except Exception:
                self._close_tracked_claim_descriptor(claim)
                raise

    def _require_claim_lease(
        self,
        token: str,
        lease: ClaimLease,
    ) -> tuple[str, str, tuple[int, int]]:
        run_id, digest = self._parse_token(token)
        current_pid = os.getpid()
        if (
            not isinstance(lease, ClaimLease)
            or self._creator_pid != current_pid
            or lease._creator_pid != current_pid
            or lease._owner is not self
            or lease.run_id != run_id
            or lease.digest != digest
            or lease.closed
        ):
            raise SessionIntegrityError(
                "claimed append requires the live owning lease"
            )
        with _ownership_publication():
            if (
                lease._descriptor,
                lease._tracking_token,
            ) not in _TRACKED_LEASE_OWNERSHIPS:
                raise SessionIntegrityError(
                    "claimed append requires the tracked owning lease"
                )
        try:
            descriptor_metadata = os.fstat(lease._descriptor)
            _owned(descriptor_metadata, directory=True)
            with self._run_directories(run_id) as directories:
                published = self._open_directory(
                    digest,
                    dir_fd=directories["claims"],
                )
                try:
                    published_metadata = os.fstat(published)
                    if (
                        descriptor_metadata.st_dev,
                        descriptor_metadata.st_ino,
                    ) != (
                        published_metadata.st_dev,
                        published_metadata.st_ino,
                    ):
                        raise SessionIntegrityError(
                            "claim lease is not bound to the published claim"
                        )
                finally:
                    os.close(published)
            marker = self._read_file(
                lease._descriptor,
                "lease",
                expected_mode=0o400,
            )
            if marker != CLAIM_MARKER:
                raise SessionIntegrityError(
                    "claim lease marker is invalid"
                )
            try:
                fcntl.flock(
                    lease._descriptor,
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            except BlockingIOError as error:
                raise SessionBusyError(
                    "generation transition is active"
                ) from error
        except (OSError, TypeError) as error:
            raise SessionIntegrityError(
                "claim lease is no longer live"
            ) from error
        claim_identity = (
            descriptor_metadata.st_dev,
            descriptor_metadata.st_ino,
        )
        return run_id, digest, claim_identity

    @contextmanager
    def _successor_transaction_lock(self, lease: ClaimLease):
        self._require_current_process()
        ownership = None
        try:
            with _audit_fd_lifecycle():
                if not _ensure_cleanup_worker():
                    raise SessionBusyError(
                        "descriptor cleanup executor is unavailable"
                    )
                with _ownership_publication():
                    try:
                        descriptor = os.open(
                            "transaction",
                            READ_FLAGS,
                            dir_fd=lease._descriptor,
                        )
                    except OSError as error:
                        raise SessionIntegrityError(
                            "claim transaction lock is unavailable or unsafe"
                        ) from error
                    token = object()
                    ownership = (descriptor, token)
                    _TRACKED_TRANSACTION_OWNERSHIPS.add(
                        ownership
                    )
        except BaseException:
            if ownership is not None:
                _schedule_pending_cleanup(
                    "transaction",
                    ownership,
                )
            raise
        try:
            try:
                metadata = os.fstat(descriptor)
                _owned(metadata, directory=False)
                if stat.S_IMODE(metadata.st_mode) != 0o400:
                    raise SessionIntegrityError(
                        "claim transaction lock permissions are invalid"
                    )
                marker = os.read(
                    descriptor,
                    len(TRANSACTION_MARKER) + 1,
                )
                if marker != TRANSACTION_MARKER:
                    raise SessionIntegrityError(
                        "claim transaction marker is invalid"
                    )
                fcntl.flock(
                    descriptor,
                    fcntl.LOCK_EX | fcntl.LOCK_NB,
                )
            except BlockingIOError as error:
                raise SessionBusyError(
                    "generation successor transaction is active"
                ) from error
            except OSError as error:
                raise SessionIntegrityError(
                    "claim transaction lock is no longer live"
                ) from error
            yield
        finally:
            _schedule_pending_cleanup(
                "transaction",
                ownership,
            )

    def claim_lease(self, token: str) -> ClaimLease:
        run_id, digest = self._parse_token(token)
        self.load(token)
        return self._new_claim_lease(run_id, digest)

    def claim(self, token: str) -> None:
        lease = self.claim_lease(token)
        lease.close()

    def claim_and_read(
        self,
        token: str,
        response_path: Path,
    ) -> tuple[ClaimLease, bytes]:
        """Claim once, then read only the state-issued no-follow inbox name."""
        run_id, digest = self._parse_token(token)
        state = self.load(token)
        lease = self.claim_lease(token)
        try:
            with self._run_directories(run_id) as directories:
                response_name = self._response_name(state)
                _, issued_path = self._resolved_run_paths(
                    directories,
                    digest,
                    response_name,
                )
                if str(response_path) != str(issued_path):
                    raise SessionIntegrityError(
                        "caller response path does not match the issued path"
                    )
                raw = self._read_file(
                    directories["inbox"],
                    response_name,
                    byte_limit=RESPONSE_BYTE_LIMIT,
                    nonblocking=True,
                )
                return lease, raw
        except (OSError, SessionIntegrityError) as error:
            raise ClaimedResponseError(str(error), lease) from error

    def _direct_successors(
        self,
        run_id: str,
        predecessor_digest: str,
    ) -> tuple[str, ...]:
        with self._run_directories(run_id) as directories:
            names = os.listdir(directories["generations"])
        successors = []
        for name in sorted(names):
            if name.startswith("."):
                continue
            if re.fullmatch(r"[0-9a-f]{64}", name) is None:
                raise SessionIntegrityError(
                    "generation directory has an invalid name"
                )
            self._load_verified(
                run_id,
                name,
                verify_previous=True,
            )
            with self._run_directories(run_id) as directories:
                generation = self._open_directory(
                    name,
                    dir_fd=directories["generations"],
                )
                try:
                    manifest_bytes = self._read_file(
                        generation,
                        "manifest.json",
                        expected_mode=0o400,
                    )
                finally:
                    os.close(generation)
            try:
                manifest = json.loads(manifest_bytes)
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise SessionIntegrityError(
                    "generation manifest JSON is invalid"
                ) from error
            if (
                not isinstance(manifest, dict)
                or manifest_bytes != _canonical_json(manifest)
            ):
                raise SessionIntegrityError(
                    "generation manifest is noncanonical"
                )
            if (
                manifest.get("previous_generation_sha256")
                != predecessor_digest
            ):
                continue
            successors.append(name)
        if len(successors) > 1:
            raise SessionIntegrityError(
                "claimed generation has multiple authenticated successors"
            )
        return tuple(successors)

    def _generation_result(
        self,
        run_id: str,
        digest: str,
    ) -> SessionGeneration:
        state = self._load_verified(
            run_id,
            digest,
            verify_previous=True,
        )
        with self._run_directories(run_id) as directories:
            packet_path, response_path = self._resolved_run_paths(
                directories,
                digest,
                self._response_name(state),
            )
        return SessionGeneration(
            token=f"{run_id}.{digest}",
            packet_path=packet_path,
            packet_sha256=state["packet_sha256"],
            response_path=response_path,
        )

    def _append_claimed_locked(
        self,
        run_id: str,
        predecessor_digest: str,
        state: Mapping[str, object],
        packet: Mapping[str, object],
    ) -> SessionGeneration:
        self._require_current_process()
        existing = self._direct_successors(
            run_id,
            predecessor_digest,
        )
        if existing:
            raise SessionIntegrityError(
                "claimed generation already has an authenticated successor"
            )
        self._require_current_process()
        expected_digest = self._prepared_generation(state, packet)[4]
        try:
            result = self._write_generation(
                run_id,
                state,
                packet,
                predecessor_digest,
            )
        except Exception:
            committed = self._direct_successors(
                run_id,
                predecessor_digest,
            )
            if committed == (expected_digest,):
                return self._generation_result(run_id, expected_digest)
            if committed:
                raise SessionIntegrityError(
                    "unexpected authenticated successor committed"
                )
            raise
        committed = self._direct_successors(
            run_id,
            predecessor_digest,
        )
        if committed != (expected_digest,):
            raise SessionIntegrityError(
                "successor commit boundary is inconsistent"
            )
        return result

    def append_claimed(
        self,
        token: str,
        state: Mapping[str, object],
        packet: Mapping[str, object],
        lease: ClaimLease | None = None,
    ) -> SessionGeneration:
        """Append after an existing claim without attempting a second claim."""
        owns_lease = lease is None
        run_id, digest = self._parse_token(token)
        if lease is None:
            lease = self._existing_claim_lease(run_id, digest)
        try:
            run_id, digest, claim_identity = self._require_claim_lease(
                token,
                lease,
            )
            with _successor_transition_lock(claim_identity):
                with self._successor_transaction_lock(lease):
                    response_name = self._response_name(state)
                    issued_response_names = set()
                    self._load_verified(
                        run_id,
                        digest,
                        verify_previous=True,
                        response_names=issued_response_names,
                    )
                    if response_name in issued_response_names:
                        raise SessionIntegrityError(
                            "response name was already issued "
                            "in this generation chain"
                        )
                    with self._run_directories(run_id) as directories:
                        self._require_response_absent(
                            directories["inbox"],
                            response_name,
                        )
                    return self._append_claimed_locked(
                        run_id,
                        digest,
                        state,
                        packet,
                    )
        finally:
            if owns_lease:
                lease.close()

    def recover_claim(
        self,
        token: str,
        terminal_state: Mapping[str, object],
    ) -> str:
        """Close a crash-abandoned claim or preserve its committed child.

        The atomic rename of a fully fsynced authenticated generation is the
        commit boundary. Temporary dot-directories are never children.
        """
        run_id, digest = self._parse_token(token)
        self._load_verified(run_id, digest, verify_previous=True)
        lease = self._existing_claim_lease(run_id, digest)
        try:
            _, _, claim_identity = self._require_claim_lease(
                token,
                lease,
            )
            with _successor_transition_lock(claim_identity):
                with self._successor_transaction_lock(lease):
                    children = self._direct_successors(run_id, digest)
                    if children:
                        return "committed-successor"
                    self._append_claimed_locked(
                        run_id,
                        digest,
                        terminal_state,
                        {"schema_version": 1, "kind": "terminal"},
                    )
                    return "abandoned-claim-closed"
        finally:
            lease.close()

    def append(
        self,
        token: str,
        state: Mapping[str, object],
        packet: Mapping[str, object],
    ) -> SessionGeneration:
        run_id, digest = self._parse_token(token)
        response_name = self._response_name(state)
        issued_response_names = set()
        self._load_verified(
            run_id,
            digest,
            verify_previous=True,
            response_names=issued_response_names,
        )
        if response_name in issued_response_names:
            raise SessionIntegrityError(
                "response name was already issued in this generation chain"
            )
        with self._run_directories(run_id) as directories:
            self._require_response_absent(
                directories["inbox"],
                response_name,
            )
        lease = self.claim_lease(token)
        try:
            return self.append_claimed(
                token,
                state,
                packet,
                lease=lease,
            )
        finally:
            lease.close()

    def tombstone(
        self,
        token: str,
        state: Mapping[str, object],
    ) -> SessionGeneration:
        return self.append(
            token,
            state,
            {"schema_version": 1, "kind": "terminal"},
        )

    def tombstone_claimed(
        self,
        token: str,
        state: Mapping[str, object],
        lease: ClaimLease | None = None,
    ) -> SessionGeneration:
        return self.append_claimed(
            token,
            state,
            {"schema_version": 1, "kind": "terminal"},
            lease=lease,
        )
