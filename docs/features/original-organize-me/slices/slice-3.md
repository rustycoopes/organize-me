# Slice 3 — LLM Prompt Page

> Part of the OrganizeMe build plan. Shared context in
> [`../implementation-plan.md`](../implementation-plan.md).

**Delivers:** User can view, edit, and reset their extraction prompt.

## Includes
- `llm_prompts` table migration
- Factory default prompt constant + seed on user creation
- Prompt page: textarea editor, Save button, Reset to Default button
- `/api/v1/llm-prompt` GET/PUT/reset endpoints

## Relevant schema — `llm_prompts`
```
id          UUID PK
user_id     UUID FK → users (UNIQUE — one prompt per user)
prompt_text TEXT NOT NULL
created_at  TIMESTAMPTZ
updated_at  TIMESTAMPTZ
```

## Relevant endpoints (under `/api/v1/`)
| Method | Path | Purpose |
|---|---|---|
| GET/PUT | /llm-prompt | Get/update user's prompt |
| POST | /llm-prompt/reset | Reset to factory default |

## Design notes
- A factory default prompt is seeded into the DB on every new user account creation
  (based on the `examples/example.lmmoutput.txt` format).
- "Reset to Default" restores that factory prompt.

## Testing
- Unit test the prompt-reset logic.
