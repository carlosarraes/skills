"""Shared helpers for oss-scout. Auth comes from the `gh` CLI, so no tokens here."""

import contextlib
import json
import os
import subprocess
import sys
import time
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")

CORPUS = os.path.join(DATA, "corpus.jsonl")
PENDING = os.path.join(DATA, "pending.jsonl")
SLICES = os.path.join(DATA, "slices.json")

# GitHub trips *secondary* (burst) limits long before the hourly quota. Search is
# far touchier than core: 2s spacing failed in testing, 3.5s holds.
SEARCH_PACE = 3.5
CORE_PACE = 0.75

# Renovate/Dependabot meta-issues stay open forever and are not real work.
NOISE_TITLES = ("dependency dashboard", "dependency updates", "roadmap", "tracking issue")

DOMAINS = [
    "systems", "database", "backend", "frontend", "cli", "devops", "networking",
    "security", "ml", "embedded", "graphics", "compiler", "testing", "docs",
    "mobile", "gamedev", "data",
]


def log(msg):
    print(msg, file=sys.stderr, flush=True)


def _alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    return True


@contextlib.contextmanager
def exclusive(name="corpus"):
    """Refuse to run while another stage holds the data files.

    discover.py appends to pending.jsonl and classify.py rewrites it, so two
    concurrent runs — of the same stage or different ones — duplicate work
    against the same queue. One lock covers both.
    """
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f".{name}.lock")
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        try:
            pid = int((open(path).read().strip() or "0"))
        except (ValueError, OSError):
            pid = 0
        if pid and _alive(pid):
            raise SystemExit(
                f"another oss-scout run holds the lock (pid {pid}).\n"
                f"wait for it, or remove {path} if you are sure it is dead.")
        log(f"clearing stale lock (pid {pid or 'unknown'} is gone)")
        os.unlink(path)
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(fd, str(os.getpid()).encode())
        os.close(fd)
        yield
    finally:
        try:
            os.unlink(path)
        except FileNotFoundError:
            pass


class RateLimited(Exception):
    pass


def gh(args, tries=5):
    """Run a gh api call. Backs off on secondary limits, raises on everything else.

    Returning None on error is how a previous version silently lost 3 of 4
    languages, so unexpected failures are loud.
    """
    for attempt in range(tries):
        r = subprocess.run(["gh"] + args, capture_output=True, text=True)
        if r.returncode == 0:
            return json.loads(r.stdout)
        err = r.stderr.lower() + r.stdout.lower()
        if "secondary rate limit" in err or "abuse detection" in err:
            wait = 25 * (attempt + 1)
            log(f"    secondary limit; sleeping {wait}s")
            time.sleep(wait)
            continue
        if "rate limit" in err:
            raise RateLimited(r.stderr.strip()[:200])
        raise RuntimeError(f"gh failed: {' '.join(args)[:80]} :: {r.stderr.strip()[:200]}")
    raise RateLimited("still rate limited after retries")


def core_remaining():
    d = gh(["api", "rate_limit", "--jq", ".resources.core"])
    return d["remaining"]


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def append_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def read_json(path, default):
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)  # atomic, so a kill mid-write can't corrupt the ledger


def corpus_repos():
    return {r["repo"] for r in read_jsonl(CORPUS)}


def month_windows(start="2024-01", end=None):
    """Inclusive month windows [(YYYY-MM-DD, YYYY-MM-DD)] up to the staleness cutoff.

    Date windows are the partition key because GitHub issue search silently
    ignores `stars:` — it returns 0 hits rather than an error, which would burn
    every slice with a false zero. Every issue has exactly one creation date, so
    windows are provably exhaustive, non-overlapping, and subdividable.
    """
    if end is None:
        end = (date.today() - timedelta(days=60)).strftime("%Y-%m")
    y, m = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out = []
    while (y, m) <= (ey, em):
        first = date(y, m, 1)
        last = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
        out.append((first.isoformat(), last.isoformat()))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def split_window(lo, hi):
    """Halve a window that hit the 1000-result cap."""
    a, b = date.fromisoformat(lo), date.fromisoformat(hi)
    if (b - a).days < 1:
        return None
    mid = a + (b - a) // 2
    return [(a.isoformat(), mid.isoformat()),
            ((mid + timedelta(days=1)).isoformat(), b.isoformat())]


def slice_id(lang, label, lo, hi):
    return f"{lang}|{label}|{lo}..{hi}"
