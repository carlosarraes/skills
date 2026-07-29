#!/usr/bin/env python3
"""Classify pending repos with a cheap model via pi, append to the corpus.

Classification is deliberately theme-agnostic: the model emits a fixed domain
vocabulary rather than answering "does this match systems programming?". That
makes re-theming a local grep in report.py instead of a paid re-judgement.
"""

import argparse
import json
import re
import subprocess
import time

from lib import CORPUS, DOMAINS, PENDING, append_jsonl, log, read_jsonl, write_jsonl

MODEL = "deepseek-v4-flash"
PROVIDER = "opencode-go"

PROMPT = """You classify open-source repos for someone looking for a project to contribute to.

For EACH repo below, judge it from its metadata and its unclaimed issue titles.

Return ONLY a JSON array, one object per repo, same order, no prose:
[{{"repo":"owner/name","domains":["..."],"approachability":0,"issue_quality":0,"needs_help":true,"red_flags":["..."],"reason":"..."}}]

Fields:
- domains: 1-3 from exactly this list: {domains}. Classify what the PROJECT is, judged from its description and topics — never what its issues happen to touch. An ebook manager with a reproducible-builds issue is NOT "systems"; it stays whatever the product is. Build/CI/packaging work never makes a project "systems" or "devops".
- approachability: 0-5. Could a competent outsider land a PR without insider context? 5=yes clearly, 0=needs deep domain/insider knowledge.
- issue_quality: 0-5. Are the issue titles specific and actionable? 5=precise and self-contained, 0=vague or a wishlist.
- needs_help: true if this looks genuinely under-resourced and open to outside help.
- red_flags: any of ["bulk-generated-issues","ai-slop","abandoned","corporate-controlled","vague-issues"], else [].
- reason: max 140 chars, concrete.

Repos:
{payload}"""


def extract_json(text):
    """Models sometimes wrap JSON in prose or fences; recover the array."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start == -1 or end == -1:
        raise ValueError("no JSON array in model output")
    return json.loads(text[start:end + 1])


def classify(batch, model, provider, timeout):
    payload = json.dumps([
        {"repo": r["repo"], "desc": r["desc"], "topics": r["topics"],
         "lang": r["lang"], "stars": r["stars"], "created": r["created"],
         "issues": [i["t"] for i in r["issues"]]}
        for r in batch
    ], ensure_ascii=False)
    prompt = PROMPT.format(domains=", ".join(DOMAINS), payload=payload)

    proc = subprocess.run(
        ["pi", "--provider", provider, "--model", model, "-p",
         "--no-tools", "--no-session", prompt],
        capture_output=True, text=True, timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"pi failed: {proc.stderr.strip()[:200]}")
    return extract_json(proc.stdout)


def validate(obj, allowed):
    if not isinstance(obj, dict) or obj.get("repo") not in allowed:
        return None
    doms = [d for d in obj.get("domains", []) if d in DOMAINS][:3]

    def score(k):
        try:
            return max(0, min(5, int(obj.get(k, 0))))
        except (TypeError, ValueError):
            return 0

    return {
        "repo": obj["repo"], "domains": doms,
        "approachability": score("approachability"),
        "issue_quality": score("issue_quality"),
        "needs_help": bool(obj.get("needs_help", False)),
        "red_flags": [str(f)[:40] for f in obj.get("red_flags", [])][:5],
        "reason": str(obj.get("reason", ""))[:140],
        "model": obj.get("_model", ""),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch-size", type=int, default=25)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--provider", default=PROVIDER)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--limit", type=int, default=0, help="max repos this run (0=all)")
    args = ap.parse_args()

    pending = read_jsonl(PENDING)
    if not pending:
        log("nothing pending; run scripts/discover.py first")
        return
    if args.limit:
        pending = pending[:args.limit]
    log(f"classifying {len(pending)} repos via {args.provider}/{args.model}")

    done, failed = [], []
    for n in range(0, len(pending), args.batch_size):
        batch = pending[n:n + args.batch_size]
        allowed = {r["repo"] for r in batch}
        rows = None
        for attempt in range(2):
            try:
                rows = classify(batch, args.model, args.provider, args.timeout)
                break
            except Exception as e:
                log(f"  batch {n // args.batch_size}: {type(e).__name__}: {str(e)[:120]}")
                time.sleep(3)
        if rows is None:
            # Left in pending so the next run retries; never silently dropped.
            failed.extend(batch)
            continue

        by_repo = {}
        for obj in rows:
            if isinstance(obj, dict):
                obj["_model"] = args.model
                v = validate(obj, allowed)
                if v:
                    by_repo[v["repo"]] = v
        # A repo the model skipped stays pending rather than vanishing.
        for r in batch:
            if r["repo"] in by_repo:
                done.append({**by_repo[r["repo"]], "stars": r["stars"],
                             "lang": r["lang"], "created": r["created"],
                             "pushed": r["pushed"], "desc": r["desc"],
                             "issues": r["issues"]})
            else:
                failed.append(r)
        log(f"  batch {n // args.batch_size}: {len(by_repo)}/{len(batch)} classified")

    if done:
        append_jsonl(CORPUS, done)
    remaining = failed + read_jsonl(PENDING)[len(pending):]
    write_jsonl(PENDING, remaining)
    log(f"\nclassified {len(done)}; {len(remaining)} left pending (retried next run)")
    log("next: scripts/report.py --theme systems")


if __name__ == "__main__":
    main()
