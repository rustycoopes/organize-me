---
name: next-issue
description: >-
  Choose the single highest-priority Slice 1 issue to work on next from the OrganizeMe GitHub
  project board, explain the choice, and kick off implementation. Use this whenever the user asks
  what to work on next, which issue to pick up, to "grab/start the next issue", "what's next", or to
  triage the Todo column — even if they don't name an issue number. The point is deliberate
  selection (bugs before enhancements before future-enhancements, and judgment within a tier), NOT
  just taking the lowest issue number.
---

# Pick and start the next issue

This project tracks work as GitHub issues on the **OrganizeMe** project board (project #2, owner
`rustycoopes`). The job of this skill is to look at what's ready to work on, make a *considered*
choice about what delivers the most value next, get the user's OK, and hand off to the
`/to-implementation` skill to actually build it.

The reason selection is a deliberate step (rather than "take the next open issue") is that a good
build order gives the project a solid base: fix what's broken before adding new things, land
foundational pieces before the work that depends on them, and don't sink effort into low-priority
polish while higher-value work sits waiting.

**Scope: Slice 1.** We are currently building Slice 1, so this skill only considers issues labelled
`slice1`. (When the project moves on, pass `--slice slice2` to the helper below and update this
line — that's the only change needed.)

## Step 1 — Gather what's ready

Run the bundled helper to get every `Todo` issue in Slice 1, already grouped into priority tiers:

```bash
python .claude/skills/next-issue/scripts/todo_issues.py
```

It reads the project board via `gh`, keeps only items whose Status is `Todo` and that carry the
`slice1` label, and buckets them into `bug` → `enhancement` → `future-enhancement` → `other` by
their labels. It deliberately does **not** pick for you — ordering *within* a tier is a judgment
call the next steps make.

If the helper returns zero issues across all tiers, there's nothing to start: tell the user Slice 1
has no `Todo` work and stop.

## Step 2 — Narrow to the top tier

Priority is strict across tiers, highest first:

1. **`bug`** — a broken thing undermines the base everything else builds on, so bugs come first.
2. **`enhancement`** — the planned Slice 1 features.
3. **`future-enhancement`** — deferred improvements/decisions; worth doing but lowest priority.

Take the highest non-empty tier. Everything below it is out of contention for this run — you only
choose *within* the top occupied tier.

## Step 3 — Choose within the tier (this is the real work)

Do **not** default to the lowest issue number. Read the candidate issues in the top tier
(`gh issue view <n>`) and weigh them:

- **What unblocks the most?** An issue that other Todo issues depend on should go first. Issue
  bodies often say this outright (e.g. "Blocked by #17", "before #16/#17"). Prefer the *unblocker*
  over the *blocked*. (Example: sidebar shell #17 is a dependency of the E2E-tests issue #23, so
  #17 goes first even though both are enhancements.)
- **What's foundational?** Shared plumbing, scaffolding, or interfaces that later work reuses beat
  leaf features.
- **Is it actually ready?** If a candidate is blocked by something still open, or (common for
  `future-enhancement`) is really a "decide whether to…" item needing a product decision rather
  than code, it's not a clean start. Note that.

Pick exactly one. If it's a genuinely close call, say so and name your runner-up.

## Step 4 — Present the choice and confirm

Before starting any implementation, tell the user:

- **The pick:** issue number + title.
- **Why:** which tier it's in, what it beat, and the deciding factor (unblocks X / foundational /
  only bug open, etc.).
- **Any caveat:** if the pick is a "decide whether…" `future-enhancement`, flag that it likely
  needs a quick decision from them first, and recommend settling that before building.

Then ask for a quick go-ahead. `/to-implementation` creates a branch/worktree, writes code,
commits, and opens a PR — real, outward-facing side effects — so it's worth a one-line confirmation
(and a chance to veto a bad pick) rather than charging in. If the user has already said "just pick
one and go", skip the pause.

## Step 5 — Hand off to implementation

On the user's go-ahead, start the selected issue with the `/to-implementation` skill, passing it the
chosen issue. From there, `to-implementation` owns the branch/worktree, build loop, review, PR, and
marking the issue done — this skill's job is finished once the right issue is handed over.

## Notes

- **Only one issue.** Even if several are ready, hand off exactly one; the user can re-run this
  skill for the next.
- **Something already In Progress?** If the board shows a `slice1` issue already `In Progress`,
  mention it — the user may want to finish that rather than start something new.
- **Ties within a tier** are where your judgment earns its keep; make the reasoning visible so the
  user can override it if they know something you don't.
