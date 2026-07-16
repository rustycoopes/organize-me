# Nav-group render state computed by a pure function in `packages/chrome`

**Status:** Proposed
**Date:** 2026-07-16
**Feature:** [`sidebar-nav-groups`](../features/sidebar-nav-groups/TDD.md)

## Context

Rendering a collapsible per-app sidebar group requires combining three things: the static app
registry (`APPS`/`AppEntry` in `packages/chrome`), the current user's persisted
`nav_collapsed_groups` preference, and the current request's path (to force the current page's
own group open without persisting that override). `packages/chrome` is a shared package consumed
by two separately deployed services (`organize-me` and `event-creator`), and its existing entry
point, `register_chrome(env, app_service_name)`, runs once at Jinja `Environment` setup time —
before any request, user, or path is known. Something has to own combining these three inputs, and
where that logic lives determines how reusable, testable, and decoupled from each service's own
FastAPI/DB/session machinery the chrome package stays.

## Decision

Add a small pure function to `packages/chrome` (e.g. `organizeme_chrome/nav_groups.py`):

```python
def build_nav_groups(
    apps: list[AppEntry],
    collapsed: dict[str, bool],
    current_path: str,
) -> list[NavGroup]:
    ...
```

It takes plain data in (no `Request`, no DB session, no Jinja) and returns plain data out (a list
of `NavGroup` objects carrying `service_name`, a humanized label, `nav` items, and a resolved
`collapsed: bool` — already accounting for the current-page force-open rule). Each consuming
service calls this function per-request, from its own route or dependency layer, using its own
mechanism for resolving "current user" and "current path," and passes the result into template
context as an ordinary variable. `register_chrome()` itself stays env-setup-time only and does not
attempt to hold per-request state.

## Alternatives considered

- **Bake grouping into `register_chrome()`'s Jinja globals.** Rejected: globals are computed once
  at env-setup time, before any request exists — there is no way to inject per-request user/path
  data into that shape without turning the "global" into a closure that secretly depends on
  request-local state, which is exactly the kind of hidden coupling this decision avoids.
- **Expose grouping as a Jinja global *function*, called from templates as `nav_groups(request)`.**
  Considered seriously — it mirrors how `request.url.path` is already read directly in the
  existing flat-list template. Rejected in favor of the pure-function approach because it would
  require the function to reach into `request.state`/session/DB internals from inside
  `packages/chrome`, coupling the shared package to each service's specific auth/session wiring.
  Keeping the impure "fetch user + call the pure function" step in each service's own route layer
  keeps `packages/chrome` ignorant of how either service authenticates or stores users.
- **Branching logic directly in Jinja templates** (e.g. `{% if service_name in collapsed_dict %}`
  spread across the template). Rejected: untestable without rendering HTML, and duplicates the
  current-page override logic wherever the template is used, which is unacceptable given the
  template is shared and rendered by two different services.

## Consequences

- `build_nav_groups()` is trivially unit-testable with plain dicts/lists — no Request or DB
  fixtures needed, matching the intended "main new test surface" for this feature.
- Each consuming service (organize-me routes, event-creator routes) carries a small amount of
  per-route boilerplate: fetch the current user's `nav_collapsed_groups`, fetch the current path,
  call `build_nav_groups()`, pass into template context. This is duplicated per route rather than
  centralized — an accepted cost, consistent with how `dark_mode`-equivalent context values are
  already threaded into event-creator's page routes today.
- Because `packages/chrome` stays free of `Request`/DB/session imports, it remains safe to import
  from either service without pulling in the other's dependencies.
