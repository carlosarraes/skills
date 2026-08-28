---
name: create-verification-skill
description: Use only when explicitly invoked to create a project-local verification skill for a real UI, CLI, service, desktop app, mobile app, or library.
disable-model-invocation: true
---

# Create a verification skill

Create a project-owned way for a later agent to launch the real application,
drive it through a user-facing interface, and prove both visible results and
side effects. Write for an agent arriving cold in a future session.

## 1. Interview the repository

Derive observable facts before asking the user:

- **Surface:** Identify every user-facing UI, command, API, or library entry
  point. Pick the primary surface and record the others.
- **Run:** Find the repository's documented start or build command, readiness
  signal, ports, environment, authentication, and seed-data needs.
- **Drive:** Reuse Playwright, Cypress, PTY helpers, CLI scripts, or HTTP clients
  already present. Use browser automation, a PTY, or plain HTTP only when the
  repository has no existing driver.
- **Observe:** Identify visible output and durable effects such as files, rows,
  messages, logs, and exit status.
- **Isolate:** Give each run its own ports, data directory, profile, or fixture.
  If isolation is impossible, record that limit and never drive a shared user
  session.

Ask only for facts that source and configuration cannot establish. A broken
checkout is not a sound verification base. Repair an in-scope startup problem
first, or report the exact blocker.

## 2. Generate the project skill

Create the canonical skill at `.agents/skills/verify-<app>/`. This path is the
single source of truth. When a runtime used by the project needs its own local
directory, add a relative symlink for the same skill under its existing skills
directory, such as `.claude/skills/`, `.codex/skills/`, `.pi/skills/`, or
`.omp/skills/`. Do not duplicate the skill body. Do not create a client-specific
directory merely because it might be useful someday.

The generated `SKILL.md` has `name`, a concrete model-facing `description`, and
these repository-grounded sections:

- **Launch:** Exact start command, readiness proof, ownership of the process,
  and teardown. Short-lived commands start in a fresh isolated session.
- **Doctor:** One read-only check proving the instance, build, environment, and
  authentication are worth driving.
- **Drive:** Exact commands or stable selectors from this repository. Prefer
  accessible names, prompt strings, route paths, and documented flags over
  coordinates or tab order.
- **Evidence:** Capture the action and resulting state. Verify durable effects
  through a second read path. A final screen alone does not prove a write.
- **Cleanup:** Stop only processes this run started and remove only its scratch
  state. Preserve proof artifacts.
- **Helpers:** Document the invocation of every executable helper the skill
  ships.

## 3. Seed the feature map

Read [the feature-map contract](references/feature-map.md). Create
`features/README.md` and one file per identifiable user-facing feature. Start
with the most important three to five, but never omit a discovered entry point
from a mapped feature merely because another path is easier to drive.

## 4. Prove the result

Execute the generated instructions end to end:

1. Launch and doctor the isolated instance.
2. Drive one mapped feature through the real user path.
3. Capture the action, visible result, and any durable side effect.
4. Clean up, including every failed attempt.
5. Confirm the evidence still exists after cleanup.
6. Confirm every required runtime resolves the canonical skill or its symlink.

A skill that has not completed this loop is a draft. Report the exact commands,
artifacts, client registrations, and any remaining limitation. Point the user
at `maintain-verification-skill` for future upkeep without inventing a cadence.
