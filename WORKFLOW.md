# Workflow

Use only the steps that reduce uncertainty for the current task.

## Pick an entry point

| Situation | Start with |
| --- | --- |
| Unstructured bug report | `triage` |
| Production or staging incident | `triage-incident` |
| Ticket needs investigation | `prep-ticket` |
| Plan is settled | `exec-ticket` |
| Implementation is complete | `qa-ticket` |
| Branch needs a final review | `clean-up` |
| PR already exists | `pr-sweep` |

## Standard routes

### Ticket

`prep-ticket → exec-ticket → qa-ticket → clean-up → atomic-commit → opening-prs`

Add `check-data` before QA when the branch needs local records.

### Bug

`triage → prep-ticket → exec-ticket → qa-ticket`

Use `triage-incident` instead when the report comes from production or staging.

### High-risk change

`clean-up → interrogate → blast-radius → opening-prs`

- `interrogate` finds risks you have not identified.
- `blast-radius` proves or clears a specific safety assumption.
- For a known risk, skip `interrogate` and run `blast-radius` directly.

Routine, well-tested tickets usually need neither risk tool.

## Project verification

Use `create-verification-skill` once when a project lacks reusable real-app
verification.

Use `maintain-verification-skill` after meaningful user-facing changes or when
the verification map has drifted. These are project-maintenance tools, not
ticket steps.

## Occasional tools

| Need | Use |
| --- | --- |
| Oversized branch | `split-pr` |
| Broad multi-agent QA review | `qa-team` |
| Whole-codebase simplification | `simplification-audit` |
| Long-running decision trail | `show-me-your-work` |
| Review in Carlos's voice | `carraes-reviewer` |
| YouTube transcript | `video-extract` |

`split-pr` triggers automatically for Mondrio above 1,000 changed lines.
`opening-prs gitflow` owns the Zapsign main and homolog flow.

## Approval boundaries

Invoking a skill authorizes its normal reversible work. Only external actions,
unsafe state, missing authority, or genuinely ambiguous outcomes should require
another decision.
