# Slice 1 — Prefactor: extract `infra/path_rules.py`

> Part of the `local-dev-environment` feature. PRD: [`../PRD.md`](../PRD.md) · Technical design:
> [`../TDD.md`](../TDD.md)

**Delivers:** No developer-visible change — the real GCP Load-Balancer URL-map generator behaves
identically before and after — but the pure path-rule-derivation logic it owns now lives
somewhere a second generator (Slice 2's Caddyfile generator) can import without duplicating it.

## What to build

Move `PathRule`, `generate_path_rules()`, `_claim_path()`, and `_prefix_patterns()` out of
`infra/gcp_lb/generate_url_map.py` into a new, provider-neutral `infra/path_rules.py`. Keep the
logic itself byte-for-byte unchanged — this is a pure relocation, not a rewrite. `generate_url_map.py`
imports these names from the new module instead of defining them; its own remaining
GCP-specific code (`_backend_service_ref`, `to_url_map_yaml`, the `__main__` block) stays put.

`generate_path_rules()`'s existing `is_qa`/`backend_suffix`/`qa_available` filtering is GCP-specific
(it decides which *backend service name* to route to) — leave that in `infra/path_rules.py` as-is
for now rather than trying to generalize it prematurely; Slice 2 will confirm whether the Caddyfile
generator needs to bypass or reuse it (its own design says it operates over the *entire* registry,
un-filtered by QA/prod distinctions, since there's only one local environment).

## Design notes

TDD "Local reverse proxy & registry-driven routing generation" and
[`docs/adr/local-dev-environment-local-reverse-proxy.md`](../../../adr/local-dev-environment-local-reverse-proxy.md)
call out this extraction as the prerequisite both generators share, specifically so a future
routing-rule bug fix (e.g. the GCP wildcard-vs-bare-path gotcha `_prefix_patterns()`'s docstring
already documents) only has to happen once.

## Blocked by

None — can start immediately.

## Acceptance criteria

- [ ] `infra/path_rules.py` exists and exports `PathRule`, `generate_path_rules`, `_claim_path`,
      `_prefix_patterns` (or the subset `generate_url_map.py` and the future Caddyfile generator
      both need).
- [ ] `infra/gcp_lb/generate_url_map.py` imports these from `infra/path_rules.py` instead of
      defining them; no logic duplicated between the two files.
- [ ] `uv run python -m infra.gcp_lb.generate_url_map` produces byte-identical output to before
      this slice, for both QA (`backend_suffix=""`) and prod (`backend_suffix="-prod"`).
- [ ] `mypy --strict` and the full `pytest` suite pass with no changes needed outside this
      refactor.

## Testing

`tests/test_url_map_generator.py`'s existing cases must all still pass unchanged (proving the
relocation didn't alter behavior). Split out (or duplicate, whichever keeps the suite's existing
structure cleanest) the path-rule-generation-specific cases into a new `tests/test_path_rules.py`
so Slice 2's Caddyfile-generator tests have an obvious sibling to follow — same style as today:
constructed `AppEntry` objects, no real network/subprocess/file dependency.

<!-- /to-implementation appends a "## Delivered" section here once this slice ships. -->
