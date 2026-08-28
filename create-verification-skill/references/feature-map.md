# Feature-map contract

`features/README.md` is the index and shared precondition record. It names the
isolated baseline state, driving conventions, evidence standard, cleanup rule,
and every feature file.

Each feature file begins with an H1 and a one-paragraph description of the
user-visible behavior. It then uses these H2 sections in order:

1. `Sub-features`
2. `How to get to it (user POV)`
3. `Driving it with <harness>`
4. `Gotchas`

The driving section pairs each user action with an exact command or stable
selector and its observable result. Include every user entry point. Name the
second read that proves persistence or another side effect. Record unreachable
paths with the attempted action and unmet precondition; verification through a
different entry point does not turn a skipped path into a pass.

Keep source internals out of the map except where an exact command or stable
handle needs them. Cleanup restores fixture state and retains evidence.
