# Fallback PR body

Use this schema only when the repository has no canonical pull-request template. Write concise, reviewer-oriented prose from observed evidence; this is a content contract, not a fill-in-the-blank template.

## Summary

State the outcome and scope in a few sentences, naming the important user-facing or system behavior without generic claims.

## Customer or user value

Explain who benefits and what becomes possible, safer, faster, or clearer. Connect the outcome to an observed change.

## What changed

List the load-bearing implementation changes and identify affected areas or files sufficiently for a reviewer to orient themselves.

## Why

Give the motivation and constraints supported by repository, ticket, branch, or code evidence. Do not infer unsupported intent.

## Architecture or flow

Include this conditional section only when at least three material interactions or transitions clarify the change. Use concise prose or Mermaid; remove the section when it adds no such clarity.

## What reviewers need to know

Call out decisions, trade-offs, gotchas, compatibility, data or migration/index effects, configuration, dependency, infrastructure, and rollout risks when applicable. State when a dimension is not materially affected only if useful.

## Test plan

Record exact verification commands and their observed outcomes, including focused backend/API or UI behavior evidence. Mark checks that were not run as unverified; never claim an unobserved result.

## Screenshots or recordings

Include this conditional section for visible UI changes with the actual screenshot or recording and a brief description of the demonstrated state. If required evidence is unavailable, state that it is missing and pause PR creation rather than weakening or inventing proof. Remove the section when UI evidence is not applicable.

## Out of scope

Include this conditional section only to name consequential adjacent work deliberately excluded from this pull request. Remove it when there is nothing useful to distinguish.

## Checklist

Include applicable reviewer or repository checklist items, completed truthfully. Preserve required items from repository instructions and remove unused items.

## Completion check

Before submission, ensure there are no placeholders, comments, or examples; remove every unused optional section; verification is observed; UI changes have UI evidence; applicable risk, compatibility, data, and infrastructure notes are concrete; and the prose is concise and reviewer-oriented.
