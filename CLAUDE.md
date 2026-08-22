# live-game — session briefing

This folder **is** the published website:
https://nirmalkumargcp-ux.github.io/spell-quest/

It is played daily by a six-year-old (JAMMU). Treat every change as going
straight to a child — because it does, about two minutes after a push.

## What's here

```
index.html     the whole game: markup, styles and logic in one file
images/        502 photos, one per word
audio/         535 clips — every word, every letter name, a few phrases
README.md      the full handover: how it works, how to change it, troubleshooting
```

500 words across 30 themed levels.

No build step and no dependencies. Open `index.html` and it runs.

## Publishing

This folder is the whole repository (`nirmalkumargcp-ux/spell-quest`). GitHub
Pages serves it straight from the `main` branch root — no build step, no
workflow. Push and it is live in about two minutes.

```bash
git add -A && git commit -m "what changed" && git push
```

The adaptive learning platform is a **separate project in a separate
repository**. Nothing here depends on it.

## Rules this game follows

Deliberate product decisions, not accidents:

- **Nothing is "wrong."** A miss shows the correct spelling and reads it out
  letter by letter. No red, no failure sound.
- **A level only opens at 10/10.** A partial score brings the missed words back
  alongside new ones.
- **No spoken praise.** A chime and a short on-screen word. The voice teaches
  words; it does not congratulate.
- **A bad picture is reportable, not fatal.** The 🚩 by the speaker files the
  word under `save.reports` and syncs it; it never skips the word or changes the
  score. Reports are listed under ☁️ Cloud Sync.
- **Offline-first.** Never introduce a CDN or network dependency for gameplay.
  The child must be able to play with no internet.

## Progress and the database

Saves locally after every answer, then to Supabase (project
`yoaireqzfiammcjuzyct`, table `profiles`) — automatically, with retries. One
row per player plus a `__players__` roster row.

**Never bulk-delete rows.** Real progress lives there: JAMMU (41 words) and
Nirmal - test (25 words). For testing, use ids prefixed `__test_` and remove
only those.

**Clear `localStorage` before loading the live site in a test browser.** Stale
data triggers the old-format migration, which invents a "Player 1" profile and
syncs it into the family's roster. That has happened twice.

## Verifying a change

Open the file locally to check behaviour, then after pushing confirm the real
site actually serves it — a green workflow is not proof:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://nirmalkumargcp-ux.github.io/spell-quest/
```

Hard-refresh with ⌘⇧R; browsers cache the old copy.
