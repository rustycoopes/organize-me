# OrganizeMe — Product Requirements Document

**Version:** 1.0  
**Date:** 2026-06-30  
**Status:** Draft

---

## Problem Statement

People who communicate agreements, logistics, and commitments via messaging apps (WhatsApp, SMS) have no automated way to turn those conversations into calendar events or tasks. Instead, they must manually re-read conversation history, interpret dates that were described loosely ("tomorrow", "Saturday"), and create calendar entries by hand. This is error-prone, time-consuming, and means agreements can easily be missed.

For co-parents, caregivers, small business owners, and anyone coordinating logistics over chat, this friction compounds — the same conversation history is processed repeatedly, manually, with no audit trail.

---

## Solution

OrganizeMe is a multi-user web application that monitors a connected cloud storage folder for conversation export files (WhatsApp `.txt`, `.zip`, or `.csv`). When a new file is detected, the system automatically extracts agreed events and actions using the Gemini LLM, stores them in a structured events dashboard, and notifies the user by SMS and email. Users can also upload files manually. Every extracted event can be added to Google Calendar or Google Tasks with a single click.

---

## User Stories

### Authentication & Account Management

1. As a new visitor, I want to see a landing page that explains what OrganizeMe does, so that I can decide whether to sign up.
2. As a new visitor, I want to create an account using Google OAuth, so that I can sign up quickly without choosing a password.
3. As a new visitor, I want to create an account using my email address and a password, so that I can register without using Google.
4. As a returning user, I want to log in with Google OAuth, so that I can access my account quickly.
5. As a returning user, I want to log in with my email address and password, so that I can access my account using my credentials.
6. As a user who forgot my password, I want to trigger a password reset by email, so that I can regain access to my account.
7. As a user, I want my account to be open to self-registration without needing an invitation, so that anyone can sign up.
8. As a user, I want to permanently delete my account and all associated data, so that I have full control over my personal information.

### Profile & Preferences

9. As a user, I want to update my display name and email address in my profile, so that my account details stay accurate.
10. As a user, I want to set a mobile phone number in my profile, so that the system can send me SMS notifications.
11. As a user, I want to toggle between dark mode and light mode, so that the UI matches my visual preference.
12. As a user, I want my UI preference (dark/light mode) to persist across sessions, so that I don't have to set it again each time I log in.

### Storage Configuration

13. As a user, I want to connect my Dropbox account using OAuth, so that OrganizeMe can monitor a folder in my Dropbox for new conversation export files.
14. As a user, I want to connect my Google Drive account using OAuth, so that OrganizeMe can monitor a folder in my Google Drive for new conversation export files.
15. As a user, I want to connect an AWS S3 bucket by providing credentials manually (access key, secret key, bucket name, region), so that OrganizeMe can monitor a specific S3 folder for new files.
16. As a user, I want to specify the exact folder path within my connected storage that OrganizeMe should watch, so that only files in the intended location are processed.
17. As a user, I want to connect only one cloud storage provider at a time, so that my configuration stays simple and unambiguous.
18. As a user, I want the Settings > Storage tab to show only the fields relevant to the provider I have selected, so that I am not confused by irrelevant configuration options.
19. As a user, I want successfully processed files to be automatically moved to a `processed/` subfolder within my watch folder, so that I can see which files have already been handled.
20. As a user, I want files that fail processing to be automatically moved to a `failed/` subfolder within my watch folder, so that I can identify and retry them.

### Processing Settings

21. As a user, I want to set a "message window" (number of days to look back) as a default of 7 days, up to a maximum of 90 days, so that processing focuses on recent relevant messages.
22. As a user, I want to view and edit the LLM prompt used to extract events from conversation history, so that I can tune the extraction to my specific use case.
23. As a user, I want the prompt editor to always show the current active prompt, and for there to be exactly one prompt (no creation or deletion of additional prompts), so that prompt management stays simple.

### Manual File Upload

24. As a user, I want to manually upload a WhatsApp or SMS export file (`.txt`, `.zip`, or `.csv`) for immediate processing, so that I can process files on demand without waiting for the storage watcher.
25. As a user, I want manually uploaded files to go through the exact same processing pipeline as auto-detected files, so that the results are consistent regardless of how the file was submitted.

### Processing Pipeline & Progress

26. As a user, I want to see the processing pipeline displayed as a sequence of graphical steps (e.g., File Received → Unzip → Filter by Date → Call LLM → Parse Response → Deduplicate → Save → Notify), so that I understand what the system is doing in real time.
27. As a user, I want all pipeline steps to be shown — including success and failure states per step — so that I have full visibility into where a failure occurred.
28. As a user, I want to view a processing history list showing all past processing runs, so that I can review previous uploads and their outcomes.
29. As a user, I want to drill into any historical processing run and see its step-by-step detail and logs, so that I can diagnose issues with past runs.

### Logs

30. As a user, I want to view structured logs for any processing run that are searchable and filterable, so that I can efficiently find error details.
31. As a user, I want to download logs for a processing run, so that I can share them or keep an offline record.

### Events Dashboard

32. As a user, I want to see a dashboard table showing all extracted events with the following columns: event type, description, resolved date, raw date text, agreed-by (shown as initials chips), Google Calendar link, Google Task link, and a delete option, so that I have a complete picture of all extracted agreements.
33. As a user, I want each "Add to Google Calendar" button to open a pre-filled Google Calendar event creation page in a new tab, so that I can add the event to my calendar without re-typing details.
34. As a user, I want each "Add to Google Task" button to open a pre-filled Google Tasks creation page in a new tab, so that I can create a task without re-typing details.
35. As a user, I want to filter the events dashboard by event type, date range, and free-text search, so that I can find specific events quickly.
36. As a user, I want to sort the events dashboard by date, so that I can view events in chronological order.
37. As a user, I want to delete individual events from the dashboard, so that I can remove entries that are no longer relevant.
38. As a user, I want event types to be dynamic (whatever the LLM returns), so that the system adapts to new categories without requiring code changes.
39. As a user, I want duplicate events (same description and same resolved date) to be automatically detected and skipped on import, so that the dashboard does not show repeated entries.

### Notifications

40. As a user, I want to receive an SMS notification after a successful processing run, containing a count of extracted events and a link to the dashboard, so that I am informed immediately when new events are available.
41. As a user, I want to receive a rich HTML email after a successful processing run, containing a summary table of the extracted events and a link to the dashboard, so that I can review results directly in my inbox.
42. As a user, I want to receive an SMS notification when a processing run fails, containing a link to the log viewing page, so that I can quickly investigate the failure.
43. As a user, I want to receive an email notification when a processing run fails, containing details of the failure and a link to the log viewing page, so that I have full context when diagnosing errors.
44. As a user, I want to independently toggle SMS notifications on or off, so that I can control whether the system sends me text messages.
45. As a user, I want to independently toggle email notifications on or off, so that I can control whether the system sends me emails.

### Onboarding

46. As a first-time user, I want to see a "Getting Started" checklist on the dashboard after I first sign up, so that I understand the steps needed to get the system running (connect storage, configure settings, upload a first file).
47. As a user who has completed onboarding, I want the Getting Started checklist to no longer be shown once all steps are completed, so that the dashboard stays clean.

### Navigation & Layout

48. As a user, I want a persistent left sidebar navigation, so that I can move between main sections (Dashboard, Upload, Processing, Logs, Prompt, Settings, Profile) without losing my place.
49. As a user, I want the Settings area to be divided into three tabs (Storage, Notifications, Preferences), so that related settings are grouped together.

### Landing Page

50. As a visitor, I want the landing page to contain three sections — a hero section, a features section, and a call-to-action section — so that I get a clear, structured introduction to the product before signing up.

### Security & Data Privacy

51. As a user, I want all my personal data and conversation content to be stored encrypted, so that sensitive information is protected at rest.
52. As a user, I want my cloud storage credentials (API keys, OAuth tokens) to be stored securely and never exposed, so that my storage accounts cannot be accessed by others.

---

## Implementation Decisions

> This section captures decisions made during requirements discovery. Technical approach is deferred to the Tech Design document.

- **Authentication:** Google OAuth and email/password are both supported as sign-in methods. Password reset by email is required.
- **Storage providers:** Dropbox (OAuth), Google Drive (OAuth), and AWS S3 (manual credentials). Only one provider may be active per user at a time. Each provider requires a specific folder path to watch.
- **Storage settings form:** Fields displayed adapt dynamically to the selected provider — OAuth providers show an "Authorise" button; S3 shows credential input fields.
- **File formats supported:** `.txt`, `.zip`, `.csv` — identical pipeline for all.
- **File lifecycle:** On success, file is moved to `processed/` subfolder. On failure, moved to `failed/` subfolder.
- **LLM:** Gemini is the LLM provider. One active prompt per user (no multi-prompt management).
- **Date window:** Default 7 days look-back, configurable up to 90 days max.
- **Event data model (derived from `examples/example.lmmoutput.txt`):**
  ```json
  {
    "type": "string (dynamic, LLM-provided)",
    "description": "string",
    "resolved_date": "string (human-readable, may span multiple dates)",
    "raw_date_text": "string (original text from conversation)",
    "agreed_by": ["array of participant names"]
  }
  ```
- **Duplicate detection:** Exact match on `description` + `resolved_date`. Duplicates are skipped, not overwritten.
- **Google Calendar / Google Tasks integration:** Pre-filled URL approach (open a URL in a new tab with event details pre-populated). No OAuth write access to calendar required.
- **Notifications:** Success SMS = count + link. Success email = rich HTML with event table + link. Failure SMS/email = failure details + link to logs. Each channel independently toggled.
- **Phone number:** User provides in profile settings; used for SMS delivery.
- **Pipeline steps (7 steps):** File Received → Extract (unzip if needed) → Filter by Date → Call Gemini LLM → Parse LLM Response → Deduplicate & Save → Notify.
- **Processing history:** List of past runs, each drillable to show per-step status and structured logs.
- **Logs:** Structured, searchable, downloadable per run.
- **UX style:** Laravel-inspired aesthetic. Left sidebar navigation. Dark/light mode toggle in profile preferences.
- **Onboarding:** Getting Started checklist surfaced on the dashboard for new users; dismissed once steps are complete.
- **Landing page:** Hero + Features + CTA sections.
- **Account deletion:** Self-service, removes all user data.
- **Admin panel:** Out of scope for initial release.

---

## Testing Decisions

- Tests should verify observable user-facing behaviour, not internal implementation details or LLM outputs.
- The events dashboard is the primary integration seam: a processing run should produce correct, deduplicated rows in the dashboard.
- The `examples/example.whatsapp.txt` file (630 lines of real conversation) and `examples/example.lmmoutput.txt` (22 extracted events) serve as canonical fixtures for end-to-end pipeline testing.
- Notification delivery (SMS, email) should be testable via stubs/mocks at the delivery boundary.
- Duplicate detection logic should be unit-tested against known matching and non-matching pairs.
- Storage provider connectivity (Dropbox, Google Drive, S3) should be tested against test sandboxes or mocks to avoid coupling tests to live credentials.
- UI preference persistence (dark/light mode), notification toggles, and storage configuration forms are good candidates for browser-level integration tests.

---

## Out of Scope

- **Admin panel / back-office tooling** — deferred to a future release.
- **Multiple simultaneous storage connections** — one provider at a time only.
- **Multi-prompt management** — there is exactly one prompt per user; no creation of additional prompts, no deletion.
- **LLM provider choice** — Gemini only; no model switching UI.
- **Native mobile apps** — web application only.
- **Direct Google Calendar / Google Tasks write access via API** — pre-filled URL approach is used instead.
- **Invitation-only or team/organisation accounts** — open self-registration only.
- **Export of the events dashboard** — not included in v1.
- **In-app re-processing of failed files** — files move to `failed/` folder; user must re-upload manually.

---

## Further Notes

- The product name is **OrganizeMe** (finalised — not to be changed).
- The application is general-purpose (not limited to co-parenting; any structured messaging conversation is a valid input).
- The WhatsApp export format (`examples/example.whatsapp.txt`) and LLM output format (`examples/example.lmmoutput.txt`) are the canonical reference formats for the first release.
- "Agreed-by" names come from the LLM output and are displayed as initials chips on the dashboard — no user-side configuration of participant names is required.
- The `resolved_date` field from the LLM may represent multiple dates (e.g., `"Sunday 28 June 2026, Monday 29 June 2026"`); the dashboard must handle multi-date values gracefully.
- Tech Design (architecture, stack selection, infrastructure) is documented separately in `docs/features/original-organize-me/technical-approach.md`.
