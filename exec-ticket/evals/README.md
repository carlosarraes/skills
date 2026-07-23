# Exec-ticket evaluation fixtures

`fixtures/` contains templates, not runnable canonical repositories. Always
materialize a repository with:

```bash
python exec-ticket/evals/materialize_fixture.py \
  contract-repo /absolute/destination
```

The manifest restores byte-sensitive files and rejects any branch or Git HEAD
that differs from the accepted baseline. Task 3 treatment trials must use
`materialize_fixture.py` exclusively for every initial repository. Verify the
manifest's expected HEAD and a clean worktree before dispatch. Concretely,
check `git rev-parse HEAD` and require empty `git status --porcelain` output.
Copying a preserved post-run baseline repository or calling a template's
`fixture_setup.py` directly is not a valid paired evaluation.
