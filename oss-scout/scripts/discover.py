#!/usr/bin/env python3
"""Burn unburned query slices, collect unclaimed issues, queue new repos.

Writes data/pending.jsonl (repos awaiting classification) and checkpoints
data/slices.json after every slice, so a kill costs one slice, not the run.
"""

import argparse
import time
from datetime import date, timedelta

from lib import (CORE_PACE, CORPUS, NOISE_TITLES, PENDING, SEARCH_PACE, SLICES,
                 RateLimited, append_jsonl, corpus_repos, core_remaining, gh, log,
                 month_windows, read_json, read_jsonl, slice_id, split_window,
                 write_json)

LANGS = ["rust", "go", "python", "typescript"]
LABELS = ["help wanted", "good first issue"]

# Mechanical gate, applied before any model call. The age rule is the highest
# yield filter we have: it rejected 65% of candidates in testing, nearly all
# brand-new repos that bulk-created issues at launch.
MIN_STARS, MAX_STARS = 80, 30000
MAX_PUSH_AGE_DAYS = 90
MIN_REPO_AGE_DAYS = 180


def build_queue(state):
    """Seed slices, then append any subdivisions recorded from truncated slices."""
    q = []
    for lang in LANGS:
        for label in LABELS:
            for lo, hi in month_windows():
                q.append((lang, label, lo, hi))
    for sid, meta in state.items():
        for lo, hi in meta.get("split_into", []):
            lang, label, _ = sid.split("|", 2)
            q.append((lang, label, lo, hi))
    return q


def search_slice(lang, label, lo, hi):
    """Drain one slice. Returns (issues, truncated)."""
    q = (f'label:"{label}" state:open is:issue no:assignee comments:0 '
         f"archived:false language:{lang} created:{lo}..{hi}")
    issues, page, total = [], 1, None
    while page <= 10:  # API hard-caps at 1000 results (10 x 100)
        d = gh(["api", "-X", "GET", "search/issues", "-f", f"q={q}",
                "-f", "per_page=100", "-f", f"page={page}"])
        time.sleep(SEARCH_PACE)
        if total is None:
            total = d.get("total_count", 0)
        items = d.get("items", [])
        for it in items:
            if it.get("user", {}).get("login", "").endswith("[bot]"):
                continue
            if any(n in it["title"].lower() for n in NOISE_TITLES):
                continue
            issues.append({
                "repo": "/".join(it["html_url"].split("/")[3:5]),
                "lang": lang, "label": label, "title": it["title"],
                "url": it["html_url"], "created": it["created_at"][:10],
            })
        if len(items) < 100:
            break
        page += 1
    return issues, (total or 0) >= 1000


def healthy(info):
    if not info or info.get("archived") or info.get("fork"):
        return False
    stars = info.get("stargazers_count", 0)
    if not (MIN_STARS <= stars <= MAX_STARS):
        return False
    today = date.today()
    pushed = info.get("pushed_at", "")[:10]
    created = info.get("created_at", "")[:10]
    if not pushed or not created:
        return False
    if date.fromisoformat(pushed) < today - timedelta(days=MAX_PUSH_AGE_DAYS):
        return False
    if date.fromisoformat(created) > today - timedelta(days=MIN_REPO_AGE_DAYS):
        return False
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--budget", type=int, default=4000,
                    help="max GitHub core calls to spend (default 4000)")
    ap.add_argument("--max-slices", type=int, default=100)
    args = ap.parse_args()

    state = read_json(SLICES, {})
    known = corpus_repos() | {r["repo"] for r in read_jsonl(PENDING)}
    remaining = core_remaining()
    budget = min(args.budget, max(0, remaining - 200))  # leave headroom
    log(f"core quota {remaining}; spending up to {budget}; corpus has {len(known)} repos")
    if budget <= 0:
        log("no quota available; try again after the hourly reset")
        return

    queue = [s for s in build_queue(state) if slice_id(*s) not in state]
    log(f"{len(queue)} unburned slices")

    spent, burned, queued = 0, 0, 0
    for lang, label, lo, hi in queue[:args.max_slices]:
        sid = slice_id(lang, label, lo, hi)
        if spent >= budget:
            log("budget spent; stopping cleanly")
            break
        try:
            issues, truncated = search_slice(lang, label, lo, hi)
        except RateLimited as e:
            log(f"rate limited, stopping cleanly: {e}")
            break

        by_repo = {}
        for i in issues:
            by_repo.setdefault(i["repo"], []).append(i)
        fresh = [r for r in by_repo if r not in known]

        new_rows, rejects = [], []
        interrupted = False
        for repo in fresh:
            if spent >= budget:
                interrupted = True
                break
            try:
                info = gh(["api", f"repos/{repo}"])
            except RateLimited:
                log("  rate limited during repo lookup")
                interrupted = True
                break
            except RuntimeError as e:
                log(f"  skip {repo}: {e}")
                known.add(repo)
                rejects.append({"repo": repo, "verdict": "lookup-failed"})
                continue
            spent += 1
            time.sleep(CORE_PACE)
            known.add(repo)
            if not healthy(info):
                # Persisted so the health gate is never paid for twice.
                rejects.append({"repo": repo, "verdict": "health-reject"})
                continue
            new_rows.append({
                "repo": repo,
                "lang": info.get("language") or lang,
                "stars": info.get("stargazers_count", 0),
                "forks": info.get("forks_count", 0),
                "created": info.get("created_at", "")[:10],
                "pushed": info.get("pushed_at", "")[:10],
                "desc": (info.get("description") or "")[:200],
                "topics": (info.get("topics") or [])[:12],
                "issues": [{"t": i["title"][:140], "u": i["url"], "l": i["label"]}
                           for i in by_repo[repo][:6]],
            })

        if new_rows:
            append_jsonl(PENDING, new_rows)
            queued += len(new_rows)
        if rejects:
            append_jsonl(CORPUS, rejects)

        if interrupted:
            # Marking a half-processed slice done would silently drop every repo
            # we never reached, while the ledger claimed full coverage.
            log(f"  {sid}: stopped mid-slice; left unburned "
                f"({len(new_rows)} queued, {len(rejects)} rejected so far)")
            break

        entry = {"done": True, "n_issues": len(issues), "n_repos": len(by_repo),
                 "n_queued": len(new_rows), "truncated": truncated,
                 "ran_at": date.today().isoformat()}
        if truncated:
            parts = split_window(lo, hi)
            if parts:
                entry["split_into"] = parts
                log(f"  {sid}: hit 1000 cap -> split into {len(parts)} windows")
        state[sid] = entry
        write_json(SLICES, state)  # checkpoint every slice
        burned += 1
        log(f"  {sid}: {len(issues)} issues, {len(by_repo)} repos, {len(new_rows)} queued "
            f"(spent {spent}/{budget})")

    left = len([s for s in build_queue(state) if slice_id(*s) not in state])
    log(f"\nburned {burned} slices, queued {queued} repos, spent {spent} calls")
    log(f"{left} slices still unburned -> run again to continue")
    log(f"next: scripts/classify.py")


if __name__ == "__main__":
    main()
