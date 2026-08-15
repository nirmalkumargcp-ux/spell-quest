# Adaptive Kids Learning — Backend

The learning brain for the children's app. It maintains a model of what each
child knows, and decides what they should see next. The frontend renders; it
never chooses the question (spec §31, §51).

English is the only subject seeded today; the schema and engine are
subject-agnostic, so Maths and Science slot in without a rewrite.

---

## Run it

No Docker needed — the default database is SQLite, so this works on a bare Mac:

```bash
cd backend
python3 -m venv .venv && ./.venv/bin/pip install -r requirements-dev.txt
./.venv/bin/alembic upgrade head          # create the schema
./.venv/bin/python -m app.seed.seed       # load the English curriculum
./.venv/bin/uvicorn app.main:app --reload
```

Then open **http://127.0.0.1:8000/docs** for the interactive API.

With Docker and real Postgres instead:

```bash
docker compose up --build
```

### Tests

```bash
./.venv/bin/python -m pytest -q            # 44 tests, ~20s
```

### Watch a simulated child learn

```bash
./.venv/bin/python -m app.simulator.simulate
```

---

## The shape of it

```
app/
  adaptive/            ← the core IP; no HTTP, no framework
    config.py            every tunable threshold and weight, in one place
    mastery.py           MasteryEngine interface + RuleBasedMasteryEngine
    difficulty.py        ability estimation, difficulty fit, calibration
    question_selector.py candidate generation → scoring → seeded choice
    spaced_repetition.py the review interval ladder
    progression.py       vocabulary estimate and bands
    learner_model.py     the only writer of learner state
    evaluation/          one evaluator per question type, registered
  api/                 thin HTTP layer over the services
  models/              SQLAlchemy: content, learner state, sessions, events
  services/            session orchestration, event log
  seed/                the English curriculum
  simulator/           synthetic learners for verifying engine behaviour
```

**The rule that matters:** adaptive logic lives in `adaptive/`. API endpoints
call it; they never re-implement it.

---

## How a question gets chosen

1. **Candidates** are generated from five sources: due for review, weak
   concepts, concepts being learned, new concepts, and retention checks on
   mastered ones.
2. Each is **scored** on independent signals — source weight, mastery gap,
   difficulty fit against this child's ability in that skill, and variety
   (so the same word, type or dimension doesn't repeat).
3. The top few are **jittered and one is drawn**, so sessions aren't
   predictable. With `ADAPTIVE_SEED` set the choice is fully reproducible.
4. Concepts whose **prerequisites** aren't understood are excluded entirely.

Every selection stores *why* it was chosen on the attempt row, and
`GET /api/children/{id}/debug/learner-state` shows the whole model for a child.

## Knowing a word is not one thing

Each concept is tracked across four **dimensions** — recognition, meaning,
context and spelling — because a child can know what *butterfly* means and
still not be able to spell it. This is what makes the system respond correctly
to "strong vocabulary, weak spelling" (spec §22): it drills spelling on words
the child already knows, rather than simply serving harder words.

The simulator demonstrates it: the `vocab_strong_spelling_weak` profile
receives roughly **half its questions on spelling** and very few on
recognition.

## Mastery

A transparent weighted update — `new = old + learning_rate × evidence` — where
evidence accounts for correctness, question difficulty relative to current
mastery, response time, hints and streaks. No machine learning in V1, by
design (spec §16). Swapping in Bayesian Knowledge Tracing later means
implementing `MasteryEngine.update()/estimate()`; nothing else changes.

Bands: `0.20 introduced · 0.40 learning · 0.65 developing · 0.85 mastered`,
all configurable in one place.

---

## API

| | |
|---|---|
| `POST /api/children` | create a child profile |
| `GET /api/children/{id}/progress` | child view — named bands, no numbers |
| `GET /api/children/{id}/notebook` | the collection, with per-dimension mastery |
| `POST /api/children/{id}/sessions` | start a session (diagnostic first time) |
| `POST /api/sessions/{id}/next-question` | **the engine decides** |
| `POST /api/sessions/{id}/answer` | evaluate, update the model, return feedback |
| `POST /api/sessions/{id}/hint` | progressive hints; costs evidence, not a life |
| `POST /api/sessions/{id}/complete` | session summary and rewards |
| `GET /api/children/{id}/parent-summary` | parent view — real numbers |
| `GET /api/children/{id}/debug/learner-state` | why the engine did what it did |

The child payload never includes the answer, the difficulty or the mastery
score. The parent sees percentages; the child sees "getting there".

---

## Tests worth reading

`tests/test_adaptive_scenarios.py` encodes the seven scenarios from spec §41:

- **A** success raises difficulty · **B** repeated failure lowers it
- **C** a weak dimension gets more practice · **D** mastery enters spaced review
- **E** forgetting lowers mastery and tightens the interval
- **F** prerequisites gate advanced concepts until met
- **G** a long absence surfaces overdue review first

Plus determinism under a fixed seed, no repeats within a session, and a check
that the engine keeps introducing new concepts rather than getting stuck.

---

## Not built yet

Authentication is modelled (`Parent.password_hash`) but not enforced — every
request currently acts on a single implicit family. That must be closed before
this is exposed beyond a local machine (spec §39).
