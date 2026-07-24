---
name: check-contract
description: Use only when explicitly asked to audit an approved change contract against the current branch implementation.
disable-model-invocation: true
---

# Check Contract

Audit code as shipped against immutable approved authority. The only permitted
repository mutation is atomic replacement of the still-active
`check-report.md`. Do not fix code. Do not edit the contract or ledger. Do not
post results. Do not commit. Do not push. Do not approve anything. Do not invoke
the recommended skill. Routes are advisory only.

For a compound A-then-B request, hash A's existing report sentinel as opaque
bytes without parsing, then resolve A. On hard stop, attest failed authority,
zero writes, and unchanged sentinel bytes; never access or mutate A
again—before beginning B or after any B repository action starts. Then resolve
B independently without carrying A evidence.

### Step 1: Resolve and verify authority

Resolve the ticket and full branch. Resolve `<check-contract-skill-dir>` as the
absolute directory containing this loaded `SKILL.md`, then its sibling
`<change-contract-skill-dir>`. Read the sibling protocol completely at
`<change-contract-skill-dir>/references/contract-protocol.md` before authority
resolution; it owns all check semantics.

From any path inside the target repository, run:

```bash
python <change-contract-skill-dir>/scripts/contract_state.py resolve-consumer \
  --repo <path-inside-target-repository> \
  --branch <full-branch> \
  --ticket <ticket> \
  --allow-missing-ledger
```

Require its canonical `git rev-parse --show-toplevel` root and verified
two-root result for `.notes/<branch-dir>/contract` and
`ai_docs/<branch-dir>/contract`. Ambiguous pointers, orphaned state, malformed
authority, identity/hash failure, or non-ancestor base are hard stops. `absent`
must be true absence across both roots and is also a hard stop.

For approved state, snapshot active version, approval version, branch, ticket,
approval bytes and approval SHA-256, contract SHA-256, full base, full HEAD,
ancestry, paths, and worktree state. Guard source, contract, ledger, and
`git status --porcelain=v1` hashes.
Guard the prior report's existence and bytes too. Hard-stop true absence or any
authority failure before implementation narrative is read; preserve any
existing report.

**Complete when:** immutable authority and guards are recorded.

### Step 2: Derive code-as-shipped first

From the canonical root, inventory names first with
`git diff --name-status --find-renames <base>..<full-head>` and separate
renames, contract artifacts, and narratives from implementation. In one
bounded static inspection pass, use path-filtered Git-object operations on the
`git diff <base>..<full-head>` range only as
`git diff <base>..<full-head> -- <implementation-source/test-paths>` to read
implementation source and tests only: every code-as-shipped byte in changed
source/tests and enough surrounding code from the recorded Git object via
`git show <full-head>:<path>`. Do not rerun a completed read or search.
Later reads and searches use recorded full-HEAD objects, never worktree files.
Never run general target tests; never import or execute target code. After
implementation reads, defer the contents of contract artifacts, the ledger,
reports, worker summaries, PR narratives, and other author narratives until
Step 5. Do not read
the ledger, report, supplied summary, or PR narrative yet. A dirty worktree is
a non-authoritative limitation; use source Git-object IDs as guards. Account
for public contracts, side effects, persisted state, and integrations with
`file:line` evidence.

**Complete when:** code-first behavior and surface are evidenced.

### Step 3: Classify contract fidelity

Assign the protocol-defined clause status to Outcome and every B/N/I/C/R,
expected-surface, complexity-budget, and acceptance-evidence clause. Check each
`A-<B-id>` against its behavior and aggregate Contract fidelity only by the
protocol.

**Complete when:** clauses are evidenced; fidelity is derived.

### Step 4: Audit YAGNI and reuse

Perform a recorded full-HEAD full-tree search with `git grep` for existing
helpers, components, services, and platform features for every changed
responsibility.
Judge every new abstraction, dependency, configuration, module, public
interface, layer/wrapper, defensive branch, duplicate, and
implementation-coupled test as earned or unearned. Correctness requirements are
not bloat. Derive YAGNI and Reuse only by protocol rules.

**Complete when:** responsibilities and both axes are evidenced.

### Step 5: Reconcile ledger and narrative

Only now read the ledger and supplied summary or PR claims; a missing ledger or
narrative means empty and is never created. Verify D entries, classify
deviations, generate sorted D/U/F IDs, and compare claims with the code-first
account. Apply protocol precedence and routes; derive Documented drift and
Undocumented drift.

For a D-stated replay probe only, create a disposable temporary tree outside
the target repository, materialize recorded HEAD with
`git archive <full-head>` using `tar -x -C <outside-temp-dir>`, run the complete
stated probe there under `PYTHONDONTWRITEBYTECODE=1`, then remove the temporary
tree; never mutate the target. Otherwise run no target code.

**Complete when:** drift, findings, verdict, and ID-citing route are derived.

### Step 6: Replace report and route

Render the complete report outside the repository. Immediately rerun the same
absolute `resolve-consumer --allow-missing-ledger` command. Require equality of
the canonical root, full HEAD, active version, approval bytes and SHA-256,
contract SHA-256, full base, branch/ticket identity, and ancestry. Recheck all
guarded hashes for source, contract, ledger, status, and the prior report. Any
authority failure or freshness mismatch aborts; preserve the previous report.

Atomically create or replace only
`<selected-root>/v<active-version>/check-report.md`; verify no other
audit-caused final delta, emit the exact verdict and route, and stop.

Use this exact report shape:

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

**Complete when:** only the active report is replaced and attested.
