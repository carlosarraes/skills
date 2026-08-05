# Cadence, Re-arming, and Reports

The scheduler name and useful interval are environment- and time-sensitive. Validate the available recurring-wakeup mechanism and current CI/bot latency before relying on the examples here.

## Liveness contract

Schedule the next firing **before** composing the report on **every nonterminal cycle**. Reuse the same scope, tracker, and worktree inputs. This includes:

- all PRs quiet;
- all PRs `WAITING`;
- no agent dispatched;
- autonomous work running while an approval batch waits;
- a gated/no-dispatch user checkpoint;
- conflict/size/finding STOP requiring adjudication.

The sole terminal condition is **all selected PRs are DONE** after a fresh refresh. Only then omit the wakeup. “No code left” and “nothing changed” do not terminate the loop.

When `ScheduleWakeup` is the available mechanism, call it with the same loop prompt and scope before reporting; the audited default was roughly 600 seconds. Never merely promise a wakeup in prose.

The audited guardrails were no shorter than **5 minutes** and no longer than **20 minutes**, with 10 minutes the default. The time-sensitive rationale was that bot passes took 5–12 minutes, CI 5–7 minutes, and the then-current prompt cache had a 5-minute TTL: after a cache miss, 10 minutes amortized the next cycle while useful work completed. **Validate** current scheduler, cache, provider, and project latency before using these bounds; preserve liveness even when the timing changes.

## Persist before handoff

Before reporting, write current `updated_at`, head SHA, CI conclusion, and latest comment timestamp for every swept PR; prune no-longer-open state. This applies even when no work occurred.

## Iteration report

Keep under 300 words. Include:

| PR | Required fields |
|---|---|
| each selected PR | `DONE` / `WAITING` / `NEEDS FIX`; mark `quiet — skipped` where applicable |
| review | current Greptile score if present; threads/review turnaround |
| work | fixes, reruns, follow-ups, approval invalidation/decision |
| policy | size override/split or conflict STOP evidence |
| liveness | next wakeup ETA, or `DONE` only for terminal refresh |

## Final report

When all selected PRs are `DONE`, do not schedule again. List per PR:

- commits added during the sweep;
- bot/human inline replies and resolutions;
- follow-up links and provenance;
- blocking-review re-request status and approval invalidation;
- deferrals/pushback;
- stacked-PR retargets;
- every size override or split recommendation;
- any historical STOP and its resolution.

If a STOP remains unresolved, the sweep is nonterminal: provide the evidence and decision path, schedule the next firing, and label it `NEEDS FIX` rather than producing a final report.
