#!/usr/bin/env python3
"""Piper neural TTS using Homebrew espeak-ng for phonemes (the wheel's bundled one is broken)."""
import subprocess, sys, unicodedata, wave
import numpy as np
from piper import PiperVoice

ESPEAK = "/opt/homebrew/bin/espeak-ng"

def phonemize(text, voice="en-us"):
    """text -> list of sentences, each a list of phoneme characters (piper's scheme)."""
    out = subprocess.run([ESPEAK, "-q", "--ipa", "-v", voice, text],
                         capture_output=True, text=True, check=True).stdout
    sentences = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        # piper decomposes to NFD codepoints and treats each char as a phoneme
        chars = list(unicodedata.normalize("NFD", line))
        sentences.append(chars)
    return sentences or [[]]

_cache = {}
def get_voice(model):
    if model not in _cache:
        _cache[model] = PiperVoice.load(model)
    return _cache[model]

def synth(model, text, out_path, length_scale=1.0, noise_scale=0.667, noise_w=0.8):
    voice = get_voice(model)
    rate = voice.config.sample_rate
    chunks = []
    for phonemes in phonemize(text):
        if not phonemes:
            continue
        ids = voice.phonemes_to_ids(phonemes)
        try:
            from piper import SynthesisConfig
            cfg = SynthesisConfig(length_scale=length_scale, noise_scale=noise_scale, noise_w_scale=noise_w)
            chunk = voice.phoneme_ids_to_audio(ids, cfg)
        except TypeError:
            chunk = voice.phoneme_ids_to_audio(ids)
        arr = np.asarray(chunk)
        if arr.dtype != np.int16:                      # float [-1,1] -> int16
            arr = np.clip(arr, -1.0, 1.0)
            arr = (arr * 32767).astype(np.int16)
        chunks.append(arr)
    audio = np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)
    with wave.open(str(out_path), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(rate)
        wf.writeframes(audio.tobytes())
    return out_path, len(audio) / rate

if __name__ == "__main__":
    model, text, out = sys.argv[1], sys.argv[2], sys.argv[3]
    ls = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    p, dur = synth(model, text, out, ls)
    print(f"wrote {p} ({dur:.2f}s)")
