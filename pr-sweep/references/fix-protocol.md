# Coordinated Fix Protocol

Read this file before dispatching any `NEEDS FIX` PR. Dispatch exactly **one fix agent** for that PR in the cycle. It owns the complete finding ledger and may perform at most **one commit push** for the PR in that cycle.

## Dispatch contract

Give the agent:

- exact independent worktree path and feature branch;
- full L1/L2/L3 ledger with stable finding keys;
- for every inline thread, author/state plus reply comment `databaseId` and review thread ID;
- per-finding action classifications (`fix-here`, `follow-up`, evidenced pushback, or no-file) and any approval invalidation to report;
- follow-up tracker (`linear` default or `jira`) and origin ticket from the branch;
- conflict/size decisions already made by their policy branches.

Never dispatch two agents for one PR. Separate PR worktrees may run in parallel.

## Worktree and update

Stay in the assigned worktree. A supplied map wins; otherwise derive from branch and create a fresh worktree at the remote tip if absent. Never reuse a path on another branch.

Pull with rebase. Worktree directory names follow a per-repo convention (typically `<repo>-<ticket>-<slug>`); read the existing worktrees to confirm it, or ask the user. Also validate whether the historic LFS fixture workaround is still needed before using `git update-index --assume-unchanged backend/tests/fixtures/surveys/*.json`; restore it afterward. A rebase conflict exits this protocol into conflict investigation before any resolution.

## Fix order

1. **L1 CI:** inspect logs and correlate the failure with the diff.
   - Real failure: smallest root-cause repair and a regression test when feasible.
   - Flake unrelated to the diff: rerun the failed job; do not change source.
   - Title-only/conventional check: edit the PR title; no commit. Title edits rerun the title check but preserve reviews.
   - Size gate or conflict: use the already selected policy path, not an improvised code fix.
2. **L2 inline threads:** smallest correct fix or specific evidenced pushback. Make one focused commit per code finding so each is traceable.
3. **L3:** de-duplicated Greptile summary-only items and discrete human review-body items. One commit per discrete requested change, but one coordinated push for the PR.
4. **Follow-ups:** create selected tickets without modifying PR code.
5. Verify the complete branch, then push commits once.

## Inline reply and resolution

After a code fix is committed, reply using the opening comment's **`databaseId`**, then resolve using the **review thread ID**:

```bash
gh api -X POST "repos/<owner/repo>/pulls/<#>/comments/<databaseId>/replies" \
  -f body="Fixed in <SHA>. <one-line explanation>"

gh api graphql -f query='mutation{
  resolveReviewThread(input: {threadId: "<thread-id>"}) { thread { isResolved } }
}'
```

In simulated IDs this means reply to `C-*` and resolve `T-*`; never swap them. A follow-up inline reply says `Filed as follow-up: <ticket-url>` and then resolves. A pushback reply cites concrete code, precedent, ticket scope, or a tested invariant and then resolves. When the reviewer explicitly says not to file or fix, make no code/ticket, reply `Noted, thanks`, and resolve.

A bot reply on its own already-resolved thread is a new finding only when it asks for additional code; otherwise leave the resolved finding closed.

Never reply directly to a top-level review body or Greptile summary. For a nonblocking top-level follow-up, post exactly one PR-level acknowledgment covering the filed items.

## Greptile and commit accounting

Use the ledger's stable key to ensure an L2 finding repeated in the summary receives one fix, not two. A summary-only item gets one focused commit or one reported pushback. Record finding key → commit SHA (or pushback evidence) for later cycles; updated wording does not reset accounting. Confidence is reported, not “fixed.”

## Follow-up provenance

Every follow-up preserves:

- reviewer's text verbatim;
- reviewer identity and whether source was inline or top-level;
- PR URL;
- origin ticket ID;
- concise reason it is deferred.

Title it `Follow-up: <short summary>` and use the origin ticket's team/project when derivable. Jira receives the same payload shape. Follow-up decisions never alter PR code. Exactly one PR-level acknowledgment covers top-level follow-ups. Use the currently configured tracker integration; the audited Linear path was `mcp__claude_ai_Linear__save_issue`, but validate the live provider-specific tool name.

## Pushback bar

Bot pushback may cite an existing utility/pattern, lack of repository convention, incorrect diagnosis, or ticket scope. File a follow-up when the rejected suggestion reveals real deferred unification/work.

Human pushback requires stronger evidence: explicit repository/ticket policy, a tested invariant the suggestion would break, or clear scope expansion with a filed follow-up. When uncertain, file it and surface the decision rather than offering weak pushback.

## Verification and push safety

Run repository-prescribed targeted tests plus type/lint checks. Typical defaults are `tsc --noEmit` for a TypeScript frontend or `uv run pyright && uv run ruff check .` for a Python backend; validate the actual project commands against the repo's own config, and ask the user if they are not discoverable. Never bypass hooks. Never use `git add -A`/broad staging when user work may coexist. Never push a base branch.

Push feature-branch commits once with plain `git push`. A clean, safe rebase of the same upstream may require `--force-with-lease` under the conflict rules; never plain `--force`.

For stacked PRs, when the lower PR merges, retarget the next PR from the merged feature base to the repository's active integration branch (historically `develop`) and surface the retarget in the report. Validate the current target branch before editing it.

## STOP boundaries

Do not half-implement work requiring roughly more than 100 LOC, an architecture/product decision, or material scope outside the existing diff. Blocking review does not waive the boundary. Return the finding, files, evidence, and recommended user decision to the loop. Preserve all user changes.
