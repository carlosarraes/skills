---
name: check-contract
description: Use only for explicit contract audits.
disable-model-invocation: true
---

# Check Contract

This is an immutable, report-only audit. The runtime may create or replace only
the active `check-report.md`; do not fix code, do not edit the contract or ledger,
and do not post, commit, push, or approve.

## Closed workflow

1. `<check-contract-skill-dir>` is the absolute directory containing this loaded `SKILL.md`.
   Invoke the absolute script path once:

   ```bash
   python <check-contract-skill-dir>/scripts/check_contract.py start
   ```

   Supply no arguments: the CLI consumes the host-issued
   `CHECK_CONTRACT_REQUEST_ID` capability. Do not inspect `start --help`. For a
   compound A-then-B request, the host-issued request manifest owns both targets;
   keep one logical runtime session, use the latest returned `session` for each
   `continue`, and never run a second `start` command.

2. If `NeedJudgment` has kind `code`, read only its runtime-issued
   code packet at `packet_path`. At `response_path`, write exactly one UTF-8
   JSON object with only `schema_version`, `session`, `nonce`, `packet_sha256`,
   `kind`, and `judgment`. `kind` is `code`.

   Now consume the packet's `semantics` and `chronology`; copy their generation
   values into `semantic_generation` and `chronology_generation`. The code response
   `judgment` has those fields, `clauses`, `path_assessments`,
   and `deviations`. `clauses` contains exactly the runtime-issued clause IDs; each
   has `status`, `evidence_ids`, `reason`, and
   `contract_boundary_changed`. `path_assessments` contains exactly the
   runtime-issued changed-path IDs; each has `surface`, `yagni_items`, and
   `reuse_items`. `surface` has `status`, `evidence_ids`, and `reason`; items
   have `kind`, `evidence_ids`, and `reason`, and each reuse item copies the
   applicable issued `helper_fact_ids`. Deviations have `path_id`, `line`,
   `description`, `evidence_ids`, and `reason`. Use only runtime-issued IDs;
   no extra keys.
   For each fidelity clause, choose evidence only from
   `fidelity_evidence_ids[clause_id]`. Evaluate fidelity against the exact contract
   noun phrases. Independent-axis failures do not broaden those noun phrases or
   imply fidelity failure. Use one short sentence per reason.

   Status: `MET | UNMET | EXCEEDED | INDETERMINATE`. YAGNI kinds:
   `UNEARNED_LOCAL | UNEARNED_MODULE | UNEARNED_RUNTIME_DEPENDENCY | UNEARNED_CONFIGURATION | UNEARNED_PUBLIC_INTERFACE | QUESTIONABLE_LOCAL | QUESTIONABLE_OTHER`;
   reuse kinds:
   `REUSED | NO_REUSE_AVAILABLE | DUPLICATED | BYPASSED | NEAR_DUPLICATE | INDETERMINATE`.
   Lists unique; reasons and descriptions non-empty;
   `contract_boundary_changed` boolean; deviation `line` a positive integer.

3. Run the first `continue`:

   ```bash
   python <check-contract-skill-dir>/scripts/check_contract.py continue \
     --session <session> --response <response_path>
   ```

4. For `NeedJudgment` kind `reconciliation`, read its runtime-issued
   reconciliation packet. Write reconciliation response at
   `response_path`: match the packet's `response_schema` exactly. `kind` is
   `reconciliation`; use only runtime-issued evidence IDs, select at most one
   runtime-issued probe ID, select no probe with `null`, and add no extra keys.

5. Run final `continue`:

   ```bash
   python <check-contract-skill-dir>/scripts/check_contract.py continue \
     --session <session> --response <response_path>
   ```

Surface every `NeedJudgment`, `AuditComplete`, or `AuditStopped` exactly as
returned. A compound transition may return the next target's `NeedJudgment`;
repeat steps 2–5 with the returned `session`. `AuditComplete` and `AuditStopped`
are terminal: return the exact canonical JSON without Markdown fences or prose,
use no more tools, do not read the generated report, and exit immediately.

The runtime owns all other work: do not inspect the target repository directly;
do not write the report directly; do not calculate aggregates; do not choose
findings; do not choose the verdict or route; do not retry; and do not invoke a
recommended skill.
