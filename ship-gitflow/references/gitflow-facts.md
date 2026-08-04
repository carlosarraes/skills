# Gitflow facts (volatile — verify against the repo's CLAUDE.md when in doubt)

Source of truth: `~/acme/api/CLAUDE.md` (Repository tooling + Commits sections) and `bt --llm`.

## Branch naming

| Suffix | Base branch | PR target |
|---|---|---|
| `{TICKET}-prd` | `main` | `main` |
| `{TICKET}-hml` | `homolog` | `homolog` |

Default convention (and the `bt pick` default). Variants exist in history (`-main`, `-homolog`, `-fix`) — read the actual branch list before assuming; when creating new twins, use `-prd`/`-hml`.

## PR creation (the team invocation — all three flags, every time)

```bash
bt pr create --no-push --ai --close-source-branch
```

- `--no-push` is load-bearing: without it, `bt pr create` prompts "Push now?" and dies on EOF in non-interactive shells. Push yourself first, then create.
- `--ai` generates the PR description (Portuguese template by default).
- `bt pr create --help` is NOT reachable non-interactively (it prompts before printing help) — do not try to rediscover flags that way; they are documented here.
- Target branch is inferred by bt from the suffix config; if it asks for or infers the wrong target, pass the destination explicitly.

## Cherry-picking between twins

```bash
bt pick show        # dry-run: what's unpicked (default direction PRD → HML)
bt pick run         # execute
bt pick run -r      # HML → PRD
bt pick continue    # after resolving a conflict
```

Suffix/prefix config: `bt config set pick.suffix_prd -prd` / `pick.suffix_hml -hml` (env: `BT_PICK_SUFFIX_PRD`, `BT_PICK_SUFFIX_HML`).

## Pipelines

```bash
bt run list --branch <branch>      # includes PR-triggered runs
bt run view <id> --log-failed      # fastest failure diagnosis
bt run watch <id>
bt run report <id> --coverage      # coverage/quality gate detail
```

Coverage/SonarCloud gate failures: `bt pr report <pr-id>`.
