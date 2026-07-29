"""Trusted-host issuance and atomic consumption of one audit request."""

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RequestEnvelope:
    request_id: str
    manifest_sha256: str


class RequestError(RuntimeError):
    def __init__(self, code, reason):
        super().__init__(str(reason))
        self.code = code


class RequestStore:
    """Persist one enforced request beside, but outside, session runs."""

    TOKEN = re.compile(r"[0-9a-f]{64}")

    def __init__(self, session_root):
        self.root = Path(session_root) / ".requests"
        self.pending = self.root / "pending"
        self.consumed = self.root / "consumed"
        self.marker = self.root / "enforced.json"

    @staticmethod
    def _bytes(value):
        return (
            json.dumps(value, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")

    @staticmethod
    def _write_new(path, value):
        descriptor = os.open(
            path,
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | os.O_NOFOLLOW
            | os.O_CLOEXEC,
            0o400,
        )
        try:
            position = 0
            while position < len(value):
                position += os.write(descriptor, value[position:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def enforced_id(self):
        try:
            value = json.loads(self.marker.read_bytes())
        except FileNotFoundError:
            leftovers = any(
                directory.is_dir() and next(directory.iterdir(), None) is not None
                for directory in (self.pending, self.consumed)
            )
            if leftovers:
                raise RequestError(
                    "REQUEST_INVALID",
                    "request registry is incomplete",
                )
            return None
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RequestError(
                "REQUEST_INVALID", "request enforcement marker is invalid"
            ) from error
        if (
            type(value) is not dict
            or set(value) != {"request_id"}
            or not isinstance(value["request_id"], str)
            or self.TOKEN.fullmatch(value["request_id"]) is None
        ):
            raise RequestError(
                "REQUEST_INVALID", "request enforcement marker is invalid"
            )
        return value["request_id"]

    def issue(self, manifest):
        self.pending.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.consumed.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.enforced_id() is not None:
            raise RequestError(
                "REQUEST_ALREADY_ISSUED",
                "an enforced request is already issued for this root",
            )
        request_id = secrets.token_hex(32)
        raw = self._bytes(
            {"schema_version": 1, "request_id": request_id, **manifest}
        )
        self._write_new(self.pending / f"{request_id}.json", raw)
        self._write_new(
            self.marker, self._bytes({"request_id": request_id})
        )
        return RequestEnvelope(request_id, hashlib.sha256(raw).hexdigest())

    def consume(self, request_id):
        if (
            not isinstance(request_id, str)
            or self.TOKEN.fullmatch(request_id) is None
        ):
            raise RequestError("REQUEST_INVALID", "request identity is invalid")
        enforced = self.enforced_id()
        if enforced is None or not secrets.compare_digest(
            enforced, request_id
        ):
            raise RequestError(
                "REQUEST_INVALID", "request identity is not issued"
            )
        pending = self.pending / f"{request_id}.json"
        consumed = self.consumed / f"{request_id}.json"
        try:
            os.link(pending, consumed, follow_symlinks=False)
            pending.unlink()
        except FileExistsError as error:
            raise RequestError(
                "REQUEST_CONSUMED", "request identity was already consumed"
            ) from error
        except FileNotFoundError as error:
            if consumed.is_file():
                raise RequestError(
                    "REQUEST_CONSUMED",
                    "request identity was already consumed",
                ) from error
            raise RequestError(
                "REQUEST_INVALID", "request manifest is unavailable"
            ) from error
        try:
            raw = consumed.read_bytes()
            value = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise RequestError(
                "REQUEST_INVALID", "request manifest is invalid"
            ) from error
        if (
            type(value) is not dict
            or set(value)
            != {"schema_version", "request_id", "primary", "then"}
            or value["schema_version"] != 1
            or value["request_id"] != request_id
        ):
            raise RequestError("REQUEST_INVALID", "request manifest is invalid")
        return value, hashlib.sha256(raw).hexdigest()
