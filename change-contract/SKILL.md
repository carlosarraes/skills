---
name: change-contract
description: Turn a settled ticket design into an approved implementation contract.
disable-model-invocation: true
---

# Change Contract

Create the contract immediately before implementation. The contract fixes the
approved outcome while leaving implementation details free to improve.

Read `references/contract-protocol.md` completely before starting. It owns the
contract shape, YAGNI order, storage, approval integrity, and drift vocabulary.

### Step 1: Resolve the agreement

Resolve the ticket, full branch, full base SHA, settled design, repository rules,
and notes root. A design is settled when brainstorming/grilling has one chosen
approach and no open product, API, security, or data decisions.

When the design is not settled, return to brainstorming or grilling.

**Complete when:** every identity field has a concrete value and the settled
design source is named.

### Step 2: Ground the change

Read the current behavior, relevant tests, project rules, and surrounding code.
For every proposed responsibility, search for existing helpers, components,
services, platform features, and installed dependencies before proposing new
structure.

**Complete when:** every proposed responsibility has a reuse verdict supported
by `file:line` evidence or by recorded searches that ruled reuse out.

### Step 3: Draft the contract

Fill every section of the protocol template. Make behaviors observable, state
plausible non-goals, map each behavior to acceptance evidence, and make the
complexity budget concrete. Put unresolved decisions in their section instead of
guessing.

**Complete when:** every required behavior has one evidence mapping, every new
responsibility has reuse evidence, the budget contains concrete counts, and all
known uncertainty is visible.

### Step 4: Get explicit approval

Present the complete draft in chat with its target path. Ask the human to approve
or edit that draft. Approval given before the draft was visible is authority to
draft, not approval of the result.

When unresolved decisions remain, ask one decision at a time and revise the
draft before presenting it again.

**Complete when:** the human explicitly approves the displayed draft and
`Unresolved decisions` is exactly `- None`.

### Step 5: Freeze the approved version

Resolve `<skill-dir>` as the absolute directory containing the currently loaded
`SKILL.md`, independent of the working directory. Derive `<branch-dir>` using
the protocol sanitizer already read. Write the approved draft to a temporary
Markdown file, then run:

```bash
python <skill-dir>/scripts/contract_state.py approve \
  --root <notes-root>/<branch-dir>/contract \
  --draft <approved-draft> \
  --ticket <ticket> \
  --branch <full-branch> \
  --base-sha <full-sha> \
  --approved-by <human> \
  --approved-at <iso-8601>
```

Then run:

```bash
python <skill-dir>/scripts/contract_state.py verify \
  --root <notes-root>/<branch-dir>/contract
```

Report the version, paths, SHA-256, and the recommended next command:
`/exec-ticket`.

**Complete when:** `verify` returns `"valid": true`, `current.json` names the new
version, its ledger is empty, and no source file was modified.
