---
name: check-contract
description: Use when the user explicitly asks to audit or check an approved change contract against the current branch implementation.
disable-model-invocation: true
---

# Check Contract

Audit code as shipped against immutable approved authority. The only permitted
repository mutation is atomic replacement of the still-active
`check-report.md`. Do not fix code. Do not edit the contract or ledger. Do not
post results. Do not commit. Do not push. Do not approve anything. Do not invoke
the recommended skill. Routes are advisory only.

### Step 1: Resolve and verify authority

Resolve the ticket and full branch. Resolve `<check-contract-skill-dir>` as the
absolute directory containing this loaded `SKILL.md`, then its sibling
`<change-contract-skill-dir>`. Read the sibling protocol completely at
`<change-contract-skill-dir>/references/contract-protocol.md` before authority
resolution; it exclusively owns storage, vocabulary, aggregation, stable IDs,
precedence, and routes.

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
ancestry, paths, and worktree state. Record dirty state as a report limitation.
Also guard source, contract, ledger, and `git status --porcelain=v1` hashes.
Guard the prior report's existence and bytes too. Hard-stop true absence or any
authority failure before implementation narrative is read; preserve any
existing report.

**Complete when:** one canonical repository, approved immutable identity, full
audit range, ancestry, worktree disclosure, and guards are recorded.

### Step 2: Derive code-as-shipped first

From the canonical root, run `git diff <base>..<full-head>` and inventory its
renames, separating contract artifacts from implementation. Read every
code-as-shipped byte—including changed source/tests and enough surrounding
code—from the recorded Git object with `git show <full-head>:<path>`. All later
code reads and searches use that full-HEAD tree, never worktree files. A dirty
worktree is disclosed only as a non-authoritative limitation. Use source
Git-object IDs as the source guards. Account for public contracts, side
effects, persisted state, and integrations with `file:line` evidence. Do not
read the ledger, report, supplied summary, or PR narrative yet.

**Complete when:** the code-first behavior and exact implementation surface are
evidenced independently of claims.

### Step 3: Classify contract fidelity

Assign the protocol-defined clause status to Outcome and every B/N/I/C/R,
expected-surface, complexity-budget, and acceptance-evidence clause. Check each
`A-<B-id>` against its behavior and aggregate Contract fidelity only by the
protocol.

**Complete when:** every clause family has a stable ID, status, evidence, and
reason, and Contract fidelity is derived.

### Step 4: Audit YAGNI and reuse

Search the recorded full-HEAD tree for existing helpers, components, services,
and platform features. Judge every new abstraction, dependency, configuration,
module, public interface, layer/wrapper, defensive branch, touched
responsibility, duplicate, and implementation-coupled test as earned or
unearned. Correctness requirements are not bloat. Derive YAGNI and Reuse only
by protocol rules.

**Complete when:** every changed responsibility has evidenced reuse/no-reuse
and earned/unearned decisions and both audit axes are derived.

### Step 5: Reconcile ledger and narrative

Only now read the ledger and supplied summary or PR claims; a missing ledger or
narrative means empty and is never created. Verify each D entry, assign its
Ledger status, classify every deviation documented or undocumented, generate
sorted D/U/F IDs, and compare every claim with the code-first account. Apply
the protocol's exhaustive verdict precedence and route table. Derive both
Documented drift and Undocumented drift.

**Complete when:** drift fields, ordered findings, exact verdict, and ID-citing
route are deterministically derived.

### Step 6: Replace report and route

Render the complete report outside the repository. Immediately rerun the same
absolute `resolve-consumer --allow-missing-ledger` command. Require equality of
the canonical root, full HEAD, active version, approval bytes and SHA-256,
contract SHA-256, full base, branch/ticket identity, and ancestry. Recheck all
guarded hashes for source, contract, ledger, status, and the prior report. Any
authority failure or freshness mismatch aborts and must preserve the previous
report.

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

**Complete when:** the active report alone is atomically replaced from a fresh,
unchanged authority snapshot and its mutation attestation is verified.
