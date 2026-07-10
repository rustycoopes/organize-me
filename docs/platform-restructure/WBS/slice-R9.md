# Slice R9 — Parity 3: Dashboard + Events + Prompt

> Part of the OrganizeMe Platform Restructure. Structural PRD:
> [`../platform-restructure-prd.md`](../platform-restructure-prd.md) ·
> Technical design: [`../platform-restructure-design.md`](../platform-restructure-design.md)

**Delivers:** The events dashboard (filter / sort / paginate / calendar / delete), the events API,
and the Prompt page (view / edit / reset) rebuilt in Event Creator — completing functional parity.

## What to build

Migrate the remaining Event-Creator surfaces: the Dashboard that replaces R6's placeholder with
the real events table, and the Prompt page. After this slice, every event-extraction feature from
`docs/prd.md` lives in Event Creator with no user-visible behaviour change.

## Includes
- Events dashboard: table (type, description, resolved_date, raw_date_text, agreed_by, Calendar
  link, Tasks link, Delete), HTMX filters/sort/pagination (`app/pages/dashboard.py`,
  `partials/dashboard_body.html`), replacing the R6 placeholder body.
- Events API: list (paginated/filtered/sorted) + single delete + calendar/tasks URL builders
  (`app/api/v1/events.py`, `app/core/calendar_url.py`).
- Onboarding "Getting Started" checklist (3 steps), driven by the R2 settings table.
- Prompt page: view/edit + Reset-to-Default, using the lazy `get_or_create_user_prompt` seed
  (`app/pages/prompt.py`, `app/api/v1/llm_prompt.py`, `app/core/prompts.py`).

## Relevant schema — `event_creator`
- `events` (read/delete), `llm_prompts` (read/update/reset), `user_settings` (onboarding flags).

## Relevant endpoints (moved into Event Creator)
| Method | Path | Purpose |
|---|---|---|
| GET | /api/v1/events | List events (paginated, filtered, sorted) |
| DELETE | /api/v1/events/{id} | Delete single event |
| GET/PUT | /api/v1/llm-prompt | Get/update user's prompt |
| POST | /api/v1/llm-prompt/reset | Reset to factory default |
| GET | /dashboard · /prompt | Pages |

## Design notes
- Pagination 50/page; default sort newest `resolved_date_earliest` first; calendar link uses the
  earliest date with full raw text + `agreed_by` in the description — unchanged from today.
- Post-login redirect target: today's monolith hardcodes `/profile`
  (`app/api/v1/auth.py`); with the split, the natural landing page is the Event Creator
  `/dashboard` via the Load Balancer — confirm/adjust the Host's redirect here.
- The onboarding checklist reads the R2 `event_creator` settings flags, not `users`.

## Blocked by
- R6 (Event Creator scaffold + SSO trust).

## Acceptance criteria
- [ ] The Dashboard renders the real events table with filter/sort/pagination and Calendar/Tasks
      links at parity, replacing R6's placeholder.
- [ ] Single-event delete (with confirm) works; calendar/tasks URL builders match today.
- [ ] The Prompt page view/edit/reset works, seeding the default prompt lazily on first use.
- [ ] The onboarding checklist reflects the R2 settings flags.
- [ ] PRD stories covering dashboard/events/prompt pass via the new structure.

## Testing
- Unit: `calendar_url` builders, duplicate detection, prompt reset.
- E2E: dashboard filter/sort/paginate/delete; prompt edit + reset; onboarding checklist visibility.
