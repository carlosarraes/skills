---
name: split-pr
description: Use when directly invoked to split an oversized PR or branch, or when enforced repository size limits are exceeded; trigger automatically for Mondrio over 1,000 changed lines.
---

# Split PR: decompose an oversized branch into an observable stack

Use this skill for a direct `split-pr` invocation or when an upstream workflow
has observed an enforced repository size-policy violation. Direct invocation or
an observed enforced repository size-policy violation authorizes the split
without a second approval. The skill remains model-visible so an enforced size
failure can route here automatically.

Repository policy is authoritative. Read the current workflow or provider check
that defines the repository size limit, its exclusions, and its effective-line
calculation. For Mondrio, use a strictly greater than 1,000 comparison: 1,001
changed lines triggers the automatic route, while 1,000 changed lines does not
trigger it. A direct invocation is still sufficient regardless of the count.

The plan stays visible before mutation. Show the complete seam plan, then start
the authorized run without asking the user to approve it again or pausing for a
second decision.

## Workflow

### Step 1: Capture the source and policy facts

Before changing a ref, capture and retain:

```bash
git status --short --branch
git symbolic-ref --short HEAD
git rev-parse HEAD
```

Record the original branch and exact SHA in the run ledger and final report.
Also record whether the worktree is clean. Staged, unstaged, or untracked work
that is not part of the source branch is a safety stop; report the exact status
and leave every ref unchanged.

Read the repository's current size-policy definition and its latest observed
result. Record the policy source, effective changed-line count, cap, exclusions,
and whether the result is an enforced violation. Do not infer a violation from
an old label or a generic status summary. Then identify the base and inspect the
complete source diff:

```bash
git fetch origin
git diff origin/<base>...<original-branch> --stat
git log origin/<base>..<original-branch> --oneline
```

Use the repository's effective-line calculation rather than raw file count. A
Mondrio count of 1,001 is over the 1,000-line limit; a count of exactly 1,000 is
not an automatic size-policy trigger.

### Step 2: Map the diff into safe seams

Identify sets of changes that can land and be verified on their own. Keep each
layer cohesive and independently runnable, roughly in dependency order:

1. Pure preparation with no behavior change, such as renames, moves, type or
   interface additions, or a new unused utility.
2. A schema or migration with its model and no callers yet.
3. Backend logic using the preparation or model, with its tests.
4. API or endpoint wiring.
5. Frontend behavior consuming the endpoint.
6. Documentation and cleanup.

For every proposed seam, state its files, dependency on earlier layers, why it
stands alone, and the checks that can run without later layers. A change that
only makes sense with a later layer belongs in the same layer.

If the oversize change is cohesive and has no safe seam, stop before creating a
branch. Return a bounded size-policy explanation containing the observed count,
the enforced limit, the evidence that no safe seam exists, and why an
intermediate layer would be non-functional. Do not manufacture an artificial
split or any non-functional PRs. Route the exception through the repository's
size-policy handling path and make no mutation.

If a seam requires a design decision that the evidence cannot resolve, stop with
the candidate seams, dependencies, and the exact decision boundary. Preserve the
source branch and do not guess.

### Step 3: Show the plan before mutation

Print a plan containing the complete execution identity and order before
creating any branch or commit:

```markdown
## Split plan: <original-branch> (<effective-lines> effective lines -> <k> PRs)

Trigger: <direct invocation or observed enforced policy violation>
Policy: <source>, cap <limit>, observed <count>
Base: <base>
Original branch: <original-branch>
Original exact SHA: <sha>
- PR 1  <new-branch>  ~<lines>  <files> — <what and why it stands alone>
- PR 2  <new-branch>  ~<lines>  <files>  (on PR 1) — <what and why>
- ...
Order rationale: <dependency order>
Risk: the original branch remains at the recorded SHA; only new stack branches change.
```

The plan is informational and must appear before creating any branch or commit
or pushing any remote. Invocation or the observed enforced violation already
provides authority, so execute the plan after displaying it without another
approval prompt.

### Step 4: Build the stack on new branches

Create only new stack branches. The original branch is a read-only source for
this operation:

```bash
git switch <base>
git switch -c <feature>-1-<slug>
# bring in only layer 1 from <original-branch>
git restore --source=<original-branch> -p -- <path> ...
git commit -m "<type>(<scope>): <layer 1 description>"
git switch -c <feature>-2-<slug>
# bring in only layer 2, then commit it
```

Branch each subsequent layer from the preceding new stack branch. Use explicit
paths or carefully selected hunks; cherry-pick an already cohesive source commit
only when it maps exactly to one layer. Record every new branch name, parent,
commit SHA, and source paths.

Never rewrite the original branch. Never reset the original branch. Never
force-push the original branch. Do not amend, rebase, or delete the original ref.
If a stack operation fails, preserve the index and worktree state, report the
failed command and exact state, and leave the original branch at its recorded
SHA.

### Step 5: Verify every layer independently

For each new branch, before moving to the next layer, run the repository build
and the tests touched by that layer. Where it has a runtime surface, exercise
that surface as well (for example, call the endpoint or load the page). A layer
is not valid because a later layer is expected to make it pass.

Record the branch and commit SHA, exact verification commands, observed output or
exit status, and any runtime evidence for every layer. If any layer is not green
on its own, stop before advancing, fold the dependent changes into a safer seam
or return to the no-safe-seam explanation, and keep the original branch
unchanged.

### Step 6: Publish and open the stack

After every layer has independent green evidence, publish only the new branches
with normal non-force pushes and open the stack bottom-up:

```bash
git push --set-upstream origin <feature>-1-<slug>
gh pr create --base <base> --head <feature>-1-<slug> --title "..." --body "..."
git push --set-upstream origin <feature>-2-<slug>
gh pr create --base <feature>-1-<slug> --head <feature>-2-<slug> --title "..." --body "..."
```

Use the repository's canonical PR template when one exists. Include the layer's
scope, dependency, verification evidence, and missing evidence in each body.
Add one navigation note per PR:

```text
Stack (merge bottom-up):
1. #<n1> <name> <- you are here
2. #<n2> <name>
3. #<n3> <name>
```

Never use a force push. A source branch that is already published remains at its
recorded commit; only the new stack branches are pushed or opened.

### Step 7: Report the result

Return one compact report with:

- the trigger and repository policy evidence;
- the original branch and exact SHA, plus confirmation that it was not rewritten,
  reset, or force-pushed;
- each new branch, parent/base, commit SHA, files, and PR number;
- independent build, test, and runtime verification with observed outcomes;
- stack merge order and any retargeting needed after lower layers merge; and
- remaining scope, failed layers, or a bounded no-safe-seam size-policy
  explanation when the stack could not be completed.

## Constraints

- Direct invocation or an observed enforced repository size-policy violation is
  sufficient authority; do not add a second approval gate.
- Show the full plan before mutation, then execute the authorized plan.
- Use the strict Mondrio threshold: 1,001 changed lines triggers automatically;
  exactly 1,000 does not.
- Create only new stack branches and keep the original branch and SHA intact.
- Verify every layer independently; do not advance on unobserved assumptions.
- A cohesive oversize change with no safe seam stops with a bounded size-policy
  explanation instead of artificial splitting.
