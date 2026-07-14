---
name: explain-diff
description: >
  Use when you want to deeply understand code you (or an agent) wrote but don't
  really grasp — "explain this to me", "explain-diff", "help me understand the
  overage feature", "teach me this subsystem/PR/branch", "I keep having to ask
  an LLM about my own code", "walk me through what changed". Generates a rich
  interactive teaching artifact (Background → Intuition → Literate walkthrough →
  Quiz) so you understand well enough to have the next idea, not just approve the
  change. Explains a whole subsystem/feature (architecture mode) or a
  PR/branch/commit (diff mode). Renders via visual-explainer.
---

# Explain Diff: understand to participate, not just to verify

Agents write code faster than you can absorb it, and unabsorbed code is
**cognitive debt** — you can vibe on it for a while, then one basic question
reveals you never understood it and can't take the next creative leap. This skill
pays that debt down: it produces a personalized teaching artifact for one change
or one subsystem, ending in a quiz you must pass. (After Geoffrey Litt's
"Understanding is the new bottleneck" / explain-diff.)

The goal is **participation, not verification**. Verification asks "is this
correct?" — agents increasingly do that themselves. Participation asks "do I
understand this well enough to have the next idea?" — that only you can do, and
it's what this artifact builds.

## Modes (auto-detect from the argument)

- **architecture** — a whole project, or a **named subsystem/feature** ("the
  overage feature", "the auth flow"). This is the main use. It requires
  **discovery**: a feature name is not a file list. Trace from real entry points,
  models, services, and migrations; follow one end-to-end path through the code.
  Disambiguate the true surface from name-substring noise (grepping "overage"
  also hits `.coveragerc`) — narrow to the ~10-20 files that actually implement
  it and say which ones you chose.
- **diff** — a PR / branch / commit / range (Litt's original). Detect scope like
  `visual-explainer:diff-review`: `#42` → a PR, a branch/commit/range as given,
  else default to `main`/`master`. Gather the diff with `git`, `gh pr diff`, or
  (Bitbucket) `bt pr diff`, plus the surrounding code the diff touches.

If the argument is ambiguous, ask once which mode/target you mean, then proceed.

## Workflow

### Step 1: Scope and gather — grounded in real code

Resolve the target (mode above). Read the **actual** code — the target files AND
enough surrounding context to teach the background. For a subsystem, trace one
concrete path end-to-end (e.g. how an overage is detected → priced → charged).
Record the real file:line anchors you'll cite. Everything downstream must come
from what you read, never from what the name suggests.

### Step 2: Write the explainer content in the Litt arc

Produce the content in **this order** — the order is the teaching method:

1. **Background** — teach the surrounding system *before* the change/feature.
   Deep-for-a-beginner first (label it skippable for those who know it), then
   narrow to what's directly relevant. Broadly explore surrounding code so this
   is real, not generic.
2. **Intuition before details** — the essence in plain language plus one concrete
   toy example, *before* any code. Name the 3-5 load-bearing ideas that unlock
   everything else. (Litt's version: "make the garden feel 3D using only 2D
   drawing tricks.") This is the most important section — it's what good teachers
   do.
3. **Interactive figure** *(only where it earns its place)* — a small embedded
   widget to fiddle with when a static picture genuinely can't convey it (drag a
   value and watch state change; scrub a step timeline). Default to Mermaid/CSS
   static diagrams; reach for live JS only when it beats static. Gratuitous
   interactivity is slop — skip it.
4. **Literate code walkthrough** — the code, in a sensible order, each file/group
   introduced by *what it does and why* before the snippet. Prose between the
   pieces. Real `file:line`. Never a raw file list or an undigested diff dump.
5. **Quiz** — exactly **5** medium-difficulty multiple-choice questions that
   require actually understanding the substance (not gotchas, not trivia).
   Interactive: clicking an answer reveals correct/incorrect with a one-line
   explanation. **Randomize which position holds the correct answer across the 5,
   and vary answer lengths** so the longest/last option isn't a tell.

Writing style: clear and flowing (Kleppmann-ish), smooth transitions between
sections, diagrams and callouts liberally.

### Step 3: Render via visual-explainer

Do **not** hand-roll the HTML/CSS. Invoke the `visual-explainer` skill and have it
render the arc above as one self-contained page: table of contents, section
headers (no top-level tabs), responsive, its design system and Mermaid theming,
`<pre>` (or `white-space: pre-wrap`) for every code block, dated filename
(`YYYY-MM-DD-explain-<target>.html`) in its output dir. explain-diff owns the
narrative arc, grounding, and quiz mechanics; visual-explainer owns the look.

> visual-explainer's own `diff-review`/`project-recap` commands cover
> diff/project framing but have **no quiz and no literate walkthrough** — those
> are this skill's job; layer them on top of its render.

**Shareable alternative:** if the user wants teammates to read/comment (Litt's
Notion-collaboration angle), render the same content as a Claude **Artifact**
instead of a local file.

### Step 4: Hand back with the quiz-gate

Point the user at the artifact and the quiz. The rule (the **speed regulator**):
*don't send this code to review — or consider yourself done understanding it —
until you can pass the quiz.* Everything about AI pushes for more speed; the quiz
keeps you moving at the speed of understanding, not just correctness.

## Constraints

- **Grounded or silent.** Every claim traces to code you actually read, with
  `file:line`. If you're unsure how something works, open the file — never invent
  behavior. An explainer that hallucinates the user's own system is worse than
  none; it manufactures false confidence.
- **Discovery before explanation** (architecture mode). A feature name ≠ its
  files. Narrow the real surface, drop substring noise, and state which files you
  treated as the feature.
- **Intuition before code, always.** If the artifact reaches a code block before
  it has given the essence + a toy example, reorder it.
- **The quiz is the gate**, and its answers are randomized (position + length).
- **Delegate the render** to visual-explainer; don't reimplement HTML/aesthetics.
- **Interactivity must beat static** or it's cut.
