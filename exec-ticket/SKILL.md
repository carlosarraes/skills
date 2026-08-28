---
name: exec-ticket
description: Use when the user wants an agreed ticket plan implemented on the current branch with test-driven, minimal changes.
---

# Exec Ticket

Implement the settled ticket intent with the smallest change that fully satisfies
it. This is the build step after the approach has been designed and stress-tested;
do not reopen design unless new information changes the requested outcome.

**REQUIRED SUB-SKILL:** Use superpowers:test-driven-development for every RED →
GREEN → REFACTOR loop.

## Phase 1: Resolve context

Gather ticket and branch context from the invocation, Git, and the ticket
provider when available.

- Parse an optional `<TICKET-ID>` and platform (`linear` by default, `jira` when
  supplied). Use an explicit ticket first; otherwise run
  `git rev-parse --abbrev-ref HEAD`, extract `[a-zA-Z]{2,5}-\d+` from the
  branch case-insensitively, and uppercase it.
- Ask for a ticket only when neither the invocation nor the branch supplies one.
- On `main`, `master`, or `develop`, create
  `feature/<ticket-id>-<short-desc>`; otherwise stay on the current feature
  branch. Resolve the full branch name.
- Read repository instructions and discover the relevant test, lint, and build
  commands before implementation.
- If the ticket provider is unavailable, record the lookup gap. Continue from
  sufficient repository, diff, and plan evidence; do not start a question loop
  when local evidence identifies the requested behavior. Record the provider gap
  in the report. Stop only when the missing evidence prevents a safe
  implementation and report that gap.

**Complete when:** the repository, platform, ticket (or a reported missing
ticket), and full branch are known, with enough local evidence to proceed.

## Phase 2: Load authority

Load the settled prep-ticket evidence and available plan from the session or
repository. Read the root and relevant module instructions, then re-check the
plan's behaviors, non-goals, and tactics against the current repository.

Repository and current user intent outrank stale plans. Use the plan for
settled behavior and scope, not as permission to ignore repository
rules or to invent a new user-visible outcome. If there is no plan or prior
design, return to the normal design process; a genuinely trivial ticket may
proceed after its one-line approach is confirmed.

Before choosing tactics, state the observable outcome and the invariants that
make it true. Name accepted and illegal domain states, the boundary that owns
external validation, and the component that owns each shared mutation. These
are implementation constraints, not a new user-visible design.

**Complete when:** each requested behavior, non-goal, and available proof is
named, the outcome and invariants are explicit, and the source of authority for
this run is clear.

## Phase 3: Record reuse decisions

Before the first RED, identify one reuse decision per implementation
responsibility. Search each responsibility in this order:

1. existing helper/module
2. native / stdlib / platform feature
3. already-installed dependency
4. few lines of new code
5. new structure

For every responsibility, record exactly one decision in working notes or the
transcript. Name each candidate with a `file:line` anchor, cite the search
evidence, and mark it compatible or incompatible with evidence. Reuse every compatible
existing helper; when none fits, record the searches and the selected next
option. Do not create a repository file for these decisions. Do not begin RED
until every responsibility has a decision.

Build a reusable helper, script, or generator only when repeated mechanical
work is already visible and the new owner removes that repetition. Keep a
one-off transformation inline. A hypothetical future caller does not earn a
new abstraction.

**Complete when:** every responsibility has one evidence-backed decision and no
selected tactic skips a compatible existing solution.

## Phase 4: Implement one behavior at a time

Implement one observable behavior at a time through a RED → GREEN → REFACTOR
loop:

- **RED:** write its behavior test; run it and confirm the expected failure in
  the focused test suite before writing its implementation.
- **GREEN:** make the smallest change that passes, following the reuse decision
  and retaining required validation, error handling, security, and accessibility.
- **REFACTOR:** refactor only while green: simplify the implementation and keep
  the diff focused; add no
  speculative abstraction or dependency.

For behavior that changes durable or shared state, RED also proves the
operational invariants that apply:

- repeat the same stable operation identity and observe one intended effect;
- interrupt after each externally visible write, resume, and observe the same
  final state as an uninterrupted run; and
- race competing actors when they can touch the same state, proving one
  transaction, conditional write, queue, lock, or single owner serializes it.

When the repository controls every caller of a replaced API, migrate the
callers and delete the obsolete path in the same green change. Prove zero
remaining references. Compatibility code requires a demonstrated external
consumer or an explicit settled requirement.

When the work exposes a recurring failure, encode the lesson at the narrowest
executable point that prevents recurrence: a type, boundary check, behavior
test, lint rule, helper, or runtime invariant. A reminder comment alone leaves
the same failure available.

If a discovery materially changes the requested user-visible outcome, stop before
writing tests or source that encode the changed outcome. Report the discovery
and the decision required alongside the original intent and conflict, then return
to the normal design process. Do not quietly alter the requested behavior. An
implementation-detail discovery that leaves the outcome unchanged may update
the working notes and continue through the loop.

**Complete when:** every behavior has observed RED and GREEN evidence, with
refactoring performed only under green tests.

## Phase 5: Verify and report

Run the focused test suite after each loop and, after all behaviors are green,
run the full test suite. Discover commands from repository instructions; if no
framework exists, find or add the smallest in-scope runner before proceeding.
All green is the bar. Preserve the exact command and result for each suite;
report the focused and full suite results.

The final report includes:

- ticket and branch (and any provider lookup gap);
- behaviors implemented, with the test that pins each;
- files changed;
- focused test suite result; and
- full test suite result.

If execution stops for missing evidence or a material outcome change, report the
observed facts and decision required instead of claiming implementation or
verification. Then stop. Recommend `/qa-ticket`, `/clean-up`, or `/pr-sweep`
when appropriate; do not chain automatically.

**Complete when:** the required suites are green and the behavior-to-test,
changed-file, and suite evidence is delivered, or a precise stop report explains
why implementation could not proceed.

## Edge cases

- Not in a Git repository: report and stop.
- No ticket from arguments or branch: ask for the ticket.
- Platform CLI unavailable: use sufficient local evidence and report the gap.
- A plan fails without changing the requested outcome: re-check the tactic
  against repository rules and reuse decisions before continuing.
- A material outcome change: stop before encoding it and return to design.
- A trivial ticket: still test-first.
