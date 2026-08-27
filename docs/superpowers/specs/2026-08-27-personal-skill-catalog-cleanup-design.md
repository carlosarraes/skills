# Personal Skill Catalog Cleanup Design

**Date:** 2026-08-27
**Status:** Approved in conversation; awaiting written-spec review

## Purpose

Reduce the personal catalog from 30 globally installed skills to 14 useful entrypoints. The retained catalog should fit Carlos's actual workflow, avoid duplicate maintenance, and pause for human input only where Carlos explicitly wants the identity or company gate.

This cleanup comes before any pstack adoption. No pstack skill or workflow layer is installed in this change. After the smaller catalog has been used for a while, the pstack audit can be revisited against the gaps that remain. `blast-radius` is the first candidate for that later pass, but it does not enter this cleanup.

## Chosen structure

Keep a flat source model: every root directory containing `SKILL.md` is an installed personal skill. A skill that should exist only as a command remains at the root with `disable-model-invocation: true` and a human-facing description beginning `Use only when explicitly invoked`. Deleted skills leave the root entirely, so `./add all` removes their stale links.

This is simpler than the two rejected alternatives:

1. A catalog manifest with active, manual, and disabled states would let dormant source remain in this repository, but it would add a second source of truth and require more installer logic.
2. Machine-specific install profiles would encode the current Mac/Zapsign split, but the split is already expressible through skill arguments and invocation metadata. Profiles would turn an evolving workflow into configuration Carlos must maintain.

Git history is the archive for deleted skills. The two OSS workflows are the exception because their scripts and collected data are still useful as a project. They move intact to a standalone local project at `~/projs/oss` and stop participating in global skill discovery.

## Final catalog

| Skill | Invocation | Decision |
| --- | --- | --- |
| `atomic-commit` | Model or user | Keep. Invocation authorizes the commits. Show the grouping as a record, then commit exact paths without a second approval. A failed hook stops with evidence and preserved state. |
| `carraes-reviewer` | User only | Keep the draft-and-approve gate because comments are posted in Carlos's identity. |
| `check-data` | Model or user | Merge `seed-data` into this skill. Default is plan, seed, then verify. `/check-data plan-only` produces the non-mutating plan and stops. |
| `clean-up` | Model or user | Keep. Resolve scope from repository and PR evidence. Process large changes in coherent risk-first slices without asking the user to choose a scope. |
| `exec-ticket` | Model or user | Rewrite around ticket intent, repository rules, an available plan, reuse evidence, and test-first implementation. Remove every change/check-contract dependency and approval artifact. |
| `opening-prs` | Model or user | Keep the portable default. Invocation authorizes ordinary push and PR creation after evidence is gathered and previewed. `/opening-prs gitflow` owns Zapsign's twin production/staging branch, PR, and pipeline flow. |
| `pr-sweep` | Model or user | Keep. The requested PR scope authorizes safe fixes and normal pushes. Preserve no-force, base-branch, concurrency, and evidence rules. |
| `prep-ticket` | Model or user | Keep. Missing ticket context degrades to repository and diff evidence with the lookup failure stated; it does not start a question loop. |
| `qa-team` | User only | Keep as the explicit, expensive multi-agent code-review command. |
| `qa-ticket` | Model or user | Keep as the sole acceptance/smoke QA workflow. Missing ticket context degrades to diff-only planning. Missing surfaces remain `SKIP` or `INCONCLUSIVE`. |
| `simplification-audit` | User only | Keep as an explicit whole-repository audit. It is too expensive and broad for automatic discovery. |
| `split-pr` | Model or user | Keep model-eligible. It may trigger automatically when a repository limit is exceeded, specifically for Mondrio changes over 1,000 changed lines. Invocation or the observed limit authorizes the split. Record the original SHA, create new branches without rewriting the original, and verify every layer. |
| `triage-incident` | Model or user | Keep its read-only investigation boundary and explicit approval before creating or commenting on a company issue. |
| `video-extract` | User only | Keep unchanged apart from user-only invocation metadata. |

For user-only skills, the frontmatter flag is the Claude control. The description also states the manual boundary so runtimes that expose the metadata differently do not mistake the skill for an automatic route.

## Exact removals

Delete these root skill directories and their bundled tests, evals, references, and scripts:

- `change-contract`
- `chaos-engineering`
- `check-contract`
- `diff-brief`
- `explain-diff`
- `flow-walkthrough`
- `orchestrate`
- `pi-review`
- `qa-evidence`
- `qa-pr`
- `review-swarm`
- `seed-data`
- `ship-gitflow`
- `stamp-check`

Move `oss-scout` and `oss-scout-issues` to `~/projs/oss`, preserving their scripts, data, and documentation. The destination is a standalone local Git repository with a short README recording the source repository and source commit. It has no remote and is not linked into any global skill directory.

Historical design and implementation documents under `docs/superpowers/` remain. They are records, not discoverable skills.

## Behavior details

### Human gates

An explicit invocation authorizes normal, in-scope, reversible work. Previewing a computed plan remains useful, but it is a record rather than another permission request.

The retained gates are deliberate:

- `carraes-reviewer` requires approval before posting words in Carlos's name.
- `triage-incident` requires approval before creating or commenting on a company issue.

Stops based on missing evidence, ambiguous targets, failed verification, unsafe state, or new authority are blockers rather than HITL rituals. The skill reports the exact fact that stopped it instead of asking whether it should ignore its own safety rule.

### `check-data`

The default flow is one unbroken operation:

1. Discover ticket, diff, schema, local database, and existing seed mechanisms.
2. Produce a concrete data plan covering happy, edge, imperfect-real-world, and pathological-but-storable rows.
3. Seed through the project's own mechanism, then ORM/management command, then direct database access, with HTTP only as a last resort.
4. Preserve idempotency through natural keys or a seed tag. Never delete existing local data to make a rerun work.
5. Re-query and report before, inserted, skipped, failed, and after counts.

`plan-only` ends after step 2. Existing plans are reused when current; stale plans produce a new versioned candidate instead of an overwrite prompt. An unreachable database is a concrete blocker for the default mode, not a reason to silently claim seeding occurred.

### `opening-prs gitflow`

The default mode stays forge-neutral and opens one informative PR for the current completed branch.

The `gitflow` argument activates the former Zapsign flow:

- discover and validate the repository's twin-flow facts;
- maintain `{TICKET}-prd` from `main` and `{TICKET}-hml` from `homolog`;
- carry equivalent patches by cherry-pick, never by merging the bases;
- reuse existing branches and PRs on reruns;
- use the repository's exact Bitbucket commands;
- watch both pipelines to a terminal result and diagnose failures;
- never rewrite or force-push a remote branch.

The general reviewer brief and evidence rules apply to both PR bodies. Invocation authorizes normal pushes and PR creation, so there is no pre-creation approval checkpoint.

### `exec-ticket`

The rewritten workflow resolves the ticket and branch, loads repository instructions and available prep/plan evidence, records reuse decisions, and implements one observable behavior at a time through RED, GREEN, and REFACTOR. It reports behaviors, pinning tests, changed files, and suite results.

Contract roots, immutable approvals, hashes, ledgers, deviation classes, and routes to `change-contract` disappear. When new information materially changes the requested outcome, the normal design process handles that fact; no private contract protocol sits between the user and implementation.

### Review and QA consolidation

- `qa-ticket` owns executable acceptance and smoke testing, including fix-and-retry.
- `qa-team` owns explicitly requested multi-agent code review and remains report-only.
- `pr-sweep` owns convergence of already-open PRs, including CI, conflicts, bot feedback, and human review state.
- Installed maintained skills such as `show-me`, `receiving-code-review`, and future `blast-radius` cover explanation, incoming review interpretation, and risk mapping without personal duplicates.

No new orchestrator or router replaces the deleted `orchestrate`. Carlos continues selecting focused skills directly while the workflow is still evolving.

## Installer and machine convergence

`./add` already has the required deletion behavior. Before every add, it scans `~/.claude/skills` and `~/.agents/skills` and removes symlinks that point into the current clone when the source directory or its `SKILL.md` no longer exists. It leaves regular directories and links owned by other repositories alone.

The implementation will add deterministic tests for this contract but will not add a manifest or profile system. After the shared commit is available on each clone, run `./add all` on Arch, Mac, and Zapsign. Then verify:

- all 14 retained skills are linked in both managed directories;
- all 16 removed names are absent from both managed directories;
- no personal-repository links remain under `~/.codex`, `~/.pi`, or `~/.omp`;
- OMP-specific configuration on Zapsign remains untouched.

## Repository and evaluation updates

The README workflow and generated catalog will describe only the 14 retained skills and distinguish automatic from user-only invocation.

The routing evaluator will exclude `disable-model-invocation: true` skills from the model-visible catalog. Routing cases for deleted skills will be removed or redirected only where a retained skill truly owns the request. Inventory tests will require exactly 14 tracked skills.

Each behavior-changing skill edit follows RED, GREEN, REFACTOR against its current committed version:

1. Add or revise a focused contract/eval case that expresses the approved behavior and fails against the old skill.
2. Run the case against the old snapshot and retain the observed failure.
3. Apply the smallest skill change.
4. Run the same case against the changed skill and run its deterministic contract tests.
5. Finish that skill before editing the next one.

Deletion-only skills need catalog and routing tests, not behavioral evaluations of behavior that no longer exists. Metadata-only manual invocation changes need frontmatter, catalog-routing, and existing behavior tests.

The final verification includes the complete Python test suite, skill-quality check, JSON validation for retained eval files, README catalog synchronization, installer tests, and symlink checks on all three machines.

## Snapdoc

After implementation and machine verification, update the existing protected Snapdoc artifact. Its personal-skill section will show the final 14-skill catalog, exact removals, deliberate HITL exceptions, the `check-data` and `opening-prs` merges, Mondrio's automatic `split-pr` threshold, and a clear statement that pstack adoption is deferred until the cleaned catalog is reassessed.

## Out of scope

- Installing or copying any pstack skill
- Adding `poteto-mode`, a pstack router, or a replacement orchestrator
- Deciding whether pstack `blast-radius` should be adopted
- Replacing Matt Pocock's `tdd`
- Changing maintained non-personal skills such as `show-me`
- Removing historical design documents
- Publishing the new OSS project to a remote
