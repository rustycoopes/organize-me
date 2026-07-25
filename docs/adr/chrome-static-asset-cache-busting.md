# Cache-bust each service's compiled stylesheet with a content-hash query string

**Status:** Accepted
**Date:** 2026-07-25

## Context

A visitor reported HA Dashboard's redesigned tiles rendering with the wrong colors, the wrong
font, and a single-column layout after a deploy that verifiably shipped correctly (confirmed by
rendering the real templates against the real compiled `app.css` locally, and by the same
deploy's own structural HTML changes - which don't depend on the stylesheet - showing up
correctly). A hard refresh (Ctrl+Shift+R) did not fix it.

Every consuming service (`organize-me` itself, `event-creator`, `doc-library`, `ha-dashboard`)
serves its own Tailwind build from a fixed path, `/static/css/app.css` (`scripts/build_css.py` per
repo, per `docs/adr/design-refresh-per-service-tailwind-build.md`), with no content hash or
version in the filename. A browser's hard refresh forces the *browser's own* cache to revalidate,
but does nothing about an intermediate cache (the platform's shared GCP Load Balancer, or Cloud
CDN if enabled in front of it - see `docs/host-integration-guide.md`'s routing section) that keys
its cache entry on the exact request URL and TTL, independent of what the client sends. A stylesheet
byte-identical in URL across releases can keep being served from that layer for as long as its TTL,
regardless of how many times a visitor reloads.

Dynamically-rendered HTML (every page in this platform) never has this problem - it's rendered
per-request and never cached upstream - which is exactly why the visitor saw the new markup/layout
correctly but not the new colors/type.

Each service's `app.css` is compiled from *that service's own* templates plus the shared chrome
templates together (`@source` covers both, per the ADR above) - so the fix has to catch a
template-only change local to one service (like HA Dashboard's tile redesign, which never touched
the shared `organizeme-chrome` package at all), not just a change to the shared package itself.

## Decision

Append a content-hash query string to the stylesheet URL:

```html
<link href="/static/css/app.css?v={{ CHROME_ASSET_VERSION }}" rel="stylesheet" type="text/css" />
```

`organizeme_chrome.assets.chrome_asset_version()` reads the *calling service's own* compiled
`app/static/css/app.css` (a fixed relative path every consuming repo already shares - same
convention as each repo's own `scripts/build_css.py`) and returns a short SHA-256 hash of its
bytes, registered as a Jinja global (`register_chrome`, alongside `theme_attr` and the existing
component-class globals). It's computed once per process, at Jinja-environment setup time - after
the compiled CSS already exists in its final on-disk form (a separate build step both locally and
in the Docker multi-stage build) - so it always reflects what that specific deploy is actually
serving. Any cache keying on the full URL, browser or intermediate, misses the moment the file's
content differs from the previous deploy, whether the change came from that service's own
templates or from a shared chrome release. No caller-side integration needed: every existing
`register_chrome(templates.env, app_service_name=...)` call site picks this up automatically.

## Alternatives considered

- **A version string sourced from the installed `organizeme-chrome` package's own version**
  (`importlib.metadata`). Rejected after further review: this would only bust the cache when the
  *shared chrome package* is released and a consumer bumps its pin - it does nothing for the
  actual scenario that triggered this ADR, where HA Dashboard's own template edits changed its own
  `app.css` content without any chrome-package change at all.
- **Fingerprinted filename** (`app.<contenthash>.css`), the more conventional static-asset
  cache-busting approach and functionally equivalent to the content hash chosen here. Rejected for
  the added build-pipeline complexity (renaming the compiled output and threading that name back
  into the template) for no practical benefit over a query string, which every intermediate cache
  still has to treat as a distinct resource.
- **Cache-Control response headers only** (short `max-age`, `must-revalidate`). Doesn't fix the
  actual failure mode observed: a shared upstream cache is what needs to miss, not the browser -
  a header the client can (and did, via hard refresh) already ask for gets no better result if the
  cache in front of Cloud Run doesn't honor client-sent cache-control the same way. A URL change
  is the one thing every caching layer has to treat as a genuinely different resource.
- **Do nothing, document "hard refresh may not be enough, wait out the CDN TTL."** Rejected -
  leaves every future deploy able to reproduce exactly this report, with no fix a visitor (or an
  agent debugging on their behalf) can act on themselves.

## Consequences

- Every consumer needs its own `organizeme-chrome` pin bumped to a tag built from this change and
  redeployed before `CHROME_ASSET_VERSION` actually appears in its rendered `<link>` tag - the fix
  doesn't apply until that happens per-repo. `ha-dashboard` gets this immediately (the reporting
  app); `event-creator`, `doc-library`, and `organize-me` itself carry the same latent staleness
  risk until they bump too, even though nothing is visibly broken for them today.
- Reads one file (a few tens of KB) from local disk once per process start - negligible, and no
  different in kind from the font-copying `scripts/build_css.py` already does at build time.
- If a future service's static assets ever move off this exact `app/static/css/app.css` relative
  layout, `chrome_asset_version()` silently falls back to a fixed placeholder rather than erroring
  - worth revisiting if that ever happens, since a placeholder means no real cache-busting for that
  service until the path assumption is fixed.
