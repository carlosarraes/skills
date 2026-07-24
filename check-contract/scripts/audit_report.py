"""Deterministic report rendering, atomic publication, and mutation proof."""

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path


class ReportError(RuntimeError):
    """Raised when report publication cannot preserve its mutation contract."""


def _json_text(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )


def _ids(values) -> str:
    values = tuple(values)
    return ", ".join(values) if values else "none"


def render_report(
    *,
    authority: dict[str, object],
    worktree_status: str,
    code_judgment,
    reconciliation_details: dict[str, object],
    decision,
    probe_observation,
    report_relative_path: str,
) -> bytes:
    """Render stable Markdown without timestamps or host-specific paths."""
    lines = [
        (
            f"# Contract Check: {authority['ticket']} — "
            f"v{authority['active_version']}"
        ),
        "",
        (
            f"Audit range: {authority['base_sha']}.."
            f"{authority['head_sha']}"
        ),
        f"Worktree state: {worktree_status}",
        f"Contract SHA-256: {authority['contract_sha256']}",
        "",
        "## Code-first observed behavior",
        "",
    ]
    if code_judgment.path_assessments:
        for path in code_judgment.path_assessments:
            lines.append(
                f"- {path.path_id}: surface {path.surface.status}; "
                f"evidence {_ids(path.surface.evidence_ids)}; "
                f"reason {_json_text(path.surface.reason)}"
            )
    else:
        lines.append("- No changed implementation paths.")
    lines.extend(["", "## Clause-by-clause fidelity", ""])
    for clause in code_judgment.clauses:
        lines.append(
            f"- {clause.clause_id}: {clause.status}; "
            f"evidence {_ids(clause.evidence_ids)}; "
            f"reason {_json_text(clause.reason)}"
        )
    lines.extend(
        [
            "",
            "## YAGNI and reuse",
            "",
            f"YAGNI: {decision.yagni}",
            f"Reuse: {decision.reuse}",
        ]
    )
    for path in code_judgment.path_assessments:
        yagni = path.yagni_items
        reuse = path.reuse_items
        lines.append(
            f"- {path.path_id} YAGNI items: "
            f"{_ids(item.item_id for item in yagni)}"
        )
        lines.append(
            f"- {path.path_id} reuse items: "
            f"{_ids(item.item_id for item in reuse)}"
        )
    lines.extend(
        [
            "",
            "## Drift reconciliation",
            "",
            f"Documented drift: {decision.documented_drift}",
            f"Undocumented drift: {decision.undocumented_drift}",
        ]
    )
    ledger_details = reconciliation_details["ledger_entries"]
    for entry in reconciliation_details["effective_ledger_entries"]:
        detail = ledger_details[entry.ledger_id]
        lines.append(
            f"- {entry.ledger_id}: {entry.status}; "
            f"evidence {_ids(detail['evidence_ids'])}; "
            f"reason {_json_text(detail['reason'])}"
        )
    matches = {
        match.deviation_id: match.ledger_id
        for match in reconciliation_details["deviation_matches"]
    }
    for deviation in code_judgment.deviations:
        documentation = matches.get(deviation.deviation_id, "undocumented")
        lines.append(
            f"- {deviation.deviation_id}: {documentation}; "
            f"evidence {_ids(deviation.evidence_ids)}; "
            f"reason {_json_text(deviation.reason)}"
        )
    if not reconciliation_details["effective_ledger_entries"]:
        lines.append("- D IDs: none")
    if not code_judgment.deviations:
        lines.append("- U IDs: none")
    if probe_observation is not None:
        status = "PASS" if probe_observation.success else "FAIL"
        lines.append(
            f"- Probe {probe_observation.probe_id}: {status}; "
            f"{probe_observation.reason}"
        )
    lines.extend(["", "## Ordered findings", ""])
    if decision.findings:
        for finding in decision.findings:
            location = (
                f" at {finding.path_id}:{finding.line}"
                if finding.path_id
                else ""
            )
            lines.append(
                f"- {finding.finding_id}: {finding.source_kind} "
                f"{finding.source_id}{location}; "
                f"{_json_text(finding.reason)}"
            )
    else:
        lines.append("- F IDs: none")
    cited_ids = [
        *(item.finding_id for item in decision.findings),
        *(item.deviation_id for item in code_judgment.deviations),
        *(
            item.ledger_id
            for item in reconciliation_details["effective_ledger_entries"]
        ),
    ]
    lines.extend(
        [
            "",
            "## Verdict and route",
            "",
            f"Contract fidelity: {decision.fidelity}",
            f"Verdict: {decision.verdict}",
            (
                "Recommended next skill: "
                + (
                    ", then ".join(decision.route)
                    if decision.route
                    else "none"
                )
            ),
            f"IDs: {_ids(cited_ids)}",
            "",
            "## Mutation attestation",
            "",
            "Only active report changed: true",
            f"Mutated paths: {report_relative_path}",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def capture_target_state(repository_root: Path) -> dict[str, str]:
    """Hash every non-Git target leaf without following symlinks."""
    repository_root = Path(repository_root)
    state = {}
    for root, directories, files in os.walk(
        repository_root,
        topdown=True,
        followlinks=False,
    ):
        root_path = Path(root)
        if root_path == repository_root:
            directories[:] = [
                name for name in directories if name != ".git"
            ]
        symlink_directories = []
        for name in directories:
            path = root_path / name
            if path.is_symlink():
                symlink_directories.append(name)
                relative = path.relative_to(repository_root).as_posix()
                metadata = path.lstat()
                content = os.fsencode(path.readlink())
                state[relative] = hashlib.sha256(
                    (
                        f"{metadata.st_dev}:{metadata.st_ino}:"
                        f"{metadata.st_mode}:"
                    ).encode("ascii")
                    + content
                ).hexdigest()
        directories[:] = [
            name for name in directories if name not in symlink_directories
        ]
        for name in files:
            path = root_path / name
            relative = path.relative_to(repository_root).as_posix()
            metadata = path.lstat()
            if stat.S_ISREG(metadata.st_mode):
                content = path.read_bytes()
            elif stat.S_ISLNK(metadata.st_mode):
                content = os.fsencode(path.readlink())
            else:
                content = (
                    f"{stat.S_IFMT(metadata.st_mode)}:{metadata.st_size}"
                ).encode("ascii")
            state[relative] = hashlib.sha256(
                (
                    f"{metadata.st_dev}:{metadata.st_ino}:"
                    f"{metadata.st_mode}:"
                ).encode("ascii")
                + content
            ).hexdigest()
    return state


def mutation_attestation(
    before: dict[str, str],
    after: dict[str, str],
    report_relative_path: str,
) -> dict[str, object]:
    changed = tuple(
        sorted(
            path
            for path in set(before) | set(after)
            if before.get(path) != after.get(path)
        )
    )
    return {
        "only_active_report_changed": changed == (report_relative_path,),
        "mutated_paths": changed,
        "initial_target_sha256": hashlib.sha256(
            _json_text(before).encode("ascii")
        ).hexdigest(),
        "final_target_sha256": hashlib.sha256(
            _json_text(after).encode("ascii")
        ).hexdigest(),
    }


def publish_atomic(report_path: Path, content: bytes) -> str:
    """Publish bytes with one same-directory atomic replacement."""
    report_path = Path(report_path)
    descriptor = None
    temporary = None
    try:
        descriptor, temporary = tempfile.mkstemp(
            prefix=".check-report-",
            suffix=".tmp",
            dir=report_path.parent,
        )
        with os.fdopen(descriptor, "wb") as output:
            descriptor = None
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, report_path)
        temporary = None
    except OSError as error:
        raise ReportError(f"atomic report publication failed: {error}") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary is not None:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
    return hashlib.sha256(content).hexdigest()


def restore_report(report_path: Path, prior_content: bytes | None) -> None:
    """Restore the exact pre-close report after a failed post-write check."""
    report_path = Path(report_path)
    if prior_content is None:
        try:
            report_path.unlink()
        except FileNotFoundError:
            pass
        return
    publish_atomic(report_path, prior_content)


__all__ = [
    "ReportError",
    "capture_target_state",
    "mutation_attestation",
    "publish_atomic",
    "render_report",
    "restore_report",
]
