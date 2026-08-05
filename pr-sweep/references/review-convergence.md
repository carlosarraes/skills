# Review Convergence

Read this file only on a **later cycle** after fixes were pushed. Convergence waits for the **new head** to be fetched and its latest-per-name CI to be green.

## Preconditions

For the current head, require:

- green CI;
- mergeable/conflict-free;
- no unresolved or new inline threads;
- no open summary-only finding;
- stable accounting for every fix/follow-up from the blocking review.

If CI is running, the PR is `WAITING`; re-arm and do nothing. If CI fails or new feedback appears, return it to classification. Never re-request or post a convergence handoff in the same cycle that pushed fixes.

## Re-request

Re-request each human **blocking reviewer** whose latest verdict is `CHANGES_REQUESTED`:

```bash
gh api -X POST "repos/<owner/repo>/pulls/<#>/requested_reviewers" \
  -f reviewers='["<login>", ...]'
```

Do not re-request approvers; GitHub handles approval invalidation/re-request behavior. Validate current provider behavior if the API changes.

## One handoff

Post exactly one PR-level handoff after the re-request. Include focused commit SHAs/subjects, resolved inline findings, and follow-up links with their provenance so the reviewer need not reconstruct the turnaround:

```text
Re-requesting review — addressed feedback in:

- <sha1> <commit subject>
- <sha2> <commit subject>

Filed as follow-up:
- <ticket-url> <summary> (from @reviewer's note)
```

Do not reply directly to the old top-level review body.

After mutation, perform a terminal refresh. Mark `DONE` only when green, mergeable, feedback-clean, and reviewer requested/turned around. Otherwise persist current state and re-arm.
