---
name: maintain-verification-skill
description: Use only when explicitly invoked to audit and repair a project-local verification skill and its user-facing feature map.
disable-model-invocation: true
---

# Maintain a verification skill

Keep a project's verification instructions aligned with source and live user
behavior. Cover features, not sentences. Product bugs remain product bugs;
never rewrite the map to make a regression look correct.

## Outcomes

End with one outcome:

- **clean:** Every mapped feature received source and live coverage. Nothing
  changed.
- **changed:** Proven corrections exist only inside the verification skill.
  Hand the focused change set to `opening-prs` when a PR is wanted.
- **blocked:** Coverage or a safe correction could not finish. Name the exact
  missing prerequisite, attempted route, and remaining scope.

## Edit boundary

Edit only the selected verification skill's `SKILL.md`, `features/`, and owned
helpers. Inspect product source read-only. Report broken product behavior
separately instead of teaching the verifier to accept it.

## 1. Select the target without routine HITL

Resolve in this order:

1. Use an explicit skill name or path from the invocation when it resolves to a
   verification skill with Launch, Doctor, Drive, Evidence, Cleanup, and a
   feature map.
2. Prefer canonical `.agents/skills/verify-*/` candidates. Collapse runtime
   symlinks that resolve to the same canonical directory.
3. Use a legacy `.cursor/skills/verify-*/` candidate only when no canonical
   candidate exists.
4. When one candidate remains, select it. When several remain, match the
   repository or application name only with concrete source evidence.

If candidates remain ambiguous, report their paths and identifying evidence as
`blocked`. Do not interrupt an unattended run with a choice. If none exists,
point at `create-verification-skill`.

## 2. Reconcile the index

Read `features/README.md` and enumerate its sibling feature files. Correct
missing, extra, duplicate, or dead index entries. Preserve one canonical file
per user-facing feature.

## 3. Read every feature from source

Give each feature to an independent read-only subagent when the current runtime
supports subagents. Use the runtime's available spawn interface and allowed
model identifiers; never copy tool names or model slugs from another client.
Bound concurrency to the available slots. If subagents are unavailable, perform
the same reads sequentially.

Each source report contains:

- feature summary;
- cited source entry points;
- likely documentation drift or `none`;
- one concise live-verification recipe.

Require one returned report per feature. Reconcile overlaps into the fewest
practical application states. Sweep recent user-facing source changes for
features absent from the map and require a concrete source path before adding
one.

## 4. Drive every feature live

Follow the selected skill's launch model. Reuse one owned healthy instance for
servers and UIs; use a fresh isolated session for each short-lived CLI drive.
Exercise every feature at least once.

Maintain these invariants throughout the pass:

1. Doctor before the first drive, after surprising behavior, and for each new
   session when sessions are the isolation unit.
2. Evidence already captured survives retries and cleanup at its named path.
3. Processes and scratch state stop when their drive no longer needs them.

Reset or relaunch a wedged state rather than trusting a healthy process check.
Retry one proven verifier correction from a fresh valid state. Mark an entry
`verified-unreachable` only with the exact unmet prerequisite and attempted
user route.

## 5. Triage and prove corrections

- Wrong or missing user description is documentation drift. Correct it.
- Working behavior the driver cannot exercise is a helper gap. Correct it and
  document every helper invocation.
- Broken application behavior is a product gap. Report it outside the change
  set.

Re-drive every changed recipe or helper. Re-read every changed file. Keep
concise scratch notes listing source coverage, live coverage, unreachable
prerequisites, corrections, product gaps, and the final outcome. Do not commit
the notes. Do not edit product code, push, or open a PR; the existing shipping
workflow owns those actions.
