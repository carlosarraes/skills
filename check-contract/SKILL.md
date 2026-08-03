---
name: check-contract
description: Use only for explicit contract audits.
disable-model-invocation: true
---

Report-only. Runtime may create/replace only active `check-report.md`; do not fix
code or edit contract/ledger; do not post/commit/push/approve.

1. `<check-contract-skill-dir>`: absolute directory containing this loaded `SKILL.md`;
   invoke its absolute script path once:

   python <check-contract-skill-dir>/scripts/check_contract.py start

   No-argument CLI consumes host-issued `CHECK_CONTRACT_REQUEST_ID`.
   `start --help` forbidden. For a compound A-then-B request, the host-issued
   request manifest owns both targets;
   keep one logical runtime session, use the latest returned `session` for each
   `continue`, and never run a second `start` command.

2. `NeedJudgment` code packet: read `packet_path`.
   At `response_path`, write exactly one UTF-8 JSON object with only
   `schema_version`, `session`, `nonce`, `packet_sha256`, `kind`, and `judgment`.
   `kind` is `code`; consume packet `semantics.generation` into
   `semantic_generation` and packet `chronology.generation` into
   `chronology_generation`. `code response` `judgment`: exactly five keys, in order:
   `semantic_generation`, `chronology_generation`, `clauses`, `path_assessments`,
   `deviations`.
   `clauses`: JSON object keyed by exactly the runtime-issued clause IDs:
   `status,evidence_ids,reason,contract_boundary_changed`. `path_assessments`:
   JSON object keyed by exactly the runtime-issued changed-path IDs:
   `surface,yagni_items,reuse_items`. Surface: `status,evidence_ids,reason`; items:
   `kind,evidence_ids,reason`. Every reuse item has `helper_fact_ids`: applicable
   issued IDs or `[]`. `deviations`: JSON array; items:
   `path_id,line,description,evidence_ids,reason`; issued IDs;
   no extra keys.
   For each fidelity clause, choose evidence only from
   `fidelity_evidence_ids[clause_id]`; omit all others. Evaluate fidelity against the exact contract
   noun phrases. Independent-axis failures do not broaden those noun phrases or
   imply fidelity failure. Use one short sentence per reason.
   Explicit assertions/`subTest` cases directly proving mapped behavior remain
   demonstrative when grouped.
   `INTRODUCED_BEFORE_AFFECTED_IMPLEMENTATION` marks a used helper earned for the
   affected change, not YAGNI. Never strengthen issued `INDETERMINATE` chronology.
   `R`, `S`, or `K` failure alone does not create YAGNI.
   Implementation-introduced or used does not itself prove earned; a code-proven dispensable wrapper can
   be `UNEARNED_LOCAL` without a `K`-cap failure. Code-proven exact current-helper
   compatibility is `DUPLICATED` despite `INDETERMINATE` chronology.
   Give every changed-path responsibility a reuse verdict; every path's `reuse_items`
   is nonempty; use `NO_REUSE_AVAILABLE`
   when issued full-HEAD search proves none.

   Status: `MET | UNMET | EXCEEDED | INDETERMINATE`. YAGNI:
   `UNEARNED_LOCAL | UNEARNED_MODULE | UNEARNED_RUNTIME_DEPENDENCY | UNEARNED_CONFIGURATION | UNEARNED_PUBLIC_INTERFACE | QUESTIONABLE_LOCAL | QUESTIONABLE_OTHER`;
   reuse:
   `REUSED | NO_REUSE_AVAILABLE | DUPLICATED | BYPASSED | NEAR_DUPLICATE | INDETERMINATE`.
   Lists unique; reasons/descriptions non-empty;
   `contract_boundary_changed`:boolean; `line`: positive integer.

3. Run first `continue`:

   python <check-contract-skill-dir>/scripts/check_contract.py continue \
     --session <session> --response <response_path>

4. Read `NeedJudgment` reconciliation packet. Write
   reconciliation response at `response_path`: match the packet's
   `response_schema` exactly. `kind` is
   `reconciliation`; use only runtime-issued evidence IDs, select at most one
   runtime-issued probe ID, select no probe with `null`, and add no extra keys.

5. Run final `continue`:

   python <check-contract-skill-dir>/scripts/check_contract.py continue \
     --session <session> --response <response_path>

Surface every `NeedJudgment`, `AuditComplete`, or `AuditStopped` exactly as returned.
A compound transition may return the next target's `NeedJudgment`;
repeat steps 2–5 using returned `session`. `AuditComplete` and `AuditStopped`
are terminal. Return plain text: return the exact canonical JSON without Markdown
fences or prose; copy the terminal tool result byte-for-byte; first/last characters
`{`/`}`; nothing before/after; then stop: no more tools/report reads; exit immediately.
Nonzero/error-marked tool-result `AuditStopped`: terminal, not recoverable;
`ReportFindings` and all subsequent tools forbidden.

Runtime owns repository inspection/report writing/aggregate
calculation/findings/verdict/route. Do none; do not retry/invoke a recommended skill.
