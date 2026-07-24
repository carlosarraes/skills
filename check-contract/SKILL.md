---
name: check-contract
description: Use only for explicit contract audits.
disable-model-invocation: true
---

# Check Contract

Audit shipped code against immutable approved authority. The only permitted
repository mutation is atomic replacement of the still-active
`check-report.md`. Do not fix code. Do not edit the contract or ledger. Do not
post results. Do not commit. Do not push. Do not approve anything. Do not invoke
the recommended skill. Routes are advisory only.

## Compound A-then-B boundary

For a compound A-then-B request, hash A's existing report sentinel as opaque
bytes without parsing, then resolve A. On hard stop, complete A's
failed-authority, zero-write, and sentinel-preservation attestation before any B
repository action. Then resolve B independently. After any B repository action
begins, run no command against A, read no A path, and make no later path
reference to A.

### Step 1: Resolve and verify authority

Resolve ticket and full branch. Resolve `<check-contract-skill-dir>` as the
absolute directory containing this loaded `SKILL.md` and sibling
`<change-contract-skill-dir>`. Read the sibling protocol completely at
`<change-contract-skill-dir>/references/contract-protocol.md` before authority
resolution.

From any path inside the target repository, run:

```bash
python <change-contract-skill-dir>/scripts/contract_state.py resolve-consumer \
  --repo <path-inside-target-repository> \
  --branch <full-branch> \
  --ticket <ticket> \
  --allow-missing-ledger
```

Require its canonical `git rev-parse --show-toplevel` root and verified two-root
result for `.notes/<branch-dir>/contract` and `ai_docs/<branch-dir>/contract`.
Ambiguous pointers, orphaned state, malformed authority, identity/hash failure,
non-ancestor base, and `absent` unless true absence spans both roots are hard
stops.

For approved state, snapshot active version/approval version, branch, ticket,
approval bytes/approval SHA-256, contract SHA-256, full base/full HEAD,
ancestry, paths, and worktree state.
Guard source, contract, ledger, prior-report, supplied-narrative, and
`git status --porcelain=v1` bytes without parsing narratives. Hard-stop true
absence or any authority failure before implementation narrative is read;
preserve any existing report.

**Complete when:** authority guarded.

### Step 2: Derive code-as-shipped first

At Step 2 start, record the monotonic start. Set the evidence deadline to start
plus 180 seconds, shortened to a supplied caller deadline minus a 60-second
finalization reserve. Then inventory names first in exactly one name inventory
with
`git diff --name-status --find-renames <base>..<full-head>`; record renames and
contract artifacts.

Before the deadline, run one batched recorded-HEAD implementation read with
path-filtered Git-object operations:
`git diff <base>..<full-head> -- <implementation-source/test-paths>` and the
recorded Git object via batched `git show <full-head>:<path>`. Read
implementation source and tests
only—every code-as-shipped byte in changed source/tests and enough surrounding
code. Run one batched repository-wide responsibility/reuse search with
`git grep <patterns> <full-head>`; never reread, retry, or issue per-path or
per-responsibility queries. Never run general target tests; never import or
execute target code.
Later implementation/code reads and searches use recorded full-HEAD objects,
never worktree files.

Do not read the contents of changed contract artifacts, the active ledger,
prior report, supplied or worker summaries, PR narratives, or other author
narratives yet. Account for public contracts, side effects, persisted state,
and integrations with `file:line` evidence. A dirty worktree is a
non-authoritative limitation; use source Git-object IDs as guards.

When the three batches finish, immediately freeze the code-as-shipped account.
If the evidence deadline arrives first, stop evidence collection, mark every
uncollected clause or search result `INDETERMINATE`, then freeze the partial
account. After either path, read the immutable approved contract body from the
verified `contract_path` bytes; proceed through Steps 3-6; reserve at least 60
seconds for Steps 5-6.

**Complete when:** ready for classification.

### Step 3: Classify contract fidelity

Assign protocol-defined clause status to Outcome, every B/N/I/C/R,
expected-surface, complexity-budget, and acceptance-evidence clause. Check each
`A-<B-id>` and aggregate Contract fidelity only by protocol.

**Complete when:** fidelity is derived.

### Step 4: Audit YAGNI and reuse

Use the batched recorded full-HEAD full-tree search evidence for every changed
responsibility. Judge new structures, dependencies, interfaces, branches,
duplicates, and implementation-coupled tests as earned or unearned.
Correctness is not bloat. Derive YAGNI and Reuse only by protocol.

**Complete when:** axes are derived.

### Step 5: Reconcile ledger and narrative

Only now read the guarded active ledger, prior report, supplied summary, PR
claims, and other narratives from their guarded sources. Missing narrative is
empty and never created. Verify D entries; classify deviations; generate sorted
D/U/F IDs; compare claims; apply protocol precedence/routes; derive Documented drift
and Undocumented drift.

For a D-stated replay probe only, materialize `git archive <full-head>` as a
disposable temporary tree outside the target repository. Run the complete
stated probe there with `PYTHONDONTWRITEBYTECODE=1`, remove the temporary tree,
and never mutate the target. Otherwise run no target code.

**Complete when:** verdict is routed.

### Step 6: Replace report and route

Render the complete report outside the repository. Immediately rerun the same
absolute `resolve-consumer --allow-missing-ledger` command. Require equality of
the canonical root, full HEAD, active version, approval bytes and SHA-256,
contract SHA-256, full base, branch/ticket identity, and ancestry. Recheck all
guarded hashes for source, contract, ledger, status, prior report, and
supplied-narrative. Any authority failure or freshness mismatch aborts;
preserve the previous report.

Atomically create or replace only
`<selected-root>/v<active-version>/check-report.md`; verify no other
audit-caused final delta, emit the exact verdict and route, and stop.

Report shape:

```markdown
# Contract Check: <ticket> — v<version>

Audit range: <full-base>..<full-head>
Worktree state: <clean or limitation>
Contract SHA-256: <digest>

## Code-first observed behavior
## Clause-by-clause fidelity
## YAGNI and reuse
## Drift reconciliation
## Ordered findings
## Verdict and route
<exact verdict block>
## Mutation attestation
```

Clause rows contain ID, status, evidence, and reason. Drift rows contain
D/deviation ID, status, evidence, and documentation state. The route cites
stable finding IDs and relevant U/D IDs when present; otherwise it uses the
protocol's explicit-none form.

**Complete when:** report is attested.
