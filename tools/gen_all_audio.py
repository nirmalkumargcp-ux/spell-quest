#!/usr/bin/env python3
"""Regenerate every Spell Quest clip with the Piper 'Amy' neural voice."""
import os, subprocess, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from piper_say import synth

MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices/en_US-amy-medium.onnx")
OUT = "/Users/nirmal/Claude Projects/Kids game/audio"
TMP = tempfile.mkdtemp(prefix="sq_audio_")
os.makedirs(OUT, exist_ok=True)

WORDS = """cat dog hat bus pig cup bee fox cow car bat owl egg ant box key
fish tree frog cake book moon duck bird ball milk lion bear boat gift kite drum
apple bread pizza grape lemon candy donut honey melon cherry peach carrot mango onion banana
tiger zebra horse mouse sheep panda koala snake whale rabbit monkey turtle penguin camel goat shark
rainbow flower house train plane rocket guitar castle umbrella balloon camera pencil hammer ladder clock
elephant dolphin dinosaur butterfly crocodile hamburger strawberry sunflower octopus kangaroo pineapple telephone helicopter watermelon chocolate""".split()

# letter names — spelled out the way a teacher says them
LETTERS = {
 "a":"ay","b":"bee","c":"see","d":"dee","e":"ee","f":"eff","g":"jee","h":"aitch","i":"eye",
 "j":"jay","k":"kay","l":"el","m":"em","n":"en","o":"oh","p":"pee","q":"cue","r":"ar","s":"ess",
 "t":"tee","u":"you","v":"vee","w":"double-you","x":"ex","y":"why","z":"zee",
}
PHRASES = {
 "greatjob":"Great job!", "welldone":"Well done!", "awesome":"Awesome!",
 "youdidit":"You did it!", "superstar":"You're a superstar!",
 "tryagain":"Good try! Let's learn this one.", "timesup":"Time's up!",
 "levelcomplete":"Level complete! You are amazing!", "perfect":"Perfect! Ten out of ten!",
}

def make(name, text, length_scale):
    wav = os.path.join(TMP, name + ".wav")
    synth(MODEL, text, wav, length_scale=length_scale)
    r44 = os.path.join(TMP, name + "_44.wav")
    subprocess.run(["afconvert", wav, r44, "-f", "WAVE", "-d", "LEI16@44100"], check=True,
                   capture_output=True)
    subprocess.run(["afconvert", r44, os.path.join(OUT, name + ".m4a"),
                    "-f", "m4af", "-d", "aac", "-b", "48000"], check=True, capture_output=True)
    os.remove(wav); os.remove(r44)

n = 0
for w in WORDS:                       # a touch slower than natural so a 6-year-old can follow
    make(w, w + ".", 1.15); n += 1
    if n % 20 == 0: print(f"  words {n}/{len(WORDS)}", flush=True)
print(f"words done: {n}", flush=True)

for ltr, spoken in LETTERS.items():
    make("letter_" + ltr, spoken + ".", 1.2)
print("letters done", flush=True)

for slug, text in PHRASES.items():
    make("phrase_" + slug, text, 1.05)
print("phrases done", flush=True)
print("total files:", len(os.listdir(OUT)))
