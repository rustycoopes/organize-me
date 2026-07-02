# Slice 5 — Events Dashboard

> Part of the OrganizeMe build plan. Shared context in
> [`../implementation-plan.md`](../implementation-plan.md).

**Delivers:** Full events table with filters, sort, pagination, calendar/tasks links, and delete.

## Includes
- Dashboard page: table (type, description, resolved_date, raw_date_text, agreed_by chips,
  Calendar link, Tasks link, Delete)
- Filters: event type dropdown, date range pickers, free-text search (HTMX-driven)
- Default sort: newest `resolved_date_earliest` first; user-sortable by date
- Pagination: 50 per page
- Google Calendar URL builder (title + resolved_date_earliest + description with
  raw_date_text and agreed_by)
- Google Tasks URL builder (title + due date)
- Single event delete (with confirmation via DaisyUI modal)
- Getting Started checklist (3 steps, shown until all complete)

## Relevant schema — `events` (read/delete; created in Slice 4)
```
id, user_id, run_id, type, description,
resolved_date (TEXT, may be multi-date),
resolved_date_earliest (DATE — sort key + calendar date),
raw_date_text, agreed_by (JSONB), created_at
```

## Relevant endpoints (under `/api/v1/`)
| Method | Path | Purpose |
|---|---|---|
| GET | /events | List events (paginated, filtered, sorted) |
| DELETE | /events/{id} | Delete single event |

## Key utilities introduced (build once, reused later)
- `app/core/calendar_url.py` — Google Calendar + Tasks URL builders

## Design notes
- **Pagination:** 50 events per page. **Default sort:** newest `resolved_date_earliest` first.
- **Calendar link** uses `resolved_date_earliest`; full raw date text goes into the
  description field along with the `agreed_by` list.
- **Onboarding checklist** (3 steps: Connect Storage → Set Notification Preferences →
  Upload First File) is shown until all three boolean flags on the user record are complete.

## Testing
- Unit test the `calendar_url` builders.
