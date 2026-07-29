#!/usr/bin/env python3
"""Render a cached scan. Free to re-run with different filters.

  show.py Byron/dua-cli
  show.py posthog/posthog --difficulty easy medium --hide-taken
"""

import argparse

from lib import cache_path, log, parse_repo, read_json

BADGE = {"easy": "easy  ", "medium": "medium", "hard": "hard  "}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repo")
    ap.add_argument("--difficulty", nargs="*", default=[],
                    choices=["easy", "medium", "hard", "unclear"])
    ap.add_argument("--kind", nargs="*", default=[])
    ap.add_argument("--min-clarity", type=int, default=3)
    ap.add_argument("--hide-taken", action="store_true",
                    help="drop issues with an open PR or a comment claiming them")
    ap.add_argument("--limit", type=int, default=15)
    args = ap.parse_args()

    owner, name = parse_repo(args.repo)
    repo = f"{owner}/{name}"
    d = read_json(cache_path(repo))
    if not d:
        log(f"no cached scan for {repo}; run scripts/scan.py {repo}")
        return

    rows = d["issues"]
    if args.difficulty:
        rows = [r for r in rows if r["difficulty"] in args.difficulty]
    if args.kind:
        rows = [r for r in rows if r.get("kind") in args.kind]
    rows = [r for r in rows if r["clarity"] >= args.min_clarity]
    if args.hide_taken:
        rows = [r for r in rows if not r["open_prs"] and not r["claimed"]]

    cv = d.get("cv") or {}
    print(f"# {repo}")
    print()
    print(f"{d.get('stars')}★ · {d.get('language')} · {d.get('open_issues')} open issues "
          f"· owner: {d.get('owner_type')} · scanned {d.get('scanned_at')}")
    print()
    print(f"**CV signal {cv.get('cv_signal','?')}/5** — {cv.get('reason','(not judged)')}")
    if cv.get("audience"):
        print(f"Impresses: {cv['audience']}")
    print()
    print(f"Showing {len(rows)} of {len(d['issues'])} ranked "
          f"({d.get('n_candidates')} candidates from {d.get('n_fetched')} open items; "
          f"top {d.get('n_verified')} verified for competition)")
    print()

    if not rows:
        print("_Nothing matched these filters._")
        return

    for r in rows[:args.limit]:
        flags = []
        if r["open_prs"]:
            prs = ", ".join(f"#{p['number']}" for p in r["open_prs"])
            flags.append(f"**TAKEN — open PR {prs}**")
        if r["claimed"]:
            flags.append("**claimed in comments**")
        if not r["verified"]:
            flags.append("_competition not checked_")
        print(f"### [#{r['number']} {r['title']}]({r['url']})")
        print(f"`{BADGE.get(r['difficulty'], r['difficulty'])}` · {r['scope']} · "
              f"{r.get('kind','')} · clarity {r['clarity']}/5 · "
              f"{r['comments']} comments · opened {r['created']}")
        if r["labels"]:
            print(f"labels: {', '.join(r['labels'])}")
        if flags:
            print(" · ".join(flags))
        print(f"> {r['reason']}")
        print()


if __name__ == "__main__":
    main()
