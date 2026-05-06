---
name: pi-review
description: "Handle code review findings from Pi (another AI agent) received via tmux or --session-control. You MUST use this skill whenever you see text prefixed with '[pi-review findings]' — that marker means Pi sent review results to the builder. Also trigger on [P0]-[P3] priority tags with a verdict line, or when the user says 'handle pi findings', 'fix pi review', 'fix and commit pi findings', 'address pi review', or 'respond to Pi'. For each valid finding, apply a minimal fix, make one focused commit explaining WHY, then reply to Pi through the same channel (session-control sender_info/send_to_session when present, otherwise tmux)."
---

# Pi Review Findings Handler

You received code review findings from Pi, another AI agent. Pi may be running in a tmux pane or in a separate `--session-control` session. Your job: investigate each finding, fix what's valid, then tell Pi what you did and ask for re-review through the same communication channel.

If the incoming message starts with `[pi-review findings]`, treat that as an explicit instruction to use this skill. In session-control workflows, the builder session often receives exactly that marker; do not wait for a separate user command.

## Recognize findings

Findings arrive as text in your prompt containing:
- The explicit marker `[pi-review findings]` (always use this skill when you see it)
- Priority tags: `[P0]`, `[P1]`, `[P2]`, `[P3]`
- A verdict line: `verdict: correct` or `verdict: needs attention`
- Optional session-control metadata: `<sender_info>{...}</sender_info>`

If verdict is **"correct"** — nothing to fix. Tell Pi/user Pi found no issues using the reply channel rules below.

## Investigate and fix

For each finding:
1. Read the referenced file and line
2. Decide if the issue is valid — think critically, don't blindly accept
3. If valid: apply a minimal fix. If you disagree: skip it and note why.
4. If you fixed it: commit immediately (see *Commit rules* below). `git status` must be clean before the next finding.

Priority handling:
- **[P0] and [P1]**: Always fix if valid
- **[P2] and [P3]**: Fix if straightforward, skip if it would be a large refactor

Keep fixes minimal and focused. Do NOT add tests, docstrings, or refactor surrounding code unless the finding specifically requires it.

## Commit rules

One commit per finding — this lets Pi (and humans) re-review commit-by-commit instead of diffing everything at once.

- Stage by explicit path, never `git add -A` or `git add .`
- Conventional commits, one line, no scopes, lowercase after the colon, under 72 chars
- Explain **WHY** — the finding is the "why", your message should capture its intent:
  - Good: `fix: guard null session to prevent 500 on logout`
  - Good: `refactor: rename uid to userId for API consistency`
  - Bad: `fix: address P1` (empty description)
  - Bad: `fix: update auth` (what? why?)
- Follow the project's `CLAUDE.md` commit rules if present — they override these defaults
- Skipped findings get no commit — they're reported in the tmux reply instead

If a commit fails (hook, test, lint): STOP, report the error, ask the user how to proceed. Do not continue to the next finding with a dirty tree.

## Reply channel rules

After fixing, send one short message back to Pi asking for re-review. Prefer session-control when the findings came through session-control; fall back to tmux only when no session-control sender is available.

### Session-control reply (preferred when `<sender_info>` is present)

If the findings include `<sender_info>...</sender_info>`, reply to that session with the `send_to_session` tool if it is available.

1. Parse `sessionId` and/or `sessionName` from the JSON inside `<sender_info>`.
2. Use `send_to_session` with:
   - `action: "send"`
   - `sessionId` if present, otherwise `sessionName`
   - `mode: "follow_up"`
   - `wait_until: "message_processed"`
   - `message`: the short summary described below
3. Do not use tmux if the session-control reply succeeds.

If `send_to_session` is not available in the current harness, you may use the CLI bridge:

```bash
pi -p --session-control \
  --control-session '<session-id-or-name>' \
  --send-session-message 'Done, can you review again? Fixed <brief list>' \
  --send-session-mode follow_up \
  --send-session-wait message_processed
```

Do not include `--send-session-include-sender-info` for this reply; Pi only needs the re-review request.

### Tmux reply (fallback / tmux workflow)

If there is no `<sender_info>` or session-control delivery fails, find Pi's tmux pane and send a single message.

#### Find Pi's pane ID

```bash
MUX_DIR="${PI_MUX_DIR:-${XDG_RUNTIME_DIR:-${TMPDIR:-/tmp}}/pi-mux-$(id -u)}"
cat "$MUX_DIR/config.json"
```

If config.json doesn't exist, auto-detect:
```bash
tmux list-panes -F '#{pane_id} #{pane_top}'
```
Sort by `pane_top` — smallest = your pane (Claude), largest = Pi's pane. Write the config for next time:
```bash
mkdir -p "$MUX_DIR"
echo '{"claudePane":"<your-id>","piPane":"<pi-id>"}' > "$MUX_DIR/config.json"
```

### Compose ONE reply message

Use the same short message for session-control or tmux:

```text
Done, can you review again? Fixed <list what you fixed briefly>
```

For tmux, send it like this:

```bash
tmux send-keys -t <piPane> 'Done, can you review again? Fixed <list what you fixed briefly>' Enter
```

The message should:
- Start with "Done" or similar acknowledgment
- List what you fixed (e.g. "Fixed P1: null check in auth handler, P2: polling now uses specific run ID")
- End with asking Pi to review again
- Stay under ~300 chars to avoid transport issues
- For tmux shell commands: use single quotes for the outer wrapper, avoid single quotes inside the message

If you skipped findings, mention them: "Skipped P3: style preference, disagree."

That's it. No extra orchestration. Fix → commit → (next finding) → reply through session-control or tmux. Done.
