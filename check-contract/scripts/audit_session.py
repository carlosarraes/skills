"""Authenticated local storage for immutable audit generations.

The HMAC chain detects accidental corruption, stale generations, and
token-only or unkeyed forgery. Because its key and data are owned by the same
effective user, it does not protect against deliberate coordinated filesystem
tampering by that same effective user.

Response creation is caller-owned at the exact issued path. Consumption claims
the generation first, then reads only the exact issued response name through
the verified inbox directory descriptor with O_NOFOLLOW and a fixed byte
limit.

Claimed-generation appenders serialize on a crash-released filesystem lock.
A fully fsynced authenticated generation becomes the one successor at its
atomic directory rename; dot-prefixed staging directories are never children.
After an interrupted call, authenticated child discovery recovers a committed
rename or permits a terminal child when no rename committed.
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


class SessionIntegrityError(RuntimeError):
    """Raised when a session component or generation is not trustworthy."""


class ClaimedResponseError(SessionIntegrityError):
    """Raised after a generation was irreversibly claimed for a bad response."""


class GenerationConsumedError(SessionIntegrityError):
    """Raised when a generation claim already exists."""


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

    def _open_base(self, *, create: bool) -> int:
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

    def claim(self, token: str) -> None:
        run_id, digest = self._parse_token(token)
        self.load(token)
        with self._run_directories(run_id) as directories:
            try:
                os.mkdir(
                    digest,
                    mode=0o700,
                    dir_fd=directories["claims"],
                )
            except FileExistsError as error:
                raise GenerationConsumedError(
                    "generation was already consumed"
                ) from error
            except OSError as error:
                raise SessionIntegrityError(
                    "cannot claim generation"
                ) from error
            os.fsync(directories["claims"])

    def claim_and_read(
        self,
        token: str,
        response_path: Path,
    ) -> bytes:
        """Claim once, then read only the state-issued no-follow inbox name."""
        run_id, digest = self._parse_token(token)
        state = self.load(token)
        self.claim(token)
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
                return self._read_file(
                    directories["inbox"],
                    response_name,
                    byte_limit=RESPONSE_BYTE_LIMIT,
                    nonblocking=True,
                )
        except (OSError, SessionIntegrityError) as error:
            raise ClaimedResponseError(str(error)) from error

    @contextmanager
    def _claim_lock(self, run_id: str, digest: str):
        with self._run_directories(run_id) as directories:
            claim = self._open_directory(
                digest,
                dir_fd=directories["claims"],
            )
            try:
                fcntl.flock(claim, fcntl.LOCK_EX)
                yield
            finally:
                fcntl.flock(claim, fcntl.LOCK_UN)
                os.close(claim)

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
        existing = self._direct_successors(
            run_id,
            predecessor_digest,
        )
        if existing:
            raise SessionIntegrityError(
                "claimed generation already has an authenticated successor"
            )
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
    ) -> SessionGeneration:
        """Append after an existing claim without attempting a second claim."""
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
        with self._claim_lock(run_id, digest):
            return self._append_claimed_locked(
                run_id,
                digest,
                state,
                packet,
            )

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
        with self._claim_lock(run_id, digest):
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
        self.claim(token)
        return self.append_claimed(token, state, packet)

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
    ) -> SessionGeneration:
        return self.append_claimed(
            token,
            state,
            {"schema_version": 1, "kind": "terminal"},
        )
