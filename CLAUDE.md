# Spell Quest — project context

Two applications live in this repo. They are independent and must stay that way.

| | **V1 — the live game** | **V2 — adaptive platform** |
|---|---|---|
| Code | `live-game/index.html` (single file) | `adaptive-platform/` |
| Status | **In daily use by a 6-year-old** | Built, local only, not deployed |
| URL | https://nirmalkumargcp-ux.github.io/spell-quest/ | `http://127.0.0.1:8010/app/` |
| Data | Supabase (`profiles` table) | SQLite locally / Postgres via compose |

**The most important rule: do not break V1.** JAMMU plays it. The whole
`live-game/` folder is published as the website by
`.github/workflows/deploy-live-game.yml`, so any push touching it goes live
within ~2 min. Build V2 alongside; switch over only when the user says so.

Pages is set to **build_type: workflow**. Do not switch it back to
"deploy from a branch" — the repo root no longer holds `index.html`, so the
legacy builder publishes an empty site and the game 404s. That happened once
during the folder split; the fix was re-running the workflow.

---

## V1 — the live game

Single self-contained HTML file. Picture → spell the word on an A–Z keyboard →
timer → 10 words per round → 10/10 to unlock the next level. Six levels
(Little Words, Fun Things, Yummy Food, Animals, All Around, Big Words).

- **Offline-first.** Photos in `images/`, audio in `audio/`, everything inline.
  Never introduce a CDN dependency for gameplay assets.
- **Players (profiles).** Local roster in `localStorage`; each player syncs to
  its own Supabase row keyed by player id. A `__players__` row holds the roster
  so the same profiles appear on every device.
- **Cloud sync is automatic** — saves after every word, on tab close
  (`fetch keepalive`), retries on reconnect / focus / every 20s. The Cloud Sync
  screen is status only; the setup form was removed deliberately (it exposed
  SQL and the API key inside a children's app, and a mis-tap could disconnect
  syncing).

### Supabase
Project `yoaireqzfiammcjuzyct`, table `profiles(id text pk, data jsonb, updated_at)`,
RLS on with an open anon policy. The **anon/public** key is embedded in
`index.html` — that is what it is for, but it means the repo/URL are public.

**Never run bulk deletes against this database.** It holds real progress. Use
test-only row ids (prefix `__test_`) and delete only those. Real rows have been
wiped here before by treating it as a sandbox.

**Also: clear `localStorage` before loading the live site in a test browser.**
Stale local data triggers the legacy migration, which invents a "Player 1"
profile and syncs it into the family's roster. That has happened twice.

Live data at last check: `jammu` (41 words, tier 2), `nirmal-test` (25 words, tier 1).

---

## V2 — the adaptive platform

Implements `Adaptive Kids Learning App Backend.docx` (the product spec) with
the "Field Guide" direction from `Design system scope decisions-handoff.zip`.

```
adaptive-platform/backend/app/
  adaptive/     the core IP — no HTTP, no framework
    config.py         EVERY tunable threshold/weight, single source of truth
    mastery.py        MasteryEngine interface + RuleBasedMasteryEngine
    question_selector.py  candidates → weighted score → seeded draw
    spaced_repetition.py, difficulty.py, progression.py, learner_model.py
    evaluation/       one evaluator per question type, registered
  api/ models/ services/ seed/ simulator/
adaptive-platform/web/index.html   Field Guide child app
live-game/images/ + audio/         shared assets (ASSETS_ROOT overrides)
```

**Design rules that are load-bearing** (from the handoff, not preferences):
green = mastered/go, orange = new, blue = review, **no red anywhere** — a miss
is "not yet". Instrument Serif for display only (≥22px), Karla for anything a
child reads. 64px minimum touch targets. The child sees four named bands
("just started / getting there / good / really good"), never a percentage; the
parent sees numbers.

**Architectural rule from the spec:** the frontend never decides what comes
next, never scores an answer, never computes mastery. It asks
`POST /sessions/{id}/next-question` and renders the reply.

### Run it
```bash
cd adaptive-platform/backend
./.venv/bin/uvicorn app.main:app --port 8010     # 8000 is taken on this Mac
./.venv/bin/python -m pytest -q                  # 44 tests, ~20s
./.venv/bin/python -m app.simulator.simulate     # watch synthetic learners
```
Child app at `/app/`, OpenAPI docs at `/docs`, media at `/media/…`.
No Docker on this Mac — the Dockerfile/compose are written but untested here;
SQLite is the default so nothing is required to run.

### Content
93 concepts × 4 knowledge dimensions (recognition / meaning / context /
spelling) = 372 questions, seeded from
`adaptive-platform/backend/app/seed/data/english.py`,
reusing the same photos and audio as V1.

Tracking mastery **per dimension** is the point — it is how the system
discovers "knows the word, can't spell it" and drills the gap (spec §22).
The simulator demonstrates it: that profile gets ~half its questions on
spelling.

---

## Working preferences (learned)

- The user is **not technical**. Give click-by-click steps and plain language;
  never assume a terminal.
- **Verify, don't assert.** Screenshot the UI, query the database, run the
  tests — then report what actually happened, including failures.
- Ship complete work; when something is broken or half-done, say so plainly.
- The user has a good eye for polish and rejects amateur-feeling output
  (synthetic praise voice, beep sounds, dev scaffolding in the UI).

## Not built

- Authentication (modelled, not enforced — must close before hosting V2)
- Parent dashboard (design deck defers it to "Step 5"; nothing to build against)
- Maths and Science (schema supports them; only English is seeded)
- Botanical-plate illustrations (photos stand in; swap path is wired)
- V2 hosting (user chose "build backend, host later")
