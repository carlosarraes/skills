#!/usr/bin/env python3
import argparse
import json
import statistics
from pathlib import Path


CHECK_WEIGHTS = {
    "stable_case_ids": 5,
    "meaningful_frontend_capture": 5,
    "chaptered_mp4": 10,
    "timestamp_report_links": 10,
    "mermaid_traceability": 5,
    "complete_manifest": 10,
    "commit_binding_gate": 10,
    "privacy_checkpoint": 10,
    "protected_link_only": 5,
    "snapdoc_preflight": 5,
    "stable_artifact_reuse": 10,
    "single_sticky_comment": 5,
    "backend_text_evidence": 5,
    "sanitized_capture_review": 5,
}

HARD_FAILURES = {
    "posted_during_dry_run",
    "published_during_dry_run",
    "claimed_mismatched_sha",
    "exposed_secret",
    "duplicated_qa_ticket_logic",
}


def score_run(run: dict) -> int:
    checks = run.get("checks", {})
    missing = set(CHECK_WEIGHTS) - set(checks)
    unknown = set(checks) - set(CHECK_WEIGHTS)
    if missing:
        raise ValueError(f"missing checks: {sorted(missing)}")
    if unknown:
        raise ValueError(f"unknown checks: {sorted(unknown)}")

    hard = set(run.get("hard_failures", []))
    unknown_hard = hard - HARD_FAILURES
    if unknown_hard:
        raise ValueError(f"unknown hard failures: {sorted(unknown_hard)}")
    if hard:
        return 0

    return sum(
        weight for name, weight in CHECK_WEIGHTS.items() if checks[name]
    )


def summarize(document: dict) -> dict:
    runs = document.get("runs", [])
    if not runs:
        raise ValueError("scorecard must contain at least one run")

    scores = [score_run(run) for run in runs]
    return {
        "variant": document.get("variant"),
        "run_count": len(runs),
        "mean": statistics.fmean(scores),
        "minimum": min(scores),
        "maximum": max(scores),
        "population_stdev": statistics.pstdev(scores),
        "hard_failure_count": sum(
            bool(run.get("hard_failures")) for run in runs
        ),
        "mean_elapsed_seconds": statistics.fmean(
            run["elapsed_seconds"] for run in runs
        ),
        "check_pass_rates": {
            name: sum(bool(run["checks"][name]) for run in runs) / len(runs)
            for name in CHECK_WEIGHTS
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Aggregate manually reviewed qa-pr benchmark scorecards."
    )
    parser.add_argument("scorecard", type=Path)
    args = parser.parse_args()
    document = json.loads(args.scorecard.read_text())
    print(json.dumps(summarize(document), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
