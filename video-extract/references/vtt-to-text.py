#!/usr/bin/env python3
"""Convert a YouTube VTT subtitle file to clean, deduplicated plain text.

YouTube auto-caption VTT is full of noise: cue timestamps, inline `<c>` /
`<00:00:00.000>` word-timing tags, `[Music]`-style annotations, and — worst —
"rolling" captions that repeat each line 2-3× as words scroll in. This strips
all of that and collapses the repeats into readable prose.

Usage: python3 vtt-to-text.py talk.en.vtt > talk.txt
"""
import re
import sys


def vtt_to_text(path: str) -> str:
    lines = open(path, encoding="utf-8").read().splitlines()
    out, seen = [], None
    for ln in lines:
        if "-->" in ln or ln.strip() in ("WEBVTT", "") or ln.startswith(
            ("Kind:", "Language:", "NOTE")
        ):
            continue
        t = re.sub(r"<[^>]+>", "", ln)        # drop <c>, <00:00:00.000> tags
        t = re.sub(r"\[.*?\]", "", t).strip()  # drop [Music], [Applause]
        if not t or t == seen:
            continue
        seen = t
        out.append(t)
    # collapse consecutive duplicate lines left by rolling captions
    clean = []
    for t in out:
        if not clean or clean[-1] != t:
            clean.append(t)
    return " ".join(clean)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: vtt-to-text.py <file.vtt>")
    sys.stdout.write(vtt_to_text(sys.argv[1]) + "\n")
