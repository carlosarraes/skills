"""Append-only, content-addressed storage for audit runtime generations."""

import hashlib
import json
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


TOKEN_RE = re.compile(r"([0-9a-f]{32})\.([0-9a-f]{64})")


class SessionIntegrityError(RuntimeError):
    """Raised when an opaque session token or immutable generation is invalid."""


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


class SessionStore:
    """Own an external append-only run log without mutating generations."""

    def __init__(self, root: Path):
        self.root = Path(root).resolve()

    def _parse_token(self, token: str) -> tuple[str, str]:
        if not isinstance(token, str):
            raise SessionIntegrityError("session token must be text")
        match = TOKEN_RE.fullmatch(token)
        if match is None:
            raise SessionIntegrityError("invalid session token")
        return match.groups()

    def _run(self, run_id: str) -> Path:
        return self.root / run_id

    def _generation(self, run_id: str, digest: str) -> Path:
        return self._run(run_id) / "generations" / digest

    def _new_run(self) -> tuple[str, Path]:
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for _ in range(100):
            run_id = secrets.token_hex(16)
            run = self._run(run_id)
            try:
                run.mkdir(mode=0o700)
            except FileExistsError:
                continue
            os.chmod(run, 0o700)
            for name in ("generations", "claims", "inbox"):
                (run / name).mkdir(mode=0o700)
            return run_id, run
        raise SessionIntegrityError("cannot allocate an audit run")

    def _write_generation(
        self,
        run_id: str,
        state: Mapping[str, object],
        packet: Mapping[str, object],
    ) -> SessionGeneration:
        packet_bytes = _canonical_json(dict(packet))
        packet_digest = _digest(packet_bytes)
        state_value = dict(state)
        existing_packet_digest = state_value.get("packet_sha256")
        if (
            existing_packet_digest is not None
            and existing_packet_digest != packet_digest
        ):
            raise SessionIntegrityError("state packet digest mismatch")
        state_value["packet_sha256"] = packet_digest
        response_name = state_value.get("response_name")
        if (
            not isinstance(response_name, str)
            or not re.fullmatch(r"[0-9a-f]{32}\.json", response_name)
        ):
            raise SessionIntegrityError("state has an invalid response name")
        state_bytes = _canonical_json(state_value)
        state_digest = _digest(state_bytes)
        run = self._run(run_id)
        generations = run / "generations"
        temporary = generations / f".{state_digest}-{secrets.token_hex(8)}"
        generation = generations / state_digest
        temporary.mkdir(mode=0o700)
        try:
            (temporary / "state.json").write_bytes(state_bytes)
            (temporary / "packet.json").write_bytes(packet_bytes)
            manifest = {
                "schema_version": 1,
                "state_sha256": state_digest,
                "packet_sha256": packet_digest,
            }
            (temporary / "manifest.json").write_bytes(
                _canonical_json(manifest)
            )
            for name in ("state.json", "packet.json", "manifest.json"):
                os.chmod(temporary / name, 0o400)
            try:
                os.rename(temporary, generation)
            except FileExistsError as error:
                raise SessionIntegrityError(
                    "generation digest already exists"
                ) from error
        finally:
            if temporary.exists():
                for child in temporary.iterdir():
                    child.chmod(0o600)
                    child.unlink()
                temporary.rmdir()
        token = f"{run_id}.{state_digest}"
        return SessionGeneration(
            token=token,
            packet_path=generation / "packet.json",
            packet_sha256=packet_digest,
            response_path=run / "inbox" / response_name,
        )

    def create(
        self,
        state: Mapping[str, object],
        packet: Mapping[str, object],
    ) -> SessionGeneration:
        run_id, _ = self._new_run()
        try:
            return self._write_generation(run_id, state, packet)
        except Exception:
            run = self._run(run_id)
            for directory in ("inbox", "claims", "generations"):
                (run / directory).rmdir()
            run.rmdir()
            raise

    def load(self, token: str) -> dict:
        run_id, expected_digest = self._parse_token(token)
        generation = self._generation(run_id, expected_digest)
        try:
            state_bytes = (generation / "state.json").read_bytes()
            packet_bytes = (generation / "packet.json").read_bytes()
            manifest_bytes = (generation / "manifest.json").read_bytes()
        except OSError as error:
            raise SessionIntegrityError("generation files are unavailable") from error
        actual_digest = _digest(state_bytes)
        if actual_digest != expected_digest:
            raise SessionIntegrityError("generation state digest mismatch")
        try:
            state = json.loads(state_bytes)
            manifest = json.loads(manifest_bytes)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise SessionIntegrityError("invalid generation JSON") from error
        if not isinstance(state, dict):
            raise SessionIntegrityError("generation state must be an object")
        packet_digest = _digest(packet_bytes)
        if state.get("packet_sha256") != packet_digest:
            raise SessionIntegrityError("generation packet digest mismatch")
        expected_manifest = {
            "schema_version": 1,
            "state_sha256": expected_digest,
            "packet_sha256": packet_digest,
        }
        if (
            manifest != expected_manifest
            or manifest_bytes != _canonical_json(expected_manifest)
        ):
            raise SessionIntegrityError("generation manifest mismatch")
        return state

    def claim(self, token: str) -> None:
        run_id, digest = self._parse_token(token)
        self.load(token)
        try:
            (self._run(run_id) / "claims" / digest).mkdir(mode=0o700)
        except FileExistsError as error:
            raise SessionIntegrityError("generation was already consumed") from error

    def append(
        self,
        token: str,
        state: Mapping[str, object],
        packet: Mapping[str, object],
    ) -> SessionGeneration:
        run_id, _ = self._parse_token(token)
        self.claim(token)
        return self._write_generation(run_id, state, packet)

    def tombstone(
        self,
        token: str,
        state: Mapping[str, object],
    ) -> SessionGeneration:
        return self.append(token, state, {"kind": "terminal"})
