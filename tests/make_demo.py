"""Create demo audio so you can try beat-guard without your own files.

    python tests/make_demo.py
    python -m beatguard --db demo/demo.db register demo/beat_*.wav
    python -m beatguard --db demo/demo.db check demo/industry_song.mp3 --report demo/report.html
"""

from pathlib import Path

import soundfile as sf
from scipy.signal import resample

from synth import SR, make_beat, make_stolen_song

out = Path(__file__).resolve().parent.parent / "demo"
out.mkdir(exist_ok=True)
beats = {name: make_beat(seed) for seed, name in enumerate(["night_drive", "sunset", "cold_case"])}
for name, audio in beats.items():
    sf.write(out / f"beat_{name}.wav", audio, SR)

# "cold_case", sped up 3% with vocals on top, after a different intro
sped = resample(beats["cold_case"], int(len(beats["cold_case"]) / 1.03))
sf.write(out / "industry_song.mp3", make_stolen_song(sped, 4, 34, intro_seed=99), SR, format="MP3")
sf.write(out / "innocent_song.mp3", make_stolen_song(make_beat(500), 0, 30, intro_seed=98), SR, format="MP3")
print(f"Demo files written to {out}")
