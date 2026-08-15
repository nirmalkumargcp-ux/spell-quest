# Asset pipeline

How the photos and the spoken audio in this repo were produced. You only need
this if you are **adding new words** or **changing the voice** — the generated
assets are committed, so the apps run without any of it.

## Audio — Piper neural TTS ("Amy")

`audio/` holds 128 clips: one per word, one per letter name, plus a few
phrases. They were generated locally with [Piper](https://github.com/OHF-Voice/piper1-gpl),
not macOS `say` — this Mac only has low-quality "compact" system voices, which
is what made the earlier audio sound robotic.

The published `piper-tts` wheel ships a broken espeak-ng data path on macOS, so
`piper_say.py` bypasses Piper's own phonemizer and calls Homebrew's espeak-ng
for IPA, then runs Piper's ONNX model directly.

### Regenerate

```bash
brew install espeak-ng

python3 -m venv .venv-tts
./.venv-tts/bin/pip install piper-tts numpy
./.venv-tts/bin/python -m piper.download_voices \
    --download-dir voices en_US-amy-medium

./.venv-tts/bin/python tools/gen_all_audio.py     # writes into audio/
```

`gen_all_audio.py` expects `voices/en_US-amy-medium.onnx` next to it and uses
macOS `afconvert` to resample to 44.1 kHz and encode AAC (Piper emits 22 kHz,
which AAC rejects at these settings).

Word list lives in the script; keep it in step with
`backend/app/seed/data/english.py`.

## Photos — Wikipedia

`images/` holds 97 JPEGs pulled from Wikipedia page thumbnails via the
MediaWiki API, one per word, with a curated article title per word to avoid
ambiguity (e.g. `cow` → *Cattle*). Fetch them in one batched API call, then
download with pacing — hitting the API per word gets you rate-limited (429).

Four words deliberately use an emoji instead of a photo, because the
encyclopedia image is misleading for a child: **sun** and **star** are both
grey telescope discs, **cloud** is a view from orbit, **corn** is a botanical
diagram. That list is `EMOJI_WORDS` in the root `index.html`.

Photos are Wikipedia-sourced and credited in the app footer.
