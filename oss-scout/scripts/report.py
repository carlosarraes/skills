#!/usr/bin/env python3
"""Query the corpus by theme and emit a ranked shortlist. No API calls, no cost."""

import argparse
import os
from collections import Counter

from lib import CORPUS, DATA, DOMAINS, log, read_jsonl


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--theme", nargs="*", default=[],
                    help=f"domains to match (any of): {', '.join(DOMAINS)}")
    ap.add_argument("--min-approachability", type=int, default=3)
    ap.add_argument("--min-issue-quality", type=int, default=3)
    ap.add_argument("--allow-red-flags", action="store_true")
    ap.add_argument("--limit", type=int, default=25)
    ap.add_argument("--out", default=os.path.join(DATA, "shortlist.md"))
    args = ap.parse_args()

    all_rows = read_jsonl(CORPUS)
    # Health-rejected repos live in the corpus purely so they are never re-fetched.
    corpus = [r for r in all_rows if not r.get("verdict")]
    rejected = len(all_rows) - len(corpus)
    if not corpus:
        log(f"no classified repos yet ({rejected} health-rejected); "
            "run discover.py then classify.py")
        return

    bad = [t for t in args.theme if t not in DOMAINS]
    if bad:
        log(f"unknown domain(s): {bad}\nvalid: {', '.join(DOMAINS)}")
        return

    rows = []
    for r in corpus:
        if args.theme and not (set(r.get("domains", [])) & set(args.theme)):
            continue
        if not r.get("needs_help"):
            continue
        if r.get("approachability", 0) < args.min_approachability:
            continue
        if r.get("issue_quality", 0) < args.min_issue_quality:
            continue
        if r.get("red_flags") and not args.allow_red_flags:
            continue
        rows.append(r)

    # Approachability first, then issue quality; fewer stars breaks ties because
    # a single PR is more visible in a smaller project.
    rows.sort(key=lambda r: (-r["approachability"], -r["issue_quality"], r.get("stars", 0)))
    rows = rows[:args.limit]

    theme = ", ".join(args.theme) if args.theme else "any"
    out = [f"# oss-scout shortlist", "",
           f"theme: **{theme}** · corpus: {len(corpus)} repos · matched: {len(rows)}", ""]
    for r in rows:
        out.append(f"## [{r['repo']}](https://github.com/{r['repo']})")
        out.append(f"{r.get('stars',0)}★ · {r.get('lang','?')} · "
                   f"created {r.get('created','?')} · pushed {r.get('pushed','?')} · "
                   f"domains: {', '.join(r.get('domains',[])) or '-'}")
        out.append(f"approachability {r['approachability']}/5 · "
                   f"issue quality {r['issue_quality']}/5")
        out.append(f"> {r.get('reason','')}")
        out.append("")
        for i in r.get("issues", [])[:4]:
            out.append(f"- [{i['l']}] [{i['t']}]({i['u']})")
        out.append("")

    text = "\n".join(out)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        f.write(text)

    dist = Counter(d for r in corpus for d in r.get("domains", []))
    log(f"corpus {len(corpus)} classified (+{rejected} health-rejected); "
        f"domains: {dict(dist.most_common(8))}")
    log(f"matched {len(rows)} -> {args.out}")
    print(text)


if __name__ == "__main__":
    main()
