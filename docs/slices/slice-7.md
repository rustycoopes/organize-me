# Slice 7 — Notifications (Email + SMS)

> Part of the OrganizeMe build plan. Shared context in
> [`../implementation-plan.md`](../implementation-plan.md).

**Status:** 7.1 (email, #86) and 7.2 (SMS, #87) implemented. 7.3 (Settings > Notifications tab,
#88) next.

**Delivers:** Users receive branded email and SMS after processing runs (success and failure).

## Includes
- Resend integration (branded HTML email template: OrganizeMe header, event summary table,
  dashboard link)
- Twilio SMS integration (success: count + link; failure: details + link)
- Settings > Notifications tab: toggle SMS on/off, toggle email on/off
- `onboarding_notifications_done` flag set when user saves notification prefs

## Notification matrix
- **Success SMS:** event count + dashboard link.
- **Success email:** styled branded HTML with event summary table + dashboard link.
- **Failure SMS:** failure summary + link to log page.
- **Failure email:** failure details + link to log page.
- **Zero-event:** success notification with count = 0.
- Both channels independently toggled in Settings > Notifications
  (`user.notification_sms`, `user.notification_email`).

## Key utilities
- `app/services/notifications/email.py` — Resend wrapper (first cut may already exist from
  Slice 1's forgot-password email; extend it here)
- `app/services/notifications/sms.py` — Twilio wrapper

## Testing
- Stub Resend + Twilio at the delivery boundary; assert payloads.
- Playwright: notification toggle behaviour.
