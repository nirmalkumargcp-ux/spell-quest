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
| Levels | 30, themed — Little Words and Fun Things through Dinosaur Dig and Really Big Words |
| Words | 500, each with a photo and a spoken clip |
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
images/        502 photos, one per word (from Wikipedia)
audio/         535 clips — every word, every letter name, a few phrases
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
`audio/apple.m4a` to exist; the asset pipeline that generates those lives in
the adaptive-platform repo, under `tools/`.

**Add a level** — put it at the **end** of `TIERS`, and give it a
`.level.lNN .face` gradient in the CSS. Never insert or reorder a level:
`save.tier` is an index into `TIERS` and `save.practice` is keyed by that same
index, so renumbering an existing level silently moves every player onto the
wrong one and misfiles their practice words.

**Change the timer** — `timeForWord()`, currently `15 + letters × 3` seconds.

**Change round length** — `ROUND_SIZE`, currently 10.

**A word with a confusing photo** — add it to `EMOJI_WORDS` and the game shows
the emoji instead. `sun`, `star` and `mouth` are already there: Wikipedia's lead
image is a grey telescope disc for the first two, and a lion's open jaws for the
third. There is no `images/mouth.jpg`; the emoji is the picture.

**Reporting a bad picture while playing** — a small grey 🚩 sits beside the 🔊
button on the play screen. Tapping it files the word under `save.reports` and
turns the flag red. It deliberately does **not** skip the word or change the
score — the word is still spoken aloud, so the round stays playable, and a child
tapping it changes nothing. Reports sync like progress does, so one made on the
child's tablet reaches your device. Read and clear them under **☁️ Cloud Sync**,
which only shows the panel when there is something to show.

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

This folder is the repository `nirmalkumargcp-ux/spell-quest`, and GitHub Pages
publishes the `main` branch root directly. There is no build step and no
workflow to maintain — `index.html` sits at the root, which is exactly what
Pages serves.

The adaptive learning platform lives in its own repository and shares nothing
with this one but a copy of the photos and audio.
