---
name: stamp-check
description: >
  Use when the user is asked to approve ("stamp") a teammate's small PR, wants a
  merge-readiness gate on a low-risk PR, or says "stamp-check #123", "can I stamp
  this?", "is this PR safe to approve?", "stamp this for me". Takes a PR number or
  URL. Checks deterministic policy gates before any judgment and never posts an
  approval without explicit user confirmation.
---

# Stamp Check: low-risk PR approval gate

Decides whether a small PR is safe to approve without deep review — the way a
busy teammate stamps a colleague's obviously-fine change — and refuses or routes
everything else. Deterministic gates run FIRST; the LLM only sees diffs that
already passed them. Modeled on PostHog's StampHog.

Verdicts: **STAMP** (post a bare approval, after user confirm), **REFUSE** (deny
with reason + risk), or **ESCALATE** (route to the right human).

## Policy

Use `.stamp-policy.yml` at the target repo's root when present; otherwise these
defaults. Each deny rule carries a `rationale` recording why it exists — history,
like a commit message.

```yaml
deny_paths:          # any changed file matching → never stamp
  - pattern: "(auth|permission|session|sso|oauth)"          # rationale: privilege changes need a human
  - pattern: "(secret|credential|token|\\.env)"             # rationale: leaked-credential blast radius
  - pattern: "(billing|payment|invoice|charge|subscription)" # rationale: money paths
  - pattern: "(migrations/|\\.sql$)"                        # rationale: schema changes are one-way doors
  - pattern: "(\\.github/workflows|bitbucket-pipelines)"    # rationale: CI runs with elevated permissions
  - pattern: "(api/public|/sdk/|openapi)"                   # rationale: public contract changes
  - pattern: "\\.stamp-policy\\.yml$"                        # rationale: self-governance — the gate never stamps its own rules
size_gate:
  max_lines: 500     # additions + deletions, excluding lockfiles and generated files
  max_files: 20
```

**Self-governance is non-negotiable:** a PR touching `.stamp-policy.yml` or this
skill's own file can never be stamped, even if every other gate passes.

## Workflow

### Step 1: Deterministic gates — no LLM, in this order

Fetch once:

```bash
gh pr view <#> --repo <o/r> --json state,isDraft,mergeable,reviewDecision,files,additions,deletions,author,title,url,headRefOid
gh pr checks <#> --repo <o/r> || true   # non-zero exit just means something isn't green
```

1. **State**: open, not draft, `mergeable != CONFLICTING`, no `CHANGES_REQUESTED`
   review decision, CI green (latest run per check). Any miss → **REFUSE** with the
   failing fact.
2. **Deny-list**: every changed file path tested against `deny_paths`. Any hit →
   **ESCALATE**, naming the file and the rule's rationale.
3. **Size**: effective diff (excluding lockfiles and generated files) within
   `max_lines` and `max_files`. Over → **REFUSE** with the numbers ("too big to
   stamp — needs a real review or `split-pr`").

A gate failure short-circuits: later gates and the LLM pass never run. Report which
gate refused — determinism is the point; the same PR always fails the same way.

### Step 2: LLM showstopper pass — one bounded read

Only for PRs that passed every gate. Read the full diff (`gh pr diff <#>`) once and
ask a single question: **is there anything a careful human stamper would refuse
over?** Obvious bugs, logic inversions, deleted tests, debug/logging left in,
suspicious obfuscation, changes that don't match the PR title. This is not a review
— no nits, no style, no suggestions. Binary: showstopper found / not found.

Showstopper found → **REFUSE**, citing it in 1–2 sentences.

### Step 3: Verdict

**STAMP** — present a one-screen summary (title, author, files, effective size,
gates passed, LLM verdict) and ask the user to confirm. Only after an explicit yes:

```bash
gh pr review <#> --repo <o/r> --approve --body "$(cat <<'EOF'
> [!NOTE]
> 🤖 Automated comment by **Stamp Check** — not written by a human

Stamp: passed deterministic gates (state, deny-list, size) and the showstopper scan.
EOF
)"
```

A bare approval, no inline comments. **Never approve without the confirm — no
exception for "obviously fine", batch runs, or being asked twice.**

**REFUSE / ESCALATE** — never silent; always output:

- **Reason** (1–2 sentences, the specific gate or showstopper)
- **Risk level**: low / medium / high
- **Next step**: for ESCALATE, name the routing target — CODEOWNERS entry for the
  matched path if one exists, else the person `git log -5 --format='%an' -- <file>`
  shows touching the denied file most recently ("blame familiarity"); for REFUSE,
  the concrete unblock ("wait for CI", "resolve the conflict", "split it with
  `split-pr`", "needs a real review").

## Constraints

- Deterministic gates always run before and independently of any LLM judgment.
- Never stamp your own PRs (author == the user) — GitHub forbids self-approval and
  the gate's purpose is a second pair of eyes; run `review-swarm` instead.
- Never leave inline comments — a stamp is a bare approval; anything worth a
  comment is worth REFUSE.
- Never dismiss or override existing reviews.
- One PR per invocation unless the user passes an explicit list; report each PR's
  verdict separately, and confirm each STAMP separately.
