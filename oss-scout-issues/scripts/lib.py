"""Shared helpers for oss-scout-issues. Auth via the `gh` CLI.

Deliberately self-contained rather than importing oss-scout's lib: skills should
stand alone, at the cost of ~50 duplicated lines.
"""

import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

CORE_PACE = 0.75

NOISE_TITLES = ("dependency dashboard", "dependency updates", "roadmap", "tracking issue")

# Phrases that mean a human has already staked a claim in the comments.
CLAIM_PHRASES = (
    "i'll take", "i will take", "i'd like to work", "i would like to work",
    "working on this", "i'm on it", "im on it", "assign me", "can i work",
    "picking this up", "i'll pick", "taking this", "started working",
)


def log(msg):
    print(msg, file=sys.stderr, flush=True)


class RateLimited(Exception):
    pass


def gh(args, tries=5):
    """Run gh. Backs off on secondary limits; raises loudly on anything else."""
    for attempt in range(tries):
        r = subprocess.run(["gh"] + args, capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout) if r.stdout.strip() else None
        err = (r.stderr + r.stdout).lower()
        if "secondary rate limit" in err or "abuse detection" in err:
            wait = 25 * (attempt + 1)
            log(f"    secondary limit; sleeping {wait}s")
            time.sleep(wait)
            continue
        if "rate limit" in err:
            raise RateLimited(r.stderr.strip()[:200])
        raise RuntimeError(f"gh failed: {' '.join(args)[:70]} :: {r.stderr.strip()[:200]}")
    raise RateLimited("still limited after retries")


def cache_path(repo):
    return os.path.join(DATA, repo.replace("/", "__") + ".json")


def read_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def parse_repo(s):
    s = s.strip().removeprefix("https://github.com/").rstrip("/")
    parts = s.split("/")
    if len(parts) != 2 or not all(parts):
        raise SystemExit(f"expected owner/name, got: {s!r}")
    return parts[0], parts[1]
