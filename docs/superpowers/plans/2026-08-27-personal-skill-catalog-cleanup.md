# Personal Skill Catalog Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce the personal skill repository from 30 global entrypoints to the approved 14-skill catalog, preserve only the two deliberate human gates, and converge Arch, Mac, Zapsign, and the protected Snapdoc report on that catalog.

**Architecture:** Root directories containing `SKILL.md` remain the only install source. Five retained skills use `disable-model-invocation: true`; every other retained skill remains model-visible. Removed skill source is recoverable from Git, except the two OSS workflows, which move intact to a standalone local project. `./add all` remains the convergence command and gains characterization tests rather than a manifest system.

**Tech Stack:** Markdown Agent Skills, Python `unittest`, JSON evaluation fixtures, Bash installer, Git, SSH, Snapdoc.

**Spec:** `docs/superpowers/specs/2026-08-27-personal-skill-catalog-cleanup-design.md`

## Global Constraints

- The final tracked catalog contains exactly 14 root `SKILL.md` files.
- No pstack skill, pstack router, or `poteto-mode` is installed in this change.
- `carraes-reviewer` and `triage-incident` retain their approved human gates.
- `split-pr` stays model-visible and includes Mondrio's 1,000-changed-line trigger.
- `/check-data` defaults to plan, seed, verify; `plan-only` is the explicit non-mutating mode.
- User-only skills are `carraes-reviewer`, `qa-team`, `simplification-audit`, and `video-extract`. The approved catalog has four user-only skills, not five; `split-pr` is model-visible.
- Skill edits are evaluated against commit `10a8687` before deployment. Finish and verify one skill before editing the next.
- Deletions are Git-recoverable. The OSS project has no remote.

---

### Task 1: Teach the repository about user-only skills and installer pruning

**Files:**
- Modify: `evals/run.py`
- Modify: `tests/test_evals.py`
- Modify: `scripts/skill_quality.py`
- Modify: `tests/test_skill_quality.py`
- Create: `tests/test_add.py`

**Interfaces:**
- Consumes: tracked `*/SKILL.md` frontmatter and the existing `./add` contract.
- Produces: `catalog_from_ref()` returns only model-visible skills; quality checks accept both model-visible and user-only description forms; installer pruning is regression-tested.

- [ ] **Step 1: Add the failing routing-catalog test**

Add a second fixture skill with this frontmatter in `tests/test_evals.py`:

```yaml
---
name: manual
description: Use only when explicitly invoked to do manual work.
disable-model-invocation: true
---
```

Assert `catalog_from_ref(root, "HEAD")` contains `one` and excludes `manual`.

- [ ] **Step 2: Run the focused test and observe RED**

Run:

```bash
python -m unittest tests.test_evals.EvalRunnerTests.test_routing_catalog_excludes_user_only_skills -v
```

Expected: FAIL because `catalog_from_ref()` currently returns every tracked skill.

- [ ] **Step 3: Filter manual-only metadata**

Change `catalog_from_ref()` to parse metadata once and skip exact truthy YAML strings:

```python
metadata = frontmatter_metadata(git_show(root, ref, path))
if metadata.get("disable-model-invocation", "").lower() == "true":
    continue
catalog.append({"name": metadata["name"], "description": metadata["description"]})
```

- [ ] **Step 4: Add and fail the manual-description quality test**

Create a fixture whose description is `Use only when explicitly invoked to inspect one thing.` and assert `check(root)["errors"] == []` after syncing its README. Run the single test and observe the current `description must start with 'Use when'` failure.

- [ ] **Step 5: Accept the two description forms**

Replace the single prefix check in `scripts/skill_quality.py` with:

```python
valid_prefixes = ("Use when", "Use only when explicitly invoked")
if not description.startswith(valid_prefixes):
    errors.append(
        f"{relative_path}: description must start with 'Use when' or "
        "'Use only when explicitly invoked'"
    )
```

- [ ] **Step 6: Characterize `./add` safely**

In `tests/test_add.py`, build a temporary repository containing a copied `add`, one valid skill, a stale symlink pointing into that temporary repository, a foreign symlink, and a regular directory. Run `bash add all` with a temporary `HOME`. Assert:

```python
self.assertTrue((home / ".claude/skills/kept").is_symlink())
self.assertFalse((home / ".claude/skills/removed").exists())
self.assertTrue((home / ".claude/skills/foreign").is_symlink())
self.assertTrue((home / ".claude/skills/regular").is_dir())
```

Repeat the retained/stale assertions for `.agents/skills`.

- [ ] **Step 7: Run infrastructure tests**

```bash
python -m unittest tests.test_evals tests.test_skill_quality tests.test_add -v
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add evals/run.py tests/test_evals.py scripts/skill_quality.py tests/test_skill_quality.py tests/test_add.py
git commit -m "test: support user-only skill catalog"
```

---

### Task 2: Remove the redundant gate from `atomic-commit`

**Files:**
- Modify: `atomic-commit/SKILL.md`
- Create: `atomic-commit/evals/evals.json`
- Create: `atomic-commit/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: an explicit commit request and the current worktree.
- Produces: focused conventional commits without a second approval; hook failures preserve state and terminate with evidence.

- [ ] **Step 1: Write the RED behavior case**

Use this simulation case:

```json
{
  "skill_name": "atomic-commit",
  "evals": [{
    "id": "invocation-authorizes-commit",
    "prompt": "SIMULATION ONLY. I invoked /atomic-commit for a worktree containing one feature with its test and one unrelated documentation edit. Describe the exact action trace through completion.",
    "expected_output": "Groups the two concerns, records the plan, stages exact paths, and commits both without asking for approval.",
    "expectations": [
      "does not ask whether to proceed",
      "stages explicit paths",
      "creates focused conventional commits",
      "stops and reports exact state after a failed hook"
    ]
  }]
}
```

Run the case against `10a8687` and retain the response showing the old approval checkpoint.

- [ ] **Step 2: Add deterministic contract assertions**

Assert the skill contains `Invocation is commit authority`, stages explicit paths, and stops after a failed hook. Assert it omits `Proceed with this commit plan?`, `yes / edit / abort`, and `ask the user how to proceed`.

- [ ] **Step 3: Rewrite the plan and execution phases**

Keep analysis and grouping. Rename Phase 3 to `Record the plan`, then execute immediately. State that invocation supplies authority, the plan is included in the final record, and a hook failure ends the run with the command, output, staged paths, and worktree status.

- [ ] **Step 4: Run GREEN checks and commit**

```bash
python -m unittest discover -s atomic-commit/tests -p 'test_*.py' -v
python evals/run.py behavior --skill atomic-commit --ref HEAD --runs 1 --dry-run
git add atomic-commit
git commit -m "fix: remove atomic commit approval gate"
```

---

### Task 3: Make `carraes-reviewer` user-only without changing its posting gate

**Files:**
- Modify: `carraes-reviewer/SKILL.md`
- Create: `carraes-reviewer/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: direct invocation and review evidence.
- Produces: Carlos-voice findings; any posting still requires Carlos's approval.

- [ ] **Step 1: Add the failing frontmatter test**

Assert exact presence of:

```yaml
description: Use only when explicitly invoked to review a PR or diff in Carlos Arraes's voice.
disable-model-invocation: true
```

Also assert the existing draft, approval, and post-only-approved-text rules remain.

- [ ] **Step 2: Run RED, edit only frontmatter, then run GREEN**

```bash
python -m unittest discover -s carraes-reviewer/tests -p 'test_*.py' -v
```

- [ ] **Step 3: Commit**

```bash
git add carraes-reviewer/SKILL.md carraes-reviewer/tests/test_skill_contract.py
git commit -m "docs: make carraes reviewer user invoked"
```

---

### Task 4: Merge planning, seeding, and verification into `check-data`

**Files:**
- Modify: `check-data/SKILL.md`
- Create: `check-data/evals/evals.json`
- Create: `check-data/tests/test_skill_contract.py`
- Delete later: `seed-data/`

**Interfaces:**
- Consumes: optional `plan-only`, optional platform, current branch, schema, and local database.
- Produces: default plan/seeding/count verification or a non-mutating plan-only report.

- [ ] **Step 1: Add RED cases for the new default and argument**

Create two simulation cases. The default case must continue from the written plan into idempotent insertion and before/after verification. The `plan-only` case must stop after writing the plan and perform no database mutation. Run both against `10a8687`; the default case fails because old `check-data` delegates to `/seed-data`.

- [ ] **Step 2: Add deterministic contract tests**

Assert the ordered headings include discovery, plan, seed, verify, report. Assert `plan-only` branches immediately after the plan. Assert the body contains natural-key match, seed tag, FK parents first, before/inserted/skipped/failed/after, and no instruction to run `/seed-data`.

- [ ] **Step 3: Rewrite `SKILL.md` as a compact router**

Retain the four data buckets and schema-aware planning contract. Fold in the insertion order, project-seed/ORM/direct-DB/API preference, idempotency, per-row failure accounting, and count verification from `seed-data`. Replace overwrite approval with current-plan reuse or a new `data-plan-<short-sha>.md` candidate. Keep raw credentials out of reports.

- [ ] **Step 4: Run GREEN checks and commit**

```bash
python -m unittest discover -s check-data/tests -p 'test_*.py' -v
python evals/run.py behavior --skill check-data --ref HEAD --runs 1 --dry-run
git add check-data
git commit -m "feat: combine data planning and seeding"
```

---

### Task 5: Remove routine pauses and deleted-skill routes from `clean-up`

**Files:**
- Modify: `clean-up/SKILL.md`
- Create: `clean-up/evals/evals.json`
- Create: `clean-up/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: current branch or explicit branch/ticket.
- Produces: risk-first review, test-first repairs, focused commits, final simplification, and handoff.

- [ ] **Step 1: Add a RED large-diff case**

The simulation describes a 2,500-line branch with five valid findings. Expect automatic risk-first coherent slicing, no scope-choice prompt, and a final record of unprocessed scope. Add a second ambiguous-target case that stops with candidate facts instead of asking the user to select one.

- [ ] **Step 2: Add contract tests**

Assert the skill omits `Confirm the resolved branch`, `offer to scope`, `Show the triage to the user`, `/pi-review`, `/be-pr`, and `/frontend-pr`. Assert it names `opening-prs`, resolves PR metadata, uses risk-first slices, and reports remaining scope.

- [ ] **Step 3: Edit the workflow**

Preserve the four review lenses and TDD repair loop. Treat the invocation as authority for valid in-scope fixes and focused commits. Keep no-push/no-PR boundaries. Replace deleted routes with retained skills.

- [ ] **Step 4: Verify and commit**

```bash
python -m unittest discover -s clean-up/tests -p 'test_*.py' -v
git add clean-up
git commit -m "fix: streamline branch cleanup workflow"
```

---

### Task 6: Rewrite `exec-ticket` without contract machinery

**Files:**
- Modify: `exec-ticket/SKILL.md`
- Replace: `exec-ticket/evals/evals.json`
- Replace: `exec-ticket/tests/test_contract_integration.py` with `exec-ticket/tests/test_skill_contract.py`
- Delete: contract-specific fixtures and assertion helpers under `exec-ticket/evals/`

**Interfaces:**
- Consumes: ticket/branch context, repository instructions, `prep-ticket` evidence, and an available plan.
- Produces: test-first implementation of each observable behavior plus focused/full verification evidence.

- [ ] **Step 1: Replace contract evals with three RED cases**

Cover: a settled plan with no contract files; missing ticket provider with sufficient repository evidence; and a discovery that changes the requested user-visible outcome. The first two continue without approval artifacts. The third stops before encoding the changed outcome and reports the decision required.

- [ ] **Step 2: Add deterministic tests**

Assert the body contains the lazy reuse order, one reuse decision per responsibility, RED/GREEN/REFACTOR, focused and full suites, and behavior-to-test reporting. Assert it omits `change-contract`, `check-contract`, `current.json`, `approval`, `ledger`, `contract root`, `contract mode`, and `legacy mode`.

- [ ] **Step 3: Replace the skill body**

Use five phases: resolve context; load authority; record reuse decisions; implement one behavior at a time; verify and report. Repository and current user intent outrank stale plans. A material outcome change returns to the normal design process, not a private contract protocol.

- [ ] **Step 4: Verify and commit**

```bash
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
python evals/run.py behavior --skill exec-ticket --ref HEAD --runs 1 --dry-run
git add -A exec-ticket
git commit -m "refactor: remove contract workflow from ticket execution"
```

---

### Task 7: Absorb Zapsign Gitflow into `opening-prs`

**Files:**
- Modify: `opening-prs/SKILL.md`
- Modify: `opening-prs/evals/evals.json`
- Modify: `opening-prs/tests/test_skill_contract.py`
- Move later: `ship-gitflow/references/gitflow-facts.md` to `opening-prs/references/gitflow-facts.md`

**Interfaces:**
- Consumes: optional `gitflow` argument plus repository and forge metadata.
- Produces: one portable PR by default or two Zapsign twin PRs with terminal pipeline results.

- [ ] **Step 1: Change eval expectations and observe RED**

Remove approval-checkpoint expectations from existing cases. Add `gitflow-twin-release` expecting `{TICKET}-prd` from `main`, `{TICKET}-hml` from `homolog`, cherry-picked equivalent patches, existing-resource reuse, two PRs, and both pipelines watched. Run against `10a8687`; the current skill fails both autonomous creation and Gitflow routing.

- [ ] **Step 2: Update deterministic tests**

Rename the final default phase to `Preview and create`. Assert preview precedes a normal push but no approval request exists. Add assertions for the `gitflow` branch and direct link to `references/gitflow-facts.md`.

- [ ] **Step 3: Implement the two-mode router**

Keep common target discovery, change reconstruction, verification, and reviewer brief phases. The default creates one PR. The `gitflow` branch uses the moved facts reference, twin bases/suffixes, `bt pick`, idempotent reuse, no merge between bases, no force push, and terminal pipeline monitoring.

- [ ] **Step 4: Verify and commit**

```bash
python -m unittest discover -s opening-prs/tests -p 'test_*.py' -v
python evals/run.py behavior --skill opening-prs --ref HEAD --runs 1 --dry-run
git add opening-prs
git commit -m "feat: add gitflow mode to opening prs"
```

---

### Task 8: Make `pr-sweep` autonomous inside its selected scope

**Files:**
- Modify: `pr-sweep/SKILL.md`
- Modify: `pr-sweep/evals/evals.json`
- Delete: `pr-sweep/references/approval-triage.md`
- Modify: `pr-sweep/references/cadence.md`
- Modify: `tests/test_pr_sweep_progressive_disclosure.py`

**Interfaces:**
- Consumes: explicit PR list or default authored non-draft PR scope.
- Produces: converged mergeability with at most one normal push per PR per cycle.

- [ ] **Step 1: Turn the approval-gate eval into a RED autonomy case**

For an approved PR with a valid bot fix, expect the single per-PR agent to apply the fix, push once, and report that approval was invalidated. Expect no batched decision or re-confirmation.

- [ ] **Step 2: Update the contract test before the skill**

Assert all selected `NEEDS FIX` PRs dispatch without an approval category, and the routing set no longer contains `approval-triage.md`. Preserve quiet-state, conflict STOP, size-gate, one-agent, one-push, and convergence contracts.

- [ ] **Step 3: Remove the gate**

Delete the approval-triage route/reference. The explicit list or authored-PR default is authority. Keep current-review classification because it affects reporting and reviewer re-request behavior, not permission.

- [ ] **Step 4: Verify and commit**

```bash
python -m unittest tests.test_pr_sweep_progressive_disclosure -v
python evals/run.py behavior --skill pr-sweep --ref HEAD --runs 1 --dry-run
git add -A pr-sweep tests/test_pr_sweep_progressive_disclosure.py
git commit -m "fix: remove pr sweep approval batching"
```

---

### Task 9: Let `prep-ticket` degrade cleanly without a ticket ID

**Files:**
- Modify: `prep-ticket/SKILL.md`
- Create: `prep-ticket/evals/evals.json`
- Create: `prep-ticket/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: optional ticket/platform plus repository state.
- Produces: ticket-backed or repository-only readiness report without invented requirements.

- [ ] **Step 1: Add a RED missing-ticket case**

Use a feature branch with no ticket pattern and unavailable provider CLI. Expect codebase/repository discovery to continue, the report to mark ticket context unavailable, and no question asking for an ID.

- [ ] **Step 2: Add contract tests and edit**

Assert the skill says repository-only mode, exact lookup failure, no invented acceptance criteria, and one evidence-backed suggested approach. Assert it omits `What's the ticket ID` and the second lookup question.

- [ ] **Step 3: Verify and commit**

```bash
python -m unittest discover -s prep-ticket/tests -p 'test_*.py' -v
git add prep-ticket
git commit -m "fix: support ticketless preparation"
```

---

### Task 10: Consolidate QA around `qa-ticket` and manual `qa-team`

**Files:**
- Modify: `qa-ticket/SKILL.md`
- Modify: `qa-ticket/references/qa-context.md`
- Modify: `qa-ticket/references/test-plan.md`
- Modify: `qa-ticket/evals/evals.json`
- Modify: `tests/test_qa_ticket_progressive_disclosure.py`
- Modify: `qa-team/SKILL.md`
- Modify: `tests/test_qa_team_progressive_disclosure.py`

**Interfaces:**
- Consumes: branch/ticket context for executable QA or direct invocation for multi-agent review.
- Produces: no references to deleted QA entrypoints; `qa-team` is absent from automatic routing.

- [ ] **Step 1: Add RED assertions for merged data and manual review routing**

Change QA-ticket expectations from `/check-data` then `/seed-data` to one `/check-data` default run. Assert missing ticket context continues in diff-only mode. Change QA-team frontmatter expectations to:

```yaml
description: Use only when explicitly invoked for a comprehensive multi-agent QA code review.
disable-model-invocation: true
```

- [ ] **Step 2: Apply the smallest edits**

Keep QA-team behavior unchanged. Update QA-ticket and both references so missing fixtures recommend or invoke `/check-data`, never `/seed-data`; missing ticket evidence stays visible as `SKIP/INCONCLUSIVE` rather than prompting.

- [ ] **Step 3: Verify and commit each skill separately**

```bash
python -m unittest tests.test_qa_ticket_progressive_disclosure -v
git add qa-ticket tests/test_qa_ticket_progressive_disclosure.py
git commit -m "fix: align ticket qa with combined data setup"

python -m unittest tests.test_qa_team_progressive_disclosure -v
git add qa-team/SKILL.md tests/test_qa_team_progressive_disclosure.py
git commit -m "docs: make qa team user invoked"
```

---

### Task 11: Make broad and media utilities user-only

**Files:**
- Modify: `simplification-audit/SKILL.md`
- Modify: `simplification-audit/tests/test_skill_contract.py`
- Modify: `video-extract/SKILL.md`
- Create: `video-extract/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: direct invocation only.
- Produces: unchanged audit/transcript behavior with zero automatic routing load.

- [ ] **Step 1: Change and fail the simplification frontmatter test**

Require:

```yaml
description: Use only when explicitly invoked for a whole-codebase simplification audit.
disable-model-invocation: true
```

Apply only this frontmatter change, run the complete simplification tests, and commit.

- [ ] **Step 2: Add and fail the video frontmatter test**

Require:

```yaml
description: Use only when explicitly invoked to extract clean transcripts from YouTube videos.
disable-model-invocation: true
```

Also assert caption-first and public-video boundaries remain. Apply only frontmatter, run tests, and commit.

- [ ] **Step 3: Commit separately**

```bash
git add simplification-audit
git commit -m "docs: make simplification audit user invoked"
git add video-extract
git commit -m "docs: make video extraction user invoked"
```

---

### Task 12: Make `split-pr` automatic for enforced size limits

**Files:**
- Modify: `split-pr/SKILL.md`
- Create: `split-pr/evals/evals.json`
- Create: `split-pr/tests/test_skill_contract.py`

**Interfaces:**
- Consumes: direct invocation or an observed repository size-policy violation.
- Produces: verified stack branches while preserving the original branch and SHA.

- [ ] **Step 1: Add RED behavior cases**

Cover a Mondrio PR with 1,001 changed lines and separable seams, expecting automatic use without a second approval. Cover a cohesive 1,001-line change with no safe seam, expecting a bounded stop and size-policy explanation rather than artificial splitting.

- [ ] **Step 2: Add deterministic contract tests**

Assert the description mentions repository size limits and Mondrio's over-1,000 threshold. Assert the body records original branch and SHA, creates only new branches, verifies each layer, and omits `Proceed?`, `wait for approval`, `Checkpoint`, and references to deleted `stamp-check`/`review-swarm`.

- [ ] **Step 3: Rewrite the authority wording and verify**

The plan remains visible before mutation, but invocation or a detected enforced limit authorizes execution. Never rewrite or force-push the original branch.

```bash
python -m unittest discover -s split-pr/tests -p 'test_*.py' -v
git add split-pr
git commit -m "fix: automate policy-driven pr splitting"
```

---

### Task 13: Move OSS tooling and remove obsolete global skills

**Files:**
- Create outside repository: `/home/carraes/projs/oss/README.md`
- Move outside repository: `oss-scout/`, `oss-scout-issues/`
- Delete: `change-contract/`, `chaos-engineering/`, `check-contract/`, `diff-brief/`, `explain-diff/`, `flow-walkthrough/`, `orchestrate/`, `pi-review/`, `qa-evidence/`, `qa-pr/`, `review-swarm/`, `seed-data/`, `ship-gitflow/`, `stamp-check/`
- Delete: `tests/test_chaos_engineering_progressive_disclosure.py`

**Interfaces:**
- Consumes: approved deletion list and source commit `10a8687`.
- Produces: two non-global OSS tool directories in a local Git repository; no obsolete root skill entrypoints.

- [ ] **Step 1: Validate exact sources and destination**

Confirm all 16 source directories exist, `/home/carraes/projs/oss` does not contain unrelated user work, and the current worktree is clean before the move commit.

- [ ] **Step 2: Create the standalone OSS project**

Move the two directories intact under `/home/carraes/projs/oss/`. Add a README stating they came from `/home/carraes/projs/skills` at `10a8687`, are project-local tooling, and are not globally installed. Initialize a local Git repository and commit all preserved files with `chore: preserve oss scouting tools`. Do not add a remote.

- [ ] **Step 3: Delete the approved skill directories from the skills repository**

Use Git-tracked deletion so every file remains recoverable from history. Verify the exact removed directory list before committing.

- [ ] **Step 4: Commit**

```bash
git add -A oss-scout oss-scout-issues change-contract chaos-engineering check-contract diff-brief explain-diff flow-walkthrough orchestrate pi-review qa-evidence qa-pr review-swarm seed-data ship-gitflow stamp-check tests/test_chaos_engineering_progressive_disclosure.py
git commit -m "chore: remove obsolete global skills"
```

---

### Task 14: Rebuild routing cases, README, and exact inventory

**Files:**
- Modify: `evals/routing-cases.json`
- Modify: `README.md`
- Modify: `tests/test_skill_quality.py`

**Interfaces:**
- Consumes: final 14 tracked skills and four user-only frontmatter flags.
- Produces: model-routing cases for ten visible skills, manual-boundary cases returning `NONE`, and an exact 14-row README catalog.

- [ ] **Step 1: Update the inventory test first and observe RED**

Change the expected inventory from 30 to 14. Add assertions that the discovered names equal:

```python
{
    "atomic-commit", "carraes-reviewer", "check-data", "clean-up",
    "exec-ticket", "opening-prs", "pr-sweep", "prep-ticket",
    "qa-team", "qa-ticket", "simplification-audit", "split-pr",
    "triage-incident", "video-extract",
}
```

- [ ] **Step 2: Replace routing cases**

Keep positive and near-miss cases only for the ten model-visible skills. Add four explicit cases for the manual-only intents with expected `NONE`. Route twin Gitflow opening to `opening-prs`, combined data setup to `check-data`, and oversized Mondrio changes to `split-pr`. Do not pretend a retained skill owns deleted flow-walkthrough, review-posting, or contract requests; those become `NONE` where no maintained installed skill is in this repository's routing catalog.

- [ ] **Step 3: Rewrite README workflow prose and sync the catalog**

Describe:

```text
Build: prep-ticket → exec-ticket → clean-up
QA: check-data → qa-ticket; qa-team only when explicitly invoked
Ship: atomic-commit → opening-prs [gitflow] → pr-sweep
Utilities: split-pr and triage-incident are automatic; carraes-reviewer,
simplification-audit, and video-extract are explicit commands
```

Then run:

```bash
python scripts/skill_quality.py sync-readme
```

- [ ] **Step 4: Run catalog checks and commit**

```bash
python -m unittest tests.test_evals tests.test_skill_quality -v
python scripts/skill_quality.py check --json
python evals/run.py routing --ref HEAD --runs 1 --dry-run
git add README.md evals/routing-cases.json tests/test_skill_quality.py
git commit -m "docs: publish reduced skill catalog"
```

---

### Task 15: Run behavioral evaluation and complete repository verification

**Files:**
- Read: every retained `SKILL.md`, retained eval JSON, and test file
- Generated and ignored: `.skill-evals/`

**Interfaces:**
- Consumes: all preceding commits.
- Produces: evidence that edited skills changed in the intended direction and the repository is internally consistent.

- [ ] **Step 1: Validate retained JSON and local links**

```bash
for file in $(rg --files -g 'evals/*.json' -g 'evals.json'); do python -m json.tool "$file" >/dev/null; done
python scripts/skill_quality.py check --json
```

- [ ] **Step 2: Run all deterministic tests**

```bash
python -m unittest discover -s tests -p 'test_*.py' -v
for directory in atomic-commit carraes-reviewer check-data clean-up exec-ticket opening-prs simplification-audit split-pr video-extract; do
  if [[ -d "$directory/tests" ]]; then
    python -m unittest discover -s "$directory/tests" -p 'test_*.py' -v
  fi
done
```

- [ ] **Step 3: Run focused old/new skill evaluations**

For each behavior-changing skill (`atomic-commit`, `check-data`, `clean-up`, `exec-ticket`, `opening-prs`, `pr-sweep`, `prep-ticket`, `qa-ticket`, `split-pr`), run one old-snapshot and one current-snapshot case. Use Luna Max workers for qualitative comparison. Require the new output to satisfy every expectation and remove the demonstrated old failure; revise and rerun one skill at a time if it does not.

- [ ] **Step 4: Inspect the final diff and status**

```bash
git diff 10a8687..HEAD --stat
git diff --check 10a8687..HEAD
git status --short
```

Expected: 14 tracked skill roots, no whitespace errors, clean worktree.

---

### Task 16: Converge installs on Arch, Mac, and Zapsign

**Files:**
- Runtime symlinks: `~/.claude/skills`, `~/.agents/skills`
- Read-only checks: `~/.codex`, `~/.pi`, `~/.omp`

**Interfaces:**
- Consumes: the final shared repository commit available to each machine.
- Produces: identical personal skill links on all three machines without altering unrelated agent configuration.

- [ ] **Step 1: Make the shared commits available**

Push the current `main` normally to its configured upstream. On Mac and Zapsign, fast-forward the existing `~/projs/skills` clone. Stop on divergence rather than resetting user work.

- [ ] **Step 2: Run the installer on each machine**

Run `./add all` in the Arch clone, then through SSH in the Mac and Zapsign clones. Capture every `pruned stale` line and the final exit status.

- [ ] **Step 3: Verify exact links**

On each machine, enumerate symlinks in `.claude/skills` and `.agents/skills` that point into that machine's skills clone. Assert the 14 retained names exist and the 16 removed names do not. Read-only scan `.codex`, `.pi`, and `.omp` for links pointing into the personal clone; expect none. Do not modify OMP configuration.

- [ ] **Step 4: Report any machine-specific drift**

If a clone is dirty or diverged, leave it untouched and report the exact branch/status. Otherwise record all three machines as converged.

---

### Task 17: Update and verify the protected Snapdoc artifact

**Files:**
- Modify: `pstack-audit-workspace/pstack-fit-audit.html`
- Modify as needed: `pstack-audit-workspace/findings/synthesis.md`

**Interfaces:**
- Consumes: verified final catalog and existing protected Snapdoc document.
- Produces: the same Snapdoc URL/passcode with the final decisions and no stale recommendations.

- [ ] **Step 1: Update the local report**

Replace the provisional personal-skill matrix with the exact 14 retained skills and 16 removals. Mark the two deliberate gates, four user-only skills, combined `check-data`, `opening-prs gitflow`, Mondrio's automatic split threshold, OSS project move, and deferred pstack adoption.

- [ ] **Step 2: Run structural checks**

Assert the HTML contains 14 retained rows, 16 removal rows, no `poteto-mode` adoption, no recommendation to install pstack `tdd`, and responsive table/card behavior. Open locally and inspect desktop and mobile widths.

- [ ] **Step 3: Update Snapdoc and verify readback**

Update the existing protected document rather than creating a new URL. Preserve its passcode and expiry policy. Read the hosted artifact back and compare its content hash with the local HTML.

- [ ] **Step 4: Final handoff**

Return the final commit range, repository tests, per-machine installer result, OSS project path, Snapdoc URL/passcode, and any intentionally retained gate. Do not recommend pstack additions until Carlos asks for the post-cleanup reassessment.
