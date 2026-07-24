"""Typed changed-path, deferred-path, and machine-grep filtering."""

import os
from dataclasses import dataclass
from pathlib import Path


KNOWN_NARRATIVE_NAMES = frozenset(
    {
        "audit-report.md",
        "check-report.md",
        "implementation-summary.md",
        "plan.md",
        "pr-description.md",
        "pull-request.md",
        "validation.md",
    }
)


class AuditPathError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangedPath:
    status: str
    path: str
    old_path: str | None = None

    def as_packet_value(self) -> dict[str, str]:
        value = {"status": self.status, "path": self.path}
        if self.old_path is not None:
            value["old_path"] = self.old_path
        return value


@dataclass(frozen=True)
class GrepMatch:
    path: str
    line: int
    text: str

    def as_packet_value(self) -> dict[str, object]:
        return {"path": self.path, "line": self.line, "text": self.text}


class PathPolicy:
    """Classify every Git path at all evidence output seams."""

    def __init__(
        self,
        repository_root: Path,
        branch_directory: str,
        narrative_paths: tuple[Path, ...],
    ):
        self.repository_root = Path(repository_root).resolve()
        self.branch_directory = branch_directory
        narratives = []
        for value in narrative_paths:
            absolute = (
                Path(value)
                if Path(value).is_absolute()
                else self.repository_root / value
            )
            normalized = Path(os.path.abspath(absolute))
            try:
                narratives.append(
                    normalized.relative_to(self.repository_root).as_posix()
                )
            except ValueError as error:
                raise AuditPathError(
                    "narrative path is outside the target repository"
                ) from error
        self.narrative_paths = tuple(sorted(set(narratives)))

    @classmethod
    def from_authority(cls, authority, narrative_paths):
        return cls(
            Path(authority["repository_root"]),
            authority["branch_directory"],
            narrative_paths,
        )

    def is_deferred(self, path: str) -> bool:
        return (
            self.is_contract_artifact(path)
            or path in self.narrative_paths
            or Path(path).name in KNOWN_NARRATIVE_NAMES
            or path.startswith(".worker-results/")
        )

    def is_contract_artifact(self, path: str) -> bool:
        prefixes = (
            f".notes/{self.branch_directory}/contract/",
            f"ai_docs/{self.branch_directory}/contract/",
        )
        return path.startswith(prefixes)

    def accepts_changed(self, changed: ChangedPath) -> bool:
        return not self.is_deferred(changed.path) and (
            changed.old_path is None
            or not self.is_deferred(changed.old_path)
        )

    def filter_changed(
        self,
        changed_paths: tuple[ChangedPath, ...],
    ) -> tuple[ChangedPath, ...]:
        return tuple(item for item in changed_paths if self.accepts_changed(item))

    def head_paths(self, raw: bytes) -> tuple[str, ...]:
        values = raw.split(b"\0")
        if values and values[-1] == b"":
            values.pop()
        return tuple(
            value.decode("utf-8", "surrogateescape")
            for value in values
        )

    def allowed_head_paths(
        self,
        raw: bytes,
        denied_paths: frozenset[str] = frozenset(),
    ) -> frozenset[str]:
        paths = self.head_paths(raw)
        return frozenset(
            path
            for path in paths
            if path not in denied_paths and not self.is_deferred(path)
        )

    def deferred_head_narratives(self, raw: bytes) -> frozenset[str]:
        return frozenset(
            path
            for path in self.head_paths(raw)
            if self.is_deferred(path)
            and not self.is_contract_artifact(path)
        )

    def parse_grep_z(
        self,
        raw: bytes,
        head: str,
        allowed_paths: frozenset[str],
        *,
        allow_incomplete_tail: bool = False,
    ) -> tuple[GrepMatch, ...]:
        prefix = head.encode("ascii") + b":"
        matches = []
        position = 0
        while position < len(raw):
            path_end = raw.find(b"\0", position)
            line_end = raw.find(b"\0", path_end + 1)
            text_end = raw.find(b"\n", line_end + 1)
            if min(path_end, line_end, text_end) < 0:
                if allow_incomplete_tail:
                    break
                raise AuditPathError("malformed NUL-delimited grep result")
            qualified = raw[position:path_end]
            if not qualified.startswith(prefix):
                raise AuditPathError("grep result is outside recorded HEAD")
            path = qualified[len(prefix) :].decode(
                "utf-8",
                "surrogateescape",
            )
            line_bytes = raw[path_end + 1 : line_end]
            if not line_bytes.isdigit():
                raise AuditPathError("grep result has an invalid line number")
            if path in allowed_paths:
                matches.append(
                    GrepMatch(
                        path=path,
                        line=int(line_bytes),
                        text=raw[line_end + 1 : text_end].decode(
                            "utf-8",
                            "replace",
                        ),
                    )
                )
            position = text_end + 1
        return tuple(matches)


def parse_name_status_z(raw: bytes) -> tuple[ChangedPath, ...]:
    fields = raw.decode("utf-8", "surrogateescape").split("\0")
    if fields and fields[-1] == "":
        fields.pop()
    result = []
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if status[:1] in {"R", "C"}:
            if index + 1 >= len(fields):
                raise AuditPathError("malformed Git name inventory")
            old_path, path = fields[index : index + 2]
            index += 2
            result.append(ChangedPath(status, path, old_path))
        else:
            if index >= len(fields):
                raise AuditPathError("malformed Git name inventory")
            result.append(ChangedPath(status, fields[index]))
            index += 1
    return tuple(result)
