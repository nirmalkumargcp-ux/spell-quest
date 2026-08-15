# Spell Quest — the live game

**https://nirmalkumargcp-ux.github.io/spell-quest/**

This folder *is* the website. Everything in it is published to that address;
nothing else in the repository is. It is the version JAMMU plays.

---

## What it is

A picture appears, a voice says the word, and the child spells it on an A–Z
keyboard against a timer. Ten words to a round. A perfect 10/10 unlocks the
next level.

| | |
|---|---|
| Levels | 6 — Little Words, Fun Things, Yummy Food, Animals, All Around, Big Words |
| Words | 93, each with a photo and a spoken clip |
| Players | Separate profiles, each with their own progress |
| Saving | Automatic, on this device and in the cloud |
| Internet | Only needed to sync — the game itself plays offline |

### The rules it follows

- **Nothing is ever "wrong."** A miss shows the correct spelling and reads it
  out letter by letter, then moves on. There is no red and no failure sound.
- **A level only opens at 10/10.** Score 6/10 and the next round is your six
  missed words plus four new ones — it re-teaches before it advances.
- **No spoken praise.** A chime, confetti and a short on-screen word. The
  voice is used for teaching words, nothing else.

---

## The files

```
index.html     the entire game — markup, styles, logic, all in one file
images/        97 photos, one per word (from Wikipedia)
audio/         128 clips — every word, every letter name, a few phrases
```

`index.html` has no dependencies. Open it by double-clicking and it runs.

---

## Changing it

Edit `index.html`, then:

```bash
git add -A
git commit -m "describe the change"
git push
```

GitHub rebuilds the site automatically. It is live in **1–2 minutes**.
Hard-refresh with **⌘⇧R** to see changes — browsers cache the old copy.

### Common edits

**Add a word** — find `TIERS` near the top of the `<script>` and add
`{w:"apple",e:"🍎"}` to a level. It needs `images/apple.jpg` and
`audio/apple.m4a` to exist; see `../tools/README.md` for generating those.

**Change the timer** — `timeForWord()`, currently `15 + letters × 3` seconds.

**Change round length** — `ROUND_SIZE`, currently 10.

**A word with a confusing photo** — add it to `EMOJI_WORDS` and the game shows
a clear icon instead. `sun`, `star`, `cloud` and `corn` are already there,
because their encyclopedia photos mislead a child.

---

## Where progress is stored

Two places, and they heal each other.

1. **On the device** — instantly, every answer.
2. **In your Supabase database** — a moment later, again when the tab closes,
   and it retries by itself on reconnect. Nothing to press.

The ☁️ chip on the home screen tells you which state it's in:

| | |
|---|---|
| ☁️ Saved | It's in the cloud |
| ☁️ Saving… | On its way |
| ⚠️ Saved on device — will sync | Offline; it will go up by itself |

**Database:** Supabase project `yoaireqzfiammcjuzyct`, table `profiles`.
One row per player, keyed by the player's id, plus a `__players__` row holding
the roster so the same profiles appear on every device.

Current data: **JAMMU** — 41 words, Level 3 · **Nirmal - test** — 25 words.

### Two cautions

- **Never bulk-delete rows.** That table holds real progress. If you need to
  experiment, use ids starting `__test_` and delete only those.
- **The API key is in `index.html`.** That is the "anon/public" key and it is
  designed to sit in a web page — but combined with a public repository it
  means anyone with the link can read and write that table. Keep the URL
  within the family; don't post it anywhere public.

---

## If something goes wrong

**The site shows an old version** — hard-refresh (⌘⇧R). If it persists, check
the **Actions** tab on GitHub for a failed deploy.

**The site is down** — check Actions. Every deploy runs a check that
`index.html` exists, so a broken deploy usually means a failed push, not a
broken game. The previous version stays live until a new one succeeds.

**Progress looks wrong** — open **☁️ Cloud Sync** in the app and press
**Sync Now**. Local and cloud progress merge; syncing only ever *adds* words,
so nothing is lost.

**A profile is missing** — it lives in the `__players__` row. Any device that
still has it locally will restore it on the next sync.

---

## How it gets published

The site is built by `.github/workflows/deploy-live-game.yml`, which uploads
**this folder** as the website root. That is why the URL has no `/live-game/`
in it.

If you ever move or rename this folder, update the `path:` in that workflow to
match, or the site will stop updating.
