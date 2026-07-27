# Check-contract Response Guidance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the runtime's existing fidelity-evidence ownership rule so an
agent can submit a valid, concise code judgment, then prove the correction with
a canary and a fresh immutable paired benchmark.

**Architecture:** A single helper in `audit_validation.py` derives allowed
evidence IDs from the immutable rule pack. The code-packet producer and the
validator consume that helper, while `SKILL.md` tells the agent to use the
runtime-issued per-clause map. The validator, single-use protocol,
aggregation, publication, and iteration-4 evidence remain unchanged.

**Tech Stack:** Python 3.13 standard library, `unittest`, Markdown skill
instructions, bubblewrap-isolated Claude Code evaluation.

## Global Constraints

- Keep iteration 4 and its independent `REJECT` review byte-for-byte
  immutable.
- Do not relax fidelity evidence namespace ownership.
- Do not permit retries or change single-use response semantics.
- Do not change aggregation, verdicts, routes, publication, or compound
  closure.
- Do not mutate approved contracts, approvals, pointers, ledgers, target
  implementations, or narrative inputs.
- Keep `check-contract/SKILL.md` at or below 500 words.
- Derive guidance from the same rule pack and issued evidence used by
  validation; do not duplicate namespace policy in the skill.
- Use one short sentence per judgment reason.
- Installation remains blocked until a fresh immutable iteration achieves
  9/9 treatment full samples and an independent reviewer returns `ACCEPT`.

---

### Task 1: Expose and consume the closed fidelity evidence map

**Files:**

- Modify: `check-contract/scripts/audit_validation.py`
- Modify: `check-contract/scripts/audit_runtime.py`
- Modify: `check-contract/SKILL.md`
- Modify: `check-contract/tests/test_audit_runtime_start.py`
- Modify: `check-contract/tests/test_skill_contract.py`
- Modify: `check-contract/tests/test_audit_runtime_reconciliation.py`

**Interfaces:**

- Produces:

  ```python
  def allowed_clause_evidence_ids(
      clause_id: str,
      issued_evidence_ids: tuple[str, ...] | list[str],
      rules: RulePack,
  ) -> tuple[str, ...]
  ```

- Adds to every code packet:

  ```json
  {
    "fidelity_evidence_ids": {
      "O1": ["behavior:O1", "behavior:B1", "..."],
      "B1": ["behavior:O1", "behavior:B1", "..."]
    }
  }
  ```

  The mapping contains exactly the issued fidelity-family clause IDs. Each
  value contains exactly the issued IDs whose namespace is in
  `rules.fidelity_evidence_namespaces`, in packet evidence order.

- The existing validator consumes the same helper; no second namespace
  implementation is allowed.

- [x] **Step 1: Add a failing packet regression for the iteration-4 contract gap**

In `test_audit_runtime_start.py`, extend
`test_start_records_authority_clause_ids_and_filtered_code`:

```python
rules = self.module.load_rules(self.module.RULES_PATH)
allowed = [
    evidence_id
    for evidence_id in packet["evidence_ids"]
    if evidence_id.partition(":")[0]
    in rules.fidelity_evidence_namespaces
]
fidelity_ids = [
    clause_id
    for clause_id in packet["clause_ids"]
    if self.module.clause_family(clause_id)
    in rules.fidelity_families
]
self.assertEqual(
    packet["fidelity_evidence_ids"],
    {clause_id: allowed for clause_id in fidelity_ids},
)
self.assertIn("behavior:O1", packet["fidelity_evidence_ids"]["O1"])
self.assertNotIn(
    "source:CAPTURE-1",
    packet["fidelity_evidence_ids"]["O1"],
)
```

- [x] **Step 2: Add a failing skill regression**

In `test_skill_contract.py`, add:

```python
def test_fidelity_evidence_uses_runtime_map_and_reasons_stay_bounded(self):
    for phrase in (
        "For each fidelity clause, choose evidence only from "
        "`fidelity_evidence_ids[clause_id]`",
        "one short sentence per reason",
    ):
        self.assertIn(phrase, self.flat_skill)
    for duplicated_policy in (
        "behavior | public-contract | risk | acceptance",
        "source evidence is forbidden for fidelity",
    ):
        self.assertNotIn(duplicated_policy, self.flat_skill)
```

- [x] **Step 3: Add a failing shared-helper regression**

In `test_audit_runtime_reconciliation.py`, add:

```python
def test_iteration4_fidelity_failure_is_explained_by_issued_map(self):
    with materialized_repo(
        "contract-compliant-overengineered"
    ) as repo, tempfile.TemporaryDirectory() as temporary:
        started = self.start(repo, Path(temporary))
        packet = packet_of(started)
        judgment = valid_code_judgment(packet)
        judgment["clauses"]["O1"]["evidence_ids"] = [
            "source:CAPTURE-1"
        ]
        write_response(
            started.response_path,
            code_response(started, judgment=judgment),
        )

        stopped = self.runtime(Path(temporary)).advance(
            self.module.ContinueAudit(
                started.session,
                started.response_path,
            )
        )

        self.assertEqual(stopped.code, "RESPONSE_INVALID")
        self.assertNotIn(
            "source:CAPTURE-1",
            packet["fidelity_evidence_ids"]["O1"],
        )
```

- [x] **Step 4: Run the focused tests and verify RED**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_start.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_reconciliation.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_skill_contract.py' -v
```

Expected: the new packet assertions fail because
`fidelity_evidence_ids` is absent, and the skill assertion fails because the
runtime-owned guidance is absent. The recorded-style response rejection
already passes and proves the reproduced failure boundary.

- [x] **Step 5: Implement one shared derivation**

In `audit_validation.py`, import `RulePack` and add:

```python
def allowed_clause_evidence_ids(
    clause_id,
    issued_evidence_ids,
    rules,
):
    issued = tuple(issued_evidence_ids)
    if clause_family(clause_id) not in rules.fidelity_families:
        return issued
    namespaces = set(rules.fidelity_evidence_namespaces)
    return tuple(
        evidence_id
        for evidence_id in issued
        if evidence_id.partition(":")[0] in namespaces
    )
```

Change `_parse_clause` to derive the allowed tuple with this helper and reject
any cited ID outside that tuple. Preserve the existing error text containing
`violates fidelity evidence namespace ownership`.

- [x] **Step 6: Add the runtime-owned map to the code packet**

In `audit_runtime.py`, import `allowed_clause_evidence_ids` and
`clause_family`. Immediately after evidence capture:

```python
rules = load_rules(RULES_PATH)
issued_evidence_ids = tuple(captured["evidence"])
fidelity_clause_ids = tuple(
    clause.clause_id
    for clause in contract.clauses
    if clause_family(clause.clause_id) in rules.fidelity_families
)
fidelity_evidence_ids = {
    clause_id: list(
        allowed_clause_evidence_ids(
            clause_id,
            issued_evidence_ids,
            rules,
        )
    )
    for clause_id in fidelity_clause_ids
}
```

Store `fidelity_evidence_ids` in the code packet. Do not store it as a mutable
authority or session fact; packet authentication already freezes it.

- [x] **Step 7: Update the thin skill without duplicating policy**

In the code-response paragraph of `SKILL.md`, add exactly:

```markdown
For each fidelity clause, choose evidence only from
`fidelity_evidence_ids[clause_id]`. Use one short sentence per reason.
```

Remove or compress nearby prose only as needed to stay at or below 500 words.
Do not add namespace names or validator logic to the skill.

- [x] **Step 8: Run focused and shared verification**

Run:

```text
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_start.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_audit_runtime_reconciliation.py' -v
python -m unittest discover -s check-contract/tests \
  -p 'test_skill_contract.py' -v
python -m unittest discover -s check-contract/tests -p 'test_*.py' -v
python -m unittest discover -s change-contract/tests -p 'test_*.py' -v
python -m unittest discover -s exec-ticket/tests -p 'test_*.py' -v
python -m py_compile check-contract/scripts/*.py
wc -w check-contract/SKILL.md
git diff --check
```

Expected: all tests pass, compilation/diff checks are clean, and the skill is
at most 500 words.

- [x] **Step 9: Write evidence and commit**

Write `.superpowers/sdd/response-guidance-task-1-report.md` with RED evidence,
the shared derivation, exact counts, word count, and immutability verdict.

Commit:

```text
git add check-contract/scripts/audit_validation.py \
  check-contract/scripts/audit_runtime.py \
  check-contract/SKILL.md \
  check-contract/tests/test_audit_runtime_start.py \
  check-contract/tests/test_audit_runtime_reconciliation.py \
  check-contract/tests/test_skill_contract.py
git commit -m "fix: expose contract fidelity evidence guidance"
```

Obtain a fresh independent task review before Task 2.

---

### Task 2: Canary and immutable iteration 5

**Files:**

- Create ignored: `check-contract-workspace/response-guidance-canary/**`
- Create ignored: `check-contract-workspace/iteration-5/**`
- Modify: `.superpowers/sdd/check-contract-runtime-eval-report.md`
- Create: `.superpowers/sdd/check-contract-runtime-iteration-5-review.md`
- Do not modify product files during either run

**Interfaces:**

- Consumes: exact independently reviewed Task 1 HEAD and its full transitive
  read-only runtime snapshot
- Produces: one preserved canary, 18 immutable paired samples, benchmark/viewer,
  and independent `ACCEPT` or `REJECT`

- [x] **Step 1: Freeze and verify the reviewed runtime**

Record the exact reviewed HEAD and SHA-256 for the complete transitive runtime
inventory. Require clean source bytes, read-only snapshot permissions, direct
`check_contract.py --help`, all shared suites, and assertion-contract v2
preflight.

- [x] **Step 2: Run one treatment-only canary**

Use `contract-compliant-overengineered`, a fresh materialized fixture/session,
Claude Code `2.1.218`, `claude-sonnet-5`, high effort, bubblewrap isolation,
and a 360-second timeout.

Accept its first behavioral result exactly once. Preserve the complete canary
directory whether it passes or fails. Require:

```text
AuditComplete
active check-report.md delivered
only active check-report.md changed
code response accepted
reconciliation response accepted
no retry
```

If any requirement fails, stop. Diagnose from the preserved canary and do not
start iteration 5.

- [ ] **Step 3: Start a fresh immutable paired iteration only after canary PASS**

Create `check-contract-workspace/iteration-5/**`. Run exactly:

- 3 scenarios × 3 treatment samples;
- 3 scenarios × 3 freshly paired control samples;
- maximum concurrency two; and
- canonical 360-second timeout.

Keep prompts neutral and byte-paired after removal of the sole treatment
procedure line. Accept every first behavioral outcome once. Never retry,
replace, overwrite, or silently quarantine behavioral failures.

- [ ] **Step 4: Grade and build the benchmark/viewer**

Persist `grading.json` per sample. Grade raw action chronology, runtime phase
order, nonce use, filesystem recapture, report delivery, report-only mutation,
semantics, verdict/route, and disjoint A/AB1/B/compound slices. A timeout is a
full-sample failure; missing terminal tokens/cost remain null.

Build benchmark JSON/Markdown and a static viewer with exact arithmetic,
population variance/SD, durations, token/cost missing counts, and
treatment-control deltas.

- [ ] **Step 5: Obtain independent causal/acceptance review**

The reviewer must independently verify snapshot hashes, isolation, prompt
parity, accepted inventory, no retries, filesystem recapture, raw action
chronology, grades, arithmetic, timeout handling, viewer inputs, and compound
slices.

Acceptance requires both:

```text
9/9 treatment full samples
independent ACCEPT
```

Do not rewrite iteration-5 evidence after review.

- [ ] **Step 6: Record the gate**

Append iteration-5 provenance and results to
`.superpowers/sdd/check-contract-runtime-eval-report.md`. Mark the original
Task 9 complete only if the two acceptance conditions pass. Otherwise retain
the failed iteration and return to systematic diagnosis without installation.
