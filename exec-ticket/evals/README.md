# Exec-ticket evaluation fixtures

`fixtures/` contains templates, not runnable canonical repositories. Always
materialize a repository with:

```bash
python exec-ticket/evals/materialize_fixture.py \
  contract-repo /absolute/destination
```

The manifest restores byte-sensitive files and rejects any branch or Git HEAD
that differs from the accepted baseline. Task 3 treatment trials must use this
materializer for every repository, or copy one of the preserved accepted
baseline repositories. Calling a template's `fixture_setup.py` directly is not
a valid paired evaluation.
