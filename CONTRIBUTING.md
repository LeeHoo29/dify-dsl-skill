# Contributing

Keep changes portable across Dify installations. A local convention is not a validation error unless it is backed by upstream source, official documentation, or a reproducible export/import failure.

For behavior changes:

1. Add a focused valid or invalid fixture.
2. Add a unit test that asserts observable validator behavior.
3. Run `python3 -m unittest discover -s tests -v`.
4. Run `npm ci --prefix skills/dify-dsl` and the layout check.
5. Validate every file under `skills/dify-dsl/examples/`.
6. Run `scripts/audit_dify_fixtures.py` against the supported Dify tag when validation rules change.
7. State the Dify release and App DSL version used as evidence.

Never commit real credentials or workspace-bound identifiers. New example DSL must be original or include clear provenance and redistribution permission.
