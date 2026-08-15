# Adaptive learning platform

The next version of Spell Quest. Where the live game runs a fixed list of
words, this keeps a model of what the child knows and decides every question
from it.

**Not deployed.** It runs on your Mac only. The live game is unaffected by
anything in this folder.

```
backend/    the engine and the API (Python, FastAPI)
web/        the child app in the "Field Guide" design system
docs/       the product spec and the design handoff this was built from
```

## Run it

```bash
cd backend
./.venv/bin/uvicorn app.main:app --port 8010
```

| | |
|---|---|
| `http://127.0.0.1:8010/app/` | the child app |
| `http://127.0.0.1:8010/docs` | every API endpoint, clickable |

Port 8010 rather than 8000, because something else on this Mac holds 8000.

```bash
./.venv/bin/python -m pytest -q              # 44 tests, about 20 seconds
./.venv/bin/python -m app.simulator.simulate # watch synthetic children learn
```

Photos and audio come from `../live-game/`. Set `ASSETS_ROOT` to override.

## What makes it adaptive

Every word is tracked across four dimensions — spotting it, its meaning, using
it in a sentence, and spelling it. A child can score 95% on meaning and 20% on
spelling for the same word, and the engine responds by drilling spelling on
words they already know rather than serving harder words.

The simulator demonstrates it: a synthetic "strong vocabulary, weak spelling"
learner receives about half its questions on spelling and very few on
recognition.

See [`backend/README.md`](backend/README.md) for how questions are selected,
how mastery is scored, and the seven learner scenarios under test.

## Still open

- **Hosting** — nothing is deployed; you chose to decide this later
- **Authentication** — modelled but not enforced; must be closed before this
  is reachable from the internet
- **Parent dashboard** — the design deck defers it to "Step 5"
- **Migrating JAMMU** — his 41 words are in the old format
