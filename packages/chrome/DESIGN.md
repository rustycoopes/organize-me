# chrome package — design notes

The visual system (color, type, shape, dark-mode strategy) lives in the repo-root
[`DESIGN.md`](../../DESIGN.md) and the ADRs under [`docs/adr/`](../../docs/adr/). This file covers
things specific to what the `organizeme_chrome` package *ships* to consumers.

## Shipped CSS

`organizeme_chrome/static/css/` holds raw CSS shipped as package data — never compiled here. Each
consuming service `@import`s these into its own Tailwind v4 entry CSS and runs its own
`pytailwindcss` build (see `docs/adr/design-refresh-per-service-tailwind-build.md`):

| File | Contents | Import style |
|---|---|---|
| `tokens.css` | `@theme`, `@font-face`, `@custom-variant dark` — build directives Tailwind consumes | unlayered, after `@import "tailwindcss"` |
| `components.css` | raw component rules that can't be Tailwind utilities (`.om-stacked-table`) | **unlayered** — rules sit outside every `@layer` and beat `@layer utilities` |

Resolve them from Python with `organizeme_chrome.paths.chrome_tokens_css_path()` /
`chrome_components_css_path()` rather than guessing a site-packages path.

## Responsive tables — `.om-stacked-table`

A dense data table that flips to labelled cards on compact viewports. Lives in `components.css`;
class name is `organizeme_chrome.design.STACKED_TABLE_CLASS`.

**Contract:**

- The class goes on the `<table>` element itself — not a wrapper div (wrappers are often
  load-bearing for Alpine/`x-data`).
- Every `<td>` needs `data-label="<column name>"`. Use the **empty string** for checkbox / actions
  columns — an empty `data-label` suppresses the injected `::before` label.
- Row cells must be `<td>` — a body-header `<th scope="row">` isn't matched by the card-mode
  reset and renders as an orphan table-cell.
- The `<table>` doesn't need `w-full` — card mode sets `display: block` on the table and tbody
  too, so it fills its container.
- Keep `<thead>`. Below the breakpoint it is visually hidden with an sr-only clip (not
  `display:none`), so the real th↔td association still reaches assistive tech. `data-label` is
  therefore **cosmetic only**.
- Below the breakpoint, cells are **not** controllable with Tailwind utilities. The rule is
  imported unlayered and wins, and it explicitly resets `display` / `max-width` / `width` /
  `white-space` / `overflow` so per-cell utilities (`truncate`, `max-w-xs`, `w-10`) don't fight
  the card layout — a `truncate`d cell wraps its full value instead of clipping.
- Dark mode is handled: the card border and `::before` label restate against `paper-2` under the
  `.dark` ancestor (the `ink-2` token they use in light mode is also the dark card surface).
- The consumer's Tailwind entry CSS must `@import` `components.css` (unlayered). A consumer that
  bumps the chrome pin but doesn't add the import gets no change at all.

**Breakpoint:** `max-width: 1023.98px`, i.e. Tailwind's default `lg` (`64rem`). Chosen to match
the shared chrome frame's sidebar-drawer breakpoint so "compact vs full layout" is one boundary
for the frame and the content alike (see `docs/adr/mobile-responsive-tables-breakpoint.md`). The
value is written once, literally, in `components.css`; if chrome ever redefines `--breakpoint-lg`,
that media query needs a matching edit.

See `docs/adr/mobile-responsive-tables-css-delivery.md` for why this ships as raw CSS in a
separate file imported unlayered.
