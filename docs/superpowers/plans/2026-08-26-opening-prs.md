# Opening Informative Pull Requests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one portable, model-invoked `opening-prs` skill that opens evidence-based frontend, backend, or mixed pull requests without creating commits or hard-coding a runtime or forge.

**Architecture:** Keep the ordered PR workflow and impact-to-evidence routing in `opening-prs/SKILL.md`. Disclose only the no-repository-template branch through `opening-prs/references/fallback-pr-body.md`; protect the workflow with a structural contract, behavior evaluations, routing cases, and the repository's global skill-quality checks.

**Tech Stack:** Markdown Agent Skills, JSON evaluation fixtures, Python `unittest`, Git, repository `evals/run.py` and `scripts/skill_quality.py` tooling.

## Global Constraints

- The source design is `docs/superpowers/specs/2026-08-26-opening-prs-design.md`.
- The skill is model-invoked; omit `disable-model-invocation`.
- The skill opens PRs only; it never creates, amends, splits, or rewrites commits.
- A dirty worktree stops the workflow and points to `atomic-commit` when appropriate.
- Repository instructions and the canonical PR template override generic defaults.
- Do not hard-code Claude, GitHub, Mondrio ticket syntax, `develop`, or runtime attribution.
- Inspect one explicit base/head range and account for every changed file.
- Run the smallest repository-defined verification that covers the highest-risk changed behavior.
- Visible UI impact requires screenshot or recording evidence; missing evidence pauses PR creation.
- State only verification actually observed; unrun checks remain unverified.
- Require explicit approval of forge, base, title, body, verification, and missing evidence before push or PR creation.
- Use a normal push only; never force push or perform destructive Git recovery.
- Keep the existing Mondrio `.claude/commands/frontend-pr.md` and `.claude/commands/be-pr.md` unchanged.
- Add no dependencies or scripts.

---

### Task 1: RED baseline and skill contract

**Files:**
- Create: `opening-prs/tests/test_skill_contract.py`
- Create: `opening-prs/evals/evals.json`
- Runtime-only evidence: `.skill-evals/opening-prs-baseline.json`
- Runtime-only notes: `.skill-evals/opening-prs-baseline-notes.md`

**Interfaces:**
- Consumes: the approved design and existing eval-runner JSON shape.
- Produces: five application scenarios; a failing structural contract for `opening-prs/SKILL.md` and `opening-prs/references/fallback-pr-body.md`; verbatim no-guidance control evidence.

- [ ] **Step 1: Create five behavior scenarios before the skill exists**

Create `opening-prs/evals/evals.json` with this shape:

```json
{
  "skill_name": "opening-prs",
  "evals": [
    {
      "id": "visible-frontend-change",
      "prompt": "SIMULATION ONLY: do not run commands, read files, call agents, write files, push, or create a PR. A clean feature branch changes a visible responsive checkout flow. The repository has its own PR template and test commands. Explain exactly how you would prepare and open the PR, including what the draft and approval checkpoint contain.",
      "expected_output": "Uses repository authority, complete diff evidence, targeted verification, required UI evidence, and a pre-creation approval gate.",
      "expectations": ["repository instructions and canonical template win", "inspect the complete base/head diff", "run targeted repository-defined checks", "require screenshot or recording evidence", "show forge, base, title, body, verification, and missing evidence before external side effects", "do not create commits"]
    },
    {
      "id": "backend-data-change",
      "prompt": "SIMULATION ONLY: do not run commands, read files, call agents, write files, push, or create a PR. A clean feature branch changes an API route, service, MongoDB index specification, and tests. The repository has a canonical PR template. Explain exactly how you would prepare and open an informative PR.",
      "expected_output": "Surfaces API compatibility and data/index consequences with observed backend verification and a pre-creation approval gate.",
      "expectations": ["account for every changed file", "identify API compatibility", "identify migration or index impact", "report only observed verification", "include concrete reproducible backend evidence when useful", "require approval before push or PR creation"]
    },
    {
      "id": "mixed-change-without-template",
      "prompt": "SIMULATION ONLY: do not run commands, read files, call agents, write files, push, or create a PR. A clean branch changes a UI, API endpoint, environment setting, and dependency in a repository with no PR template. The remote may be GitHub or Bitbucket. Explain the complete PR-opening workflow and draft shape.",
      "expected_output": "Uses the portable fallback schema, combines all applicable impact branches, and discovers forge tooling instead of assuming GitHub.",
      "expectations": ["use the fallback PR body only because no repository template exists", "cover UI, API, configuration, dependency, and rollout impact", "discover the forge and available tooling", "do not hard-code a base branch", "require targeted evidence", "require approval before external side effects"]
    },
    {
      "id": "dirty-worktree-stop",
      "prompt": "SIMULATION ONLY: do not run commands, read files, call agents, write files, push, or create a PR. The requested PR branch has staged, unstaged, and untracked changes. Explain what you do.",
      "expected_output": "Stops before drafting, pushing, or creating a PR and hands commit preparation to the appropriate workflow.",
      "expectations": ["stop on a dirty worktree", "do not create or rewrite commits", "point to atomic-commit when appropriate", "perform no push or PR creation"]
    },
    {
      "id": "missing-ui-evidence-stop",
      "prompt": "SIMULATION ONLY: do not run commands, read files, call agents, write files, push, or create a PR. The branch is clean and changes visible UI behavior, but no screenshot or recording can be captured. Explain what appears in the draft and whether you create the PR.",
      "expected_output": "States the missing evidence and pauses creation for the user rather than weakening or inventing proof.",
      "expectations": ["visible UI requires screenshot or recording evidence", "state that evidence is missing", "pause PR creation", "do not invent verification", "ask the user to supply or unblock evidence"]
    }
  ]
}
```

- [ ] **Step 2: Run the no-guidance control five times per scenario**

Run all five scenarios without loading any skill:

```bash
mkdir -p .skill-evals
python3 - <<'PY'
import json
import subprocess
from pathlib import Path

cases = json.loads(Path("opening-prs/evals/evals.json").read_text())["evals"]
records = []
for case in cases:
    for sample in range(1, 6):
        command = [
            "codex", "exec", "--ephemeral", "--ignore-user-config",
            "--sandbox", "read-only", case["prompt"],
        ]
        completed = subprocess.run(command, text=True, capture_output=True)
        records.append({
            "case_id": case["id"],
            "sample": sample,
            "response": completed.stdout,
            "stderr": completed.stderr,
            "returncode": completed.returncode,
        })
Path(".skill-evals/opening-prs-baseline.json").write_text(
    json.dumps(records, indent=2) + "\n", encoding="utf-8"
)
PY
```

Expected: 25 fresh no-guidance responses are captured. If the control already satisfies every expectation consistently, stop and report that a new skill is not justified.

- [ ] **Step 3: Read every baseline response and record exact failures**

Create ignored `.skill-evals/opening-prs-baseline-notes.md`. For each case, quote the exact response fragments that demonstrate omissions or wrong shape. Classify only observed failures, using this checklist:

- repository template or instructions not treated as authority
- partial diff analysis or changed files unaccounted for
- generic feature summary instead of customer/reviewer value
- backend-only or frontend-only assumptions on mixed changes
- invented or vague test claims
- missing UI evidence accepted
- data, compatibility, configuration, dependency, or rollout impact omitted
- hard-coded forge or base branch
- push/creation before preview and approval
- commit creation folded into PR opening
- placeholders or runtime attribution in the final draft

Expected: every planned guidance clause maps to at least one observed failure or to a hard safety boundary from the approved design.

- [ ] **Step 4: Write the failing structural contract**

Create `opening-prs/tests/test_skill_contract.py`:

```python
import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
SKILL = ROOT / "SKILL.md"
FALLBACK = ROOT / "references" / "fallback-pr-body.md"
EVALS = ROOT / "evals" / "evals.json"


def normalized(text):
    return " ".join(text.lower().split())


class OpeningPrsSkillTests(unittest.TestCase):
    def setUp(self):
        self.skill = SKILL.read_text(encoding="utf-8")
        self.body = self.skill.split("\n---\n", 1)[1]
        self.flat = normalized(self.body)

    def test_frontmatter_is_model_invoked_and_bounded_to_pr_opening(self):
        frontmatter = self.skill.split("---", 2)[1]
        self.assertIn("name: opening-prs", frontmatter)
        self.assertNotIn("disable-model-invocation", frontmatter)
        for phrase in ("open", "create", "draft", "informative pull request", "completed branch"):
            self.assertIn(phrase, frontmatter.lower())

    def test_five_ordered_gates_have_checkable_completion_criteria(self):
        headings = (
            "## 1. Establish the target",
            "## 2. Reconstruct the change",
            "## 3. Verify the changed behavior",
            "## 4. Draft the reviewer brief",
            "## 5. Approve and create",
        )
        positions = [self.body.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(self.body.count("**Complete when:**"), 5)

    def test_repository_authority_and_pr_only_boundary_are_explicit(self):
        for phrase in (
            "repository instructions and canonical pull-request template win",
            "dirty worktree",
            "atomic-commit",
            "never create, amend, split, or rewrite commits",
            "one base/head range",
            "every changed file",
        ):
            self.assertIn(normalized(phrase), self.flat)

    def test_impact_table_covers_frontend_backend_data_and_operations(self):
        for phrase in (
            "visible ui",
            "screenshot or recording",
            "frontend state, routing, or data flow",
            "api or backend",
            "compatibility",
            "data, migration, or index",
            "configuration, dependency, or rollout",
        ):
            self.assertIn(normalized(phrase), self.flat)

    def test_verification_and_approval_are_evidence_bound(self):
        for phrase in (
            "smallest repository-defined checks",
            "exact commands and observed outcomes",
            "unrun checks remain unverified",
            "missing ui evidence pauses pr creation",
            "forge, base, title, body, verification, and missing evidence",
            "explicit approval",
            "normal non-force push",
        ):
            self.assertIn(normalized(phrase), self.flat)
        self.assertLess(self.flat.index("explicit approval"), self.flat.index("normal non-force push"))

    def test_fallback_is_loaded_only_when_repository_has_no_template(self):
        self.assertIn("[fallback pr body](references/fallback-pr-body.md)", self.body.lower())
        fallback = normalized(FALLBACK.read_text(encoding="utf-8"))
        for phrase in (
            "summary", "customer or user value", "what changed", "why",
            "architecture or flow", "what reviewers need to know", "test plan",
            "screenshots or recordings", "out of scope", "checklist",
            "remove every unused optional section", "no placeholders",
        ):
            self.assertIn(normalized(phrase), fallback)

    def test_behavior_cases_cover_all_branches(self):
        payload = json.loads(EVALS.read_text(encoding="utf-8"))
        self.assertEqual(payload["skill_name"], "opening-prs")
        self.assertEqual(
            {case["id"] for case in payload["evals"]},
            {"visible-frontend-change", "backend-data-change", "mixed-change-without-template", "dirty-worktree-stop", "missing-ui-evidence-stop"},
        )
        for case in payload["evals"]:
            self.assertTrue(case["prompt"].strip())
            self.assertTrue(case["expected_output"].strip())
            self.assertTrue(case["expectations"])

    def test_skill_is_runtime_and_forge_neutral(self):
        for forbidden in ("generated with claude", "co-authored-by: claude", "gh pr create --base develop", "mon-xxx"):
            self.assertNotIn(forbidden, self.flat)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 5: Run the contract and verify RED**

Run:

```bash
python3 -m unittest opening-prs/tests/test_skill_contract.py -v
```

Expected: error because `opening-prs/SKILL.md` and `opening-prs/references/fallback-pr-body.md` do not exist.

- [ ] **Step 6: Commit the independently reviewable RED contract**

```bash
git add opening-prs/tests/test_skill_contract.py opening-prs/evals/evals.json
git commit -m "test: define opening prs contract"
```

---

### Task 2: GREEN portable PR-opening skill

**Files:**
- Create: `opening-prs/SKILL.md`
- Create: `opening-prs/references/fallback-pr-body.md`
- Modify only if evaluation demonstrates a gap: `opening-prs/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: the Task 1 failure notes, approved design, structural contract, and fallback pointer.
- Produces: model-invoked `opening-prs`; conditional reference `references/fallback-pr-body.md`; five ordered completion gates.

- [ ] **Step 1: Write the minimal frontmatter and workflow**

Create `opening-prs/SKILL.md` with this exact frontmatter:

```yaml
---
name: opening-prs
description: Use when the user wants to open, create, prepare, or draft an informative pull request for a completed branch.
---
```

Use these exact sections in order:

```markdown
# Opening pull requests

## Authority
## 1. Establish the target
## 2. Reconstruct the change
## 3. Verify the changed behavior
## 4. Draft the reviewer brief
## 5. Approve and create
## Quick impact map
## Common mistakes
```

Under `Authority`, establish the PR-only boundary and repository authority. Each numbered section ends with exactly one `**Complete when:**` criterion implementing the approved design. Keep the body below 800 words.

The five phases must encode:

1. Discover repository instructions, canonical template, forge, remote/default branch, branch/head, base, and status. Stop on dirty state, protected/default branch, or ambiguous target.
2. Inspect the complete base/head diff plus surrounding code, classify every changed file by reviewer impact, and derive title/ticket only from reliable evidence.
3. Select and run the smallest repository-defined checks covering the highest-risk behavior; preserve exact commands/results; require UI evidence for visible changes.
4. Use the repository template as schema. Read the [fallback PR body](references/fallback-pr-body.md) only when no canonical template exists. Fill/remove all sections; use Mermaid only for at least three material interactions/transitions.
5. Preview forge/base/title/body/verification/missing evidence and require explicit approval before normal push and forge creation. Stop on failure without destructive recovery; return the stable URL on success.

The quick impact map is one compact table mapping the tested impact phrases to required reviewer evidence. `Common mistakes` is a positive correction table derived only from the baseline failures in `.skill-evals/opening-prs-baseline-notes.md`.

- [ ] **Step 2: Write the fallback output contract**

Create `opening-prs/references/fallback-pr-body.md` with these sections in order:

```markdown
# Fallback PR body
## Summary
## Customer or user value
## What changed
## Why
## Architecture or flow
## What reviewers need to know
## Test plan
## Screenshots or recordings
## Out of scope
## Checklist
## Completion check
```

Define the content contract for each section rather than a fill-in-the-blank template. `Architecture or flow`, `Screenshots or recordings`, and `Out of scope` are conditional. The completion check requires no placeholders/comments/examples, removal of every unused optional section, observed verification only, UI evidence when applicable, concrete risk/compatibility/data/infra notes when applicable, and concise reviewer-oriented prose.

- [ ] **Step 3: Run the structural contract and verify GREEN**

Run:

```bash
python3 -m unittest opening-prs/tests/test_skill_contract.py -v
wc -w opening-prs/SKILL.md
```

Expected: 8 tests pass; the body remains below 800 words.

- [ ] **Step 4: Commit the minimal skill before ref-backed evaluation**

```bash
git add opening-prs/SKILL.md opening-prs/references/fallback-pr-body.md
git commit -m "feat: add portable opening prs skill"
```

- [ ] **Step 5: Run five behavior samples per case with the skill**

Run:

```bash
python3 evals/run.py behavior --skill opening-prs --ref HEAD --runs 5
```

Expected: 25 fresh-context responses in `.skill-evals/behavior-opening-prs.json`; every response follows the applicable scenario expectations and makes no repository mutation.

- [ ] **Step 6: Manually compare every response with the baseline and refactor only demonstrated gaps**

Read all 25 responses. Confirm convergence increased relative to the 15 no-guidance controls. Record new rationalizations or omissions in `.skill-evals/opening-prs-baseline-notes.md`.

When a response fails an expectation, change the smallest authoritative clause in `SKILL.md` or `fallback-pr-body.md`; add or alter a structural assertion only when it protects the corrected behavior. Re-run the focused test and the failed behavior case with `--cases` pointing to a temporary one-case JSON until five consecutive samples comply. Do not add guidance for hypothetical failures.

- [ ] **Step 7: Commit any evaluation-driven refactor**

If Task 2 Step 6 changed tracked files:

```bash
git add opening-prs/SKILL.md opening-prs/references/fallback-pr-body.md opening-prs/tests/test_skill_contract.py
git commit -m "fix: tighten opening prs guidance"
```

If no tracked file changed, record that the initial GREEN guidance passed and continue without an empty commit.

---

### Task 3: Routing, catalog, and deployment verification

**Files:**
- Modify: `evals/routing-cases.json`
- Modify: `tests/test_skill_quality.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: tracked `opening-prs/SKILL.md` frontmatter.
- Produces: unambiguous routing against `atomic-commit`, `qa-pr`, `pr-sweep`, and review skills; deterministic catalog row; global inventory count of 30.

- [ ] **Step 1: Add routing cases and update the inventory expectation**

Add these cases to `evals/routing-cases.json`:

```json
{"id":"opening-prs-positive","prompt":"Open an informative pull request for this completed clean branch.","expected":"opening-prs"}
{"id":"opening-prs-draft-positive","prompt":"Prepare the title and reviewer-friendly PR body, then create the pull request.","expected":"opening-prs"}
{"id":"opening-prs-commit-near-miss","prompt":"Split my staged and unstaged work into clean conventional commits before we discuss a PR.","expected":"atomic-commit"}
{"id":"opening-prs-qa-near-miss","prompt":"QA this existing pull request and post observable acceptance evidence for reviewers.","expected":"qa-pr"}
{"id":"opening-prs-sweep-near-miss","prompt":"Drive my already-open pull requests through CI and review until mergeable.","expected":"pr-sweep"}
```

Change `tests/test_skill_quality.py` to expect:

```python
self.assertEqual(result["inventory_count"], 30)
```

Keep the description-character budget unchanged at `8_360`; the expected new description keeps the total below it.

- [ ] **Step 2: Run focused tests and verify RED catalog drift**

Run:

```bash
python3 -m unittest opening-prs/tests/test_skill_contract.py tests.test_skill_quality -v
```

Expected: the opening-prs contract passes; skill quality fails because `README.md` has not been synchronized.

- [ ] **Step 3: Synchronize the managed catalog**

Run:

```bash
python3 scripts/skill_quality.py sync-readme
```

Expected: `synced 30 skills`; `README.md` receives one alphabetically positioned `opening-prs` row and no text outside the managed markers changes.

- [ ] **Step 4: Commit routing and catalog integration**

```bash
git add evals/routing-cases.json tests/test_skill_quality.py README.md
git commit -m "docs: catalog opening prs skill"
```

- [ ] **Step 5: Run post-commit routing and behavior dry runs**

Run:

```bash
python3 evals/run.py routing --ref HEAD --runs 1 --dry-run
python3 evals/run.py behavior --skill opening-prs --ref HEAD --runs 1 --dry-run
```

Expected: routing dry-run includes the five new cases and the catalog includes `opening-prs`; behavior dry-run returns five records from the committed skill and evals.

- [ ] **Step 6: Run focused and full verification**

Run:

```bash
python3 -m unittest opening-prs/tests/test_skill_contract.py -v
python3 -m unittest tests.test_skill_quality -v
python3 scripts/skill_quality.py check --json
python3 -m unittest discover -s tests -p 'test_*.py' -v
git diff --check
git status --short
```

Expected:

- 8 opening-prs contract tests pass.
- All skill-quality and root tests pass.
- Quality JSON reports `inventory_count: 30`, no errors, and no warning for `opening-prs/SKILL.md`.
- `git diff --check` prints nothing.
- `git status --short` is empty.

- [ ] **Step 7: Review the final implementation range against the approved design**

Run:

```bash
git log --oneline e0079eb..HEAD
git diff --stat e0079eb..HEAD
git diff e0079eb..HEAD -- opening-prs README.md evals/routing-cases.json tests/test_skill_quality.py
```

Confirm every approved requirement maps to a structural assertion, behavior expectation, or explicit skill/reference clause; the Mondrio source commands remain untouched; no runtime/forge attribution leaked in; and no unrelated files changed.
