---
name: split-pr
description: >
  Use when a PR or branch is too big to review or stamp and needs to become a
  stack of small, independently-reviewable PRs — "split this PR", "this is too
  big, break it up", "stack these changes", "split-pr #123", or when pr-sweep's
  size gate recommended a split instead of an override. Decomposes one oversized
  branch into a bottom-up stack where each layer is independently runnable and
  each diff is small enough to observe rather than just reason about.
---

# Split PR: decompose an oversized branch into an observable stack

Big diffs can't be trusted by reading — a 2,000-line PR is where reasoning-based
review fails and bugs hide. This skill turns one oversized branch into a **stack**
of small PRs, each independently runnable and observable, merged bottom-up so early
layers are already verified before later ones build on them. It's the execution arm
of what `pr-sweep`'s size gate only *recommends* (`pr-sweep` STOPs at "split
recommendation" — this skill carries it out).

Native `git` + `gh` only — no Graphite dependency. If Graphite is installed the
user can drive the same stack through it, but this skill doesn't require it.

## When to use vs. override

`pr-sweep`'s size gate offers override-or-split. Use **split-pr** when the branch
**decomposes into independently-landable changes** (unrelated scopes, or a refactor
bundled with a feature), or is **far over the cap** (>~2× the limit). Use the
size-override (in `pr-sweep`) only for a genuinely cohesive change that would yield
non-functional intermediate PRs. When in doubt, splitting is the repo default.

## Workflow

### Step 1: Map the diff into seams

```bash
git fetch origin
git diff origin/<base>...HEAD --stat
git log origin/<base>..HEAD --oneline
```

Identify **seams** — sets of changes that can land and be verified on their own.
Good seams, roughly in dependency order:

1. Pure prep with no behavior change (renames, moves, type/interface additions, a
   new util nothing calls yet). Lands first, safest.
2. A schema/migration + its model, no callers yet.
3. Backend logic that uses (1)/(2), with tests.
4. The API/endpoint wiring.
5. Frontend that consumes the endpoint.
6. Docs, cleanup.

Each layer must **build and pass its own tests without the layers above it**. If a
change only makes sense with a later change, they belong in the same layer.

### Step 2: Checkpoint the stack plan

Before touching git, present the plan and wait for approval — this reorganizes the
user's branch:

```markdown
## Split plan: <branch> (<N> effective lines → <k> PRs)

Base: <base>
- PR 1  <name>  ~<lines>  <files>           — <what/why, why it stands alone>
- PR 2  <name>  ~<lines>  <files>  (on PR1) — <...>
- ...
Order rationale: <why this dependency order>
Risk: <the branch is rewritten into a stack; original stays at <sha>>

Proceed? yes / edit / cancel
```

Record the original HEAD sha so the branch can be restored if the split goes wrong.

### Step 3: Build the stack bottom-up

For each layer, branch from the previous layer's branch (PR 1 from `<base>`):

```bash
git switch <base> && git switch -c <feature>-1-<slug>
# bring in only this layer's changes:
#   whole files:      git checkout <original-branch> -- <path> ...
#   partial/by-hunk:  git restore --source=<original-branch> -p -- <path>
#   or cherry-pick a commit if the branch was already committed in seams
git commit -m "<type>(<scope>): <layer 1 description>"
```

Then `git switch -c <feature>-2-<slug>` **from layer 1's branch** and repeat, so
each branch's diff-vs-its-base is only that layer.

Known conflict patterns (from `pr-sweep`): a format-only commit that touches files
not yet present in an earlier layer → `git rm` the missing files from that
cherry-pick; they re-add cleanly in the layer that introduces them. An empty commit
after a rebase is fine — drop it.

### Step 4: Verify each layer independently — observe, don't assume

The whole point. For **each** layer's branch, run the project's build + the tests
that layer touches, and where there's a runtime surface, **exercise it** (curl the
endpoint, load the page) — the same observability standard as `/verify`. A layer
that can't be observed green on its own isn't a valid seam; fold it into the next
layer and re-split. Don't move up the stack on a layer you only reasoned about.

### Step 5: Open the stack

Bottom-up, each PR based on the one below:

```bash
gh pr create --base <base>            --head <feature>-1-<slug> --title "..." --body "..."
gh pr create --base <feature>-1-<slug> --head <feature>-2-<slug> --title "..." --body "..."
```

Add one stack-navigation comment per PR (position + links to the others) so a
reviewer can walk it:

```
Stack (merge bottom-up):
1. #<n1> <name> ← you are here
2. #<n2> <name>
3. #<n3> <name>
```

Small, single-purpose PRs are exactly what `stamp-check` can gate and `review-swarm`
can review cheaply — that's the payoff of splitting.

### Step 6: Report

The stack (PR numbers + names + sizes), the per-layer verification evidence, the
merge order, and the retarget reminder: as each PR merges, the next one's base must
move to `<base>` (`gh pr edit <next> --base <base>`) — `pr-sweep` handles this
retarget automatically if it's running.

## Constraints

- Checkpoint before rewriting the branch (Step 2). Never split silently.
- Never force-push the original branch; build the stack on new branch names.
- Every layer must be independently green — no "it'll pass once the next PR lands".
- If a diff genuinely won't decompose (one cohesive change), say so and route back
  to the size-override path in `pr-sweep` instead of forcing artificial seams.
- Stop and surface if seams can't be found without a design decision (e.g. the
  change is entangled and needs refactoring first) — that's the user's call.
