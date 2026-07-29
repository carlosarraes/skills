"""Per-run Unix-socket broker for enforced contract audits."""

import base64
import binascii
import hashlib
import json
import os
import socket
import socketserver
import threading
from contextlib import contextmanager
from dataclasses import fields, is_dataclass
from pathlib import Path

from audit_runtime import (
    AuditComplete,
    AuditRuntime,
    AuditStopped,
    ContinueAudit,
    NeedJudgment,
    StartAudit,
)
from audit_session import SessionStore


REQUEST_LIMIT = 3 * 1024 * 1024
RESPONSE_LIMIT = 2 * 1024 * 1024
SOCKET_TIMEOUT_SECONDS = 10


class BrokerError(RuntimeError):
    def __init__(self, code, reason, *, zero_target_writes=True):
        super().__init__(str(reason))
        self.code = code
        self.zero_target_writes = zero_target_writes


def _public_value(value):
    if value is None or type(value) in (bool, int, float, str):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {key: _public_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_public_value(item) for item in value]
    if is_dataclass(value):
        return {
            field.name: _public_value(getattr(value, field.name))
            for field in fields(value)
        }
    return dict(value) if hasattr(value, "items") else value


def subject_report_path(repository_root, report_path, public_target_root):
    """Map a host result through one authenticated repository authority."""
    repository_root = Path(repository_root).resolve(strict=False)
    report_path = Path(report_path).resolve(strict=False)
    public_target_root = Path(public_target_root)
    if not public_target_root.is_absolute():
        raise BrokerError(
            "BROKER_RESULT_INVALID", "public target root is not absolute"
        )
    try:
        relative = report_path.relative_to(repository_root)
    except ValueError as error:
        raise BrokerError(
            "BROKER_RESULT_INVALID",
            "runtime report path is outside its authorized repository",
        ) from error
    return (public_target_root / relative).as_posix()


def _manifest_repositories(envelope):
    if not isinstance(getattr(envelope, "manifest_json", None), str):
        raise TypeError("broker requires its host-issued request envelope")
    raw = envelope.manifest_json.encode("utf-8")
    if not hashlib.sha256(raw).hexdigest() == envelope.manifest_sha256:
        raise ValueError("request envelope manifest digest is invalid")
    try:
        manifest = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("request envelope manifest is invalid") from error
    if (
        type(manifest) is not dict
        or set(manifest)
        != {"schema_version", "request_id", "primary", "then"}
        or manifest.get("schema_version") != 1
        or manifest.get("request_id") != envelope.request_id
        or type(manifest.get("primary")) is not dict
        or (
            manifest.get("then") is not None
            and type(manifest.get("then")) is not dict
        )
    ):
        raise ValueError("request envelope manifest is invalid")
    repositories = []
    for target in (manifest["primary"], manifest["then"]):
        if target is None:
            continue
        repo = target.get("repo")
        if not isinstance(repo, str) or not Path(repo).is_absolute():
            raise ValueError("request envelope repository is invalid")
        repositories.append(Path(repo).resolve(strict=False))
    return tuple(repositories)


def _validated_public_targets(envelope, public_targets):
    if type(public_targets) is not dict:
        raise TypeError("broker public target mapping must be a dictionary")
    normalized = {}
    for host_root, public_root in public_targets.items():
        host = Path(host_root).resolve(strict=False)
        public = Path(public_root)
        if not public.is_absolute() or Path(os.path.normpath(public)) != public:
            raise ValueError("broker public target root is invalid")
        normalized[host] = public
    repositories = _manifest_repositories(envelope)
    if any(repository not in normalized for repository in repositories):
        raise ValueError("request repository has no public target mapping")
    public_roots = [normalized[repository] for repository in repositories]
    if len(set(public_roots)) != len(public_roots):
        raise ValueError("request repositories require distinct public targets")
    return {repository: normalized[repository] for repository in repositories}


class HostAuditBroker:
    """Own runtime authority and expose only start/continue protocol bytes."""

    def __init__(self, runtime: AuditRuntime, envelope, public_targets):
        if not all(
            isinstance(getattr(envelope, field, None), str)
            for field in ("request_id", "manifest_sha256")
        ):
            raise TypeError("broker requires its host-issued request envelope")
        self.runtime = runtime
        self.request_id = envelope.request_id
        self.manifest_sha256 = envelope.manifest_sha256
        self.public_targets = _validated_public_targets(
            envelope, public_targets
        )
        self._responses = {}
        self._lock = threading.Lock()

    @staticmethod
    def _stopped(code, *, zero_target_writes=True):
        return {
            "result": "AuditStopped",
            "code": code,
            "reason": "audit stopped",
            "target": "broker",
            "prior_report_preserved": True,
            "zero_target_writes": zero_target_writes,
        }

    def _session_repository_root(self, session):
        state = SessionStore(self.runtime.session_root).load(session)
        try:
            repository_root = Path(
                state["target_identity"]["repository_root"]
            ).resolve(strict=False)
        except (KeyError, TypeError, ValueError) as error:
            raise BrokerError(
                "BROKER_RESULT_INVALID",
                "runtime session repository authority is invalid",
            ) from error
        if repository_root not in self.public_targets:
            raise BrokerError(
                "BROKER_RESULT_INVALID",
                "runtime session repository is not request-authorized",
            )
        return repository_root

    def _export(self, result, repository_root=None):
        if isinstance(result, NeedJudgment):
            packet_bytes = result.packet_path.read_bytes()
            if hashlib.sha256(packet_bytes).hexdigest() != result.packet_sha256:
                raise BrokerError(
                    "BROKER_RESULT_INVALID", "issued packet hash changed"
                )
            packet = json.loads(packet_bytes)
            packet_request = packet.get("request")
            if (
                result.request_id != self.request_id
                or type(packet_request) is not dict
                or packet_request.get("id") != self.request_id
                or packet_request.get("manifest_sha256")
                != self.manifest_sha256
            ):
                raise BrokerError(
                    "BROKER_RESULT_INVALID",
                    "issued packet request binding changed",
                )
            issued_repository = self._session_repository_root(result.session)
            with self._lock:
                self._responses[result.session] = (
                    result.response_path,
                    issued_repository,
                )
            public = _public_value(result)
            for field in ("packet_path", "response_path", "next_command"):
                public.pop(field, None)
            public.update(
                {
                    "result": "NeedJudgment",
                    "packet": packet,
                }
            )
            return public
        if isinstance(result, AuditComplete):
            try:
                if repository_root not in self.public_targets:
                    raise BrokerError(
                        "BROKER_RESULT_INVALID",
                        "completed audit has no authorized public target",
                    )
                public = _public_value(result)
                public["report_path"] = subject_report_path(
                    repository_root,
                    result.report_path,
                    self.public_targets[repository_root],
                )
            except BrokerError as error:
                raise BrokerError(
                    error.code,
                    error,
                    zero_target_writes=False,
                ) from error
            except (OSError, TypeError, ValueError) as error:
                raise BrokerError(
                    "BROKER_RESULT_INVALID",
                    "completed report path mapping failed",
                    zero_target_writes=False,
                ) from error
            public["result"] = "AuditComplete"
            return public
        if isinstance(result, AuditStopped):
            public = _public_value(result)
            public.update(
                {"result": "AuditStopped", "reason": "audit stopped"}
            )
            return public
        raise BrokerError("BROKER_RESULT_INVALID", "runtime result is invalid")

    def _start(self, request):
        if set(request) != {"operation", "request_id"}:
            raise BrokerError(
                "BROKER_REQUEST_INVALID", "start fields are invalid"
            )
        if request["request_id"] != self.request_id:
            raise BrokerError(
                "BROKER_REQUEST_INVALID", "request identity is invalid"
            )
        return self._export(
            self.runtime.advance(
                StartAudit(request_id=request["request_id"])
            )
        )

    def _continue(self, request):
        if set(request) != {"operation", "session", "response_base64"}:
            raise BrokerError(
                "BROKER_REQUEST_INVALID", "continue fields are invalid"
            )
        session = request["session"]
        encoded = request["response_base64"]
        if not isinstance(session, str) or not isinstance(encoded, str):
            raise BrokerError(
                "BROKER_REQUEST_INVALID", "continue values are invalid"
            )
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (binascii.Error, ValueError) as error:
            raise BrokerError(
                "BROKER_REQUEST_INVALID", "response encoding is invalid"
            ) from error
        if len(raw) > RESPONSE_LIMIT:
            raise BrokerError(
                "BROKER_REQUEST_INVALID", "response exceeds the byte limit"
            )
        with self._lock:
            response_context = self._responses.pop(session, None)
        if response_context is None:
            raise BrokerError(
                "BROKER_SESSION_INVALID", "session was not issued by this broker"
            )
        response_path, repository_root = response_context
        descriptor = os.open(
            response_path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o400,
        )
        try:
            position = 0
            while position < len(raw):
                position += os.write(descriptor, raw[position:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return self._export(
            self.runtime.advance(ContinueAudit(session, response_path)),
            repository_root,
        )

    def handle(self, request):
        if type(request) is not dict or not isinstance(
            request.get("operation"), str
        ):
            raise BrokerError(
                "BROKER_REQUEST_INVALID", "request must be one JSON object"
            )
        if request["operation"] == "start":
            return self._start(request)
        if request["operation"] == "continue":
            return self._continue(request)
        raise BrokerError(
            "BROKER_REQUEST_INVALID", "operation is not supported"
        )


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(SOCKET_TIMEOUT_SECONDS)
        chunks = []
        total = 0
        try:
            while True:
                chunk = self.request.recv(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > REQUEST_LIMIT:
                    response = self.server.broker._stopped(
                        "BROKER_REQUEST_INVALID"
                    )
                    break
                chunks.append(chunk)
        except TimeoutError:
            response = self.server.broker._stopped("BROKER_REQUEST_TIMEOUT")
            total = REQUEST_LIMIT + 1
        if total <= REQUEST_LIMIT:
            try:
                def closed_object(pairs):
                    value = {}
                    for key, item in pairs:
                        if key in value:
                            raise BrokerError(
                                "BROKER_REQUEST_INVALID",
                                "request contains a duplicate key",
                            )
                        value[key] = item
                    return value

                request = json.loads(
                    b"".join(chunks), object_pairs_hook=closed_object
                )
                response = self.server.broker.handle(request)
            except (BrokerError, UnicodeDecodeError, json.JSONDecodeError) as error:
                response = self.server.broker._stopped(
                    getattr(error, "code", "BROKER_REQUEST_INVALID"),
                    zero_target_writes=getattr(
                        error, "zero_target_writes", True
                    ),
                )
            except (OSError, ValueError, TypeError):
                response = self.server.broker._stopped("BROKER_FAILURE")
        self.request.sendall(
            json.dumps(
                response, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        )


class AuditBrokerServer(socketserver.UnixStreamServer):
    def __init__(self, socket_path, runtime, envelope, *, public_targets):
        self.socket_path = Path(socket_path)
        self.broker = HostAuditBroker(runtime, envelope, public_targets)
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        super().__init__(str(self.socket_path), _Handler)

    @contextmanager
    def running(self):
        thread = threading.Thread(target=self.serve_forever, daemon=True)
        thread.start()
        try:
            yield self
        finally:
            self.shutdown()
            self.server_close()
            thread.join(timeout=SOCKET_TIMEOUT_SECONDS)
            try:
                self.socket_path.unlink()
            except FileNotFoundError:
                pass


def broker_call(socket_path, request):
    raw = json.dumps(
        request, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(raw) > REQUEST_LIMIT:
        raise BrokerError("BROKER_REQUEST_INVALID", "request is too large")
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(SOCKET_TIMEOUT_SECONDS)
            connection.connect(str(socket_path))
            connection.sendall(raw)
            connection.shutdown(socket.SHUT_WR)
            chunks = []
            total = 0
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                total += len(chunk)
                if total > REQUEST_LIMIT:
                    raise BrokerError(
                        "BROKER_RESULT_INVALID", "broker result is too large"
                    )
                chunks.append(chunk)
        return json.loads(b"".join(chunks))
    except BrokerError:
        raise
    except (OSError, TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise BrokerError(
            "BROKER_UNAVAILABLE", "broker exchange failed"
        ) from error
