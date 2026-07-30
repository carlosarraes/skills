#!/usr/bin/env python3
"""Rank a repo's open issues by difficulty, clarity and how taken they are.

  scan.py posthog/posthog
  scan.py Byron/dua-cli --max-verify 20

Writes data/<owner>__<repo>.json. Re-render for free with show.py.
"""

import argparse
import json
import re
import subprocess
import time
from collections import Counter
from datetime import date, datetime, timedelta

from lib import (BLOCKING_LABELS, CLAIM_PHRASES, CORE_PACE, NOISE_TITLES, RateLimited,
                 cache_path, gh, log, parse_repo, write_json)

MODEL = "deepseek-v4-flash"
PROVIDER = "opencode-go"

ISSUE_PROMPT = """You triage open-source issues for someone choosing what to contribute.

Return ONLY a JSON array, one object per issue, same order, no prose:
[{{"number":1,"difficulty":"easy","scope":"one-file","clarity":0,"kind":"bug","reason":"..."}}]

Fields:
- difficulty: "easy" | "medium" | "hard". Judge the work, not the wording. "easy" = a competent outsider could do it without insider context.
- scope: "one-file" | "few-files" | "cross-cutting" | "unclear"
- clarity: 0-5. Is it actionable AS WRITTEN? 5 = states the problem and what done looks like. 0 = vague wish or a question.
- kind: "bug" | "feature" | "docs" | "test" | "refactor" | "perf" | "chore"
- reason: max 120 chars, concrete, mention what the work actually involves.

Issues:
{payload}"""

CV_PROMPT = """Judge how much weight "contributed to this project" carries with hiring managers.

Return ONLY JSON, no prose:
{{"cv_signal":0,"recognized":true,"audience":"...","reason":"..."}}

- cv_signal: 0-5. 5 = a widely recognized project a hiring manager would know by name (major company OSS, core language/infra tooling). 3 = respected within its niche. 0 = obscure personal project.
- recognized: true if an engineer outside this project's niche would plausibly recognize the name.
- audience: who is impressed by this, max 60 chars.
- reason: max 140 chars.

Project:
{payload}"""


def run_model(prompt, model, provider, timeout=300):
    p = subprocess.run(
        ["pi", "--provider", provider, "--model", model, "-p",
         "--no-tools", "--no-session", prompt],
        capture_output=True, text=True, timeout=timeout)
    if p.returncode != 0:
        raise RuntimeError(f"pi failed: {p.stderr.strip()[:200]}")
    return p.stdout


def extract(text, opener, closer):
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    a, b = text.find(opener), text.rfind(closer)
    if a == -1 or b == -1:
        raise ValueError("no JSON found in model output")
    return json.loads(text[a:b + 1])


def fetch_issues(owner, name, max_pages):
    """Bulk-list open issues. One call per 100, body and labels included."""
    out, page = [], 1
    while page <= max_pages:
        rows = gh(["api", "-X", "GET", f"repos/{owner}/{name}/issues",
                   "-f", "state=open", "-f", "per_page=100", "-f", f"page={page}",
                   "-f", "sort=created", "-f", "direction=desc"])
        time.sleep(CORE_PACE)
        if not rows:
            break
        out.extend(rows)
        if len(rows) < 100:
            break
        page += 1
    return out


def drop_reason(it, max_comments, max_age_days):
    """Why this item is not a candidate, or None if it is. Reasons get tallied."""
    # The issues endpoint returns pull requests too; they are not issues.
    if it.get("pull_request"):
        return "is-a-pr"
    if it.get("assignee") or it.get("assignees"):
        return "assigned"
    if it.get("locked"):
        return "locked"
    if (it.get("user") or {}).get("login", "").endswith("[bot]"):
        return "bot-authored"
    if any(n in it["title"].lower() for n in NOISE_TITLES):
        return "meta-issue"
    labels = [(l.get("name") or "").lower() for l in it.get("labels", [])]
    for lab in labels:
        if any(b in lab for b in BLOCKING_LABELS):
            return f"blocked:{lab}"
    if it.get("comments", 0) > max_comments:
        return "too-crowded"
    created = datetime.fromisoformat(it["created_at"].replace("Z", "+00:00")).date()
    if created < date.today() - timedelta(days=max_age_days):
        return "too-old"
    return None


def verify_taken(owner, name, numbers):
    """One GraphQL call for all finalists: linked PRs + claim language in comments."""
    if not numbers:
        return {}
    parts = []
    for n in numbers:
        parts.append(f"""
        i{n}: issue(number: {n}) {{
          number
          timelineItems(itemTypes: [CROSS_REFERENCED_EVENT], last: 15) {{
            nodes {{ ... on CrossReferencedEvent {{
              source {{ ... on PullRequest {{ number state url }} }} }} }}
          }}
          comments(last: 5) {{ nodes {{ body }} }}
        }}""")
    query = ("query($owner:String!,$name:String!){repository(owner:$owner,name:$name){"
             + "".join(parts) + "}}")
    d = gh(["api", "graphql", "-f", f"query={query}",
            "-F", f"owner={owner}", "-F", f"name={name}"])
    repo = ((d or {}).get("data") or {}).get("repository") or {}
    out = {}
    for key, node in repo.items():
        if not isinstance(node, dict) or "number" not in node:
            continue
        prs = []
        for ev in (node.get("timelineItems") or {}).get("nodes") or []:
            src = (ev or {}).get("source") or {}
            if src.get("number") and src.get("state") != "CLOSED":
                prs.append({"number": src["number"], "state": src.get("state"),
                            "url": src.get("url")})
        claimed = False
        for c in (node.get("comments") or {}).get("nodes") or []:
            body = (c.get("body") or "").lower()
            if any(p in body for p in CLAIM_PHRASES):
                claimed = True
                break
        out[node["number"]] = {"open_prs": prs, "claimed": claimed}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo", help="owner/name or a github URL")
    ap.add_argument("--max-comments", type=int, default=3,
                    help="drop issues with more comments (crowded); default 3")
    ap.add_argument("--max-age-days", type=int, default=730)
    ap.add_argument("--max-pages", type=int, default=20, help="100 issues per page")
    ap.add_argument("--max-judge", type=int, default=120, help="issues sent to the model")
    ap.add_argument("--max-verify", type=int, default=20, help="finalists GraphQL-checked")
    ap.add_argument("--batch-size", type=int, default=20)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--provider", default=PROVIDER)
    args = ap.parse_args()

    owner, name = parse_repo(args.repo)
    repo = f"{owner}/{name}"

    info = gh(["api", f"repos/{repo}"])
    time.sleep(CORE_PACE)
    org = gh(["api", f"users/{owner}"])
    time.sleep(CORE_PACE)

    log(f"{repo}: {info.get('stargazers_count')}* "
        f"{info.get('open_issues_count')} open issues, owner type {org.get('type')}")

    # CV signal is a property of the project, so judge it once.
    cv_payload = json.dumps({
        "repo": repo, "desc": info.get("description"),
        "topics": info.get("topics", []), "stars": info.get("stargazers_count"),
        "forks": info.get("forks_count"), "language": info.get("language"),
        "owner_type": org.get("type"), "owner_company": org.get("company"),
        "owner_public_repos": org.get("public_repos"),
        "owner_followers": org.get("followers"), "homepage": info.get("homepage"),
    }, ensure_ascii=False)
    try:
        cv = extract(run_model(CV_PROMPT.format(payload=cv_payload),
                               args.model, args.provider), "{", "}")
    except Exception as e:
        log(f"CV judgement failed ({type(e).__name__}); continuing without it")
        cv = {}

    raw = fetch_issues(owner, name, args.max_pages)
    cands, dropped = [], Counter()
    for it in raw:
        why = drop_reason(it, args.max_comments, args.max_age_days)
        if why is None:
            cands.append(it)
        else:
            dropped[why.split(":")[0]] += 1
    log(f"fetched {len(raw)} open items -> {len(cands)} candidates")
    log(f"  dropped: {dict(dropped.most_common())}")
    if not cands:
        log("nothing to rank (all assigned, too crowded, or too old)")
        return

    cands = cands[:args.max_judge]
    judged = {}
    for n in range(0, len(cands), args.batch_size):
        batch = cands[n:n + args.batch_size]
        payload = json.dumps([{
            "number": it["number"], "title": it["title"],
            "labels": [l["name"] for l in it.get("labels", [])][:8],
            "body": (it.get("body") or "")[:900],
            "comments": it.get("comments", 0),
        } for it in batch], ensure_ascii=False)
        try:
            rows = extract(run_model(ISSUE_PROMPT.format(payload=payload),
                                     args.model, args.provider), "[", "]")
        except Exception as e:
            log(f"  batch {n // args.batch_size}: {type(e).__name__}: {str(e)[:110]}")
            continue
        allowed = {it["number"] for it in batch}
        for r in rows:
            if isinstance(r, dict) and r.get("number") in allowed:
                judged[r["number"]] = r
        log(f"  judged {len(judged)}/{len(cands)}")

    by_num = {it["number"]: it for it in cands}
    rows = []
    for num, j in judged.items():
        it = by_num[num]
        try:
            clarity = max(0, min(5, int(j.get("clarity", 0))))
        except (TypeError, ValueError):
            clarity = 0
        rows.append({
            "number": num, "title": it["title"], "url": it["html_url"],
            "labels": [l["name"] for l in it.get("labels", [])][:8],
            "comments": it.get("comments", 0), "created": it["created_at"][:10],
            "difficulty": j.get("difficulty", "unclear"),
            "scope": j.get("scope", "unclear"),
            "kind": j.get("kind", ""), "clarity": clarity,
            "reason": str(j.get("reason", ""))[:120],
        })

    # Clearest first; that is what makes an issue safe to start on.
    rows.sort(key=lambda r: (-r["clarity"], r["comments"], r["number"]))

    finalists = [r["number"] for r in rows[:args.max_verify]]
    try:
        taken = verify_taken(owner, name, finalists)
    except (RateLimited, RuntimeError) as e:
        log(f"verification skipped: {str(e)[:120]}")
        taken = {}
    for r in rows:
        v = taken.get(r["number"])
        r["verified"] = v is not None
        r["open_prs"] = (v or {}).get("open_prs", [])
        r["claimed"] = (v or {}).get("claimed", False)

    out = {
        "repo": repo, "scanned_at": date.today().isoformat(),
        "stars": info.get("stargazers_count"), "language": info.get("language"),
        "open_issues": info.get("open_issues_count"),
        "owner_type": org.get("type"), "cv": cv,
        "n_fetched": len(raw), "n_candidates": len(cands),
        "n_verified": len(taken), "issues": rows,
    }
    write_json(cache_path(repo), out)
    blocked = sum(1 for r in rows if r["open_prs"] or r["claimed"])
    log(f"\nranked {len(rows)} issues; {blocked} of the top {len(finalists)} already taken")
    log(f"cv_signal {cv.get('cv_signal','?')}/5 -> {cv.get('reason','')[:90]}")
    log(f"next: scripts/show.py {repo}")


if __name__ == "__main__":
    main()
