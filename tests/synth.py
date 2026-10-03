"""Generate test audio: synthetic beats and speech-like 'vocals'.

Lets the test suite (and anyone trying the tool) work without real music files.
"""

from __future__ import annotations

import numpy as np

SR = 44100
NOTES = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def hz(semitones_from_a4: float) -> float:
    return 440.0 * 2 ** (semitones_from_a4 / 12)


def _env(n, attack=0.005, decay=0.2):
    t = np.arange(n) / SR
    return np.minimum(1, t / attack) * np.exp(-t / decay)


def _place(buf, sound, start):
    end = min(len(buf), start + len(sound))
    if start < len(buf):
        buf[start:end] += sound[: end - start]


def make_beat(seed: int, seconds: float = 40.0) -> np.ndarray:
    """A loop-based beat whose tempo, key, drum pattern and melody depend on seed."""
    rng = np.random.default_rng(seed)
    bpm = rng.integers(80, 150)
    root = rng.integers(-24, -12)                     # bass root, semitones from A4
    step = int(SR * 60 / bpm / 4)                     # 16th note
    n = int(SR * seconds)
    out = np.zeros(n, dtype=np.float64)

    kick_pat = rng.random(16) < 0.3; kick_pat[0] = True
    snare_pat = np.zeros(16, bool); snare_pat[[4, 12]] = True
    hat_pat = rng.random(16) < 0.7
    scale = np.array([0, 3, 5, 7, 10, 12, 15])          # minor pentatonic-ish
    melody = rng.choice(scale, 16) + 12
    chords = [rng.choice([0, 3, 5, 7, 8, 10]) for _ in range(4)]

    t_kick = np.arange(int(0.25 * SR)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(50 + 70 * np.exp(-t_kick * 30)) / SR) * _env(len(t_kick), decay=0.15)
    snare = rng.standard_normal(int(0.2 * SR)) * _env(int(0.2 * SR), decay=0.06) * 0.5
    hat = np.diff(rng.standard_normal(int(0.05 * SR) + 1)) * _env(int(0.05 * SR), decay=0.015) * 0.25

    i = 0
    for pos in range(0, n, step):
        s = i % 16
        bar = (i // 16) % 4
        if kick_pat[s]: _place(out, kick, pos)
        if snare_pat[s]: _place(out, snare, pos)
        if hat_pat[s]: _place(out, hat, pos)
        if s % 2 == 0:  # melody on 8ths
            f = hz(root + 24 + chords[bar] + melody[s])
            t = np.arange(int(step * 1.8)) / SR
            _place(out, 0.25 * np.sin(2 * np.pi * f * t) * _env(len(t), decay=0.25), pos)
        if s == 0:      # bass + chord pad each bar
            t = np.arange(step * 16) / SR
            fb = hz(root + chords[bar])
            _place(out, 0.35 * np.sin(2 * np.pi * fb * t) * _env(len(t), decay=1.5), pos)
            for iv in (0, 3, 7):
                fc = hz(root + 12 + chords[bar] + iv)
                _place(out, 0.08 * np.sign(np.sin(2 * np.pi * fc * t)) * _env(len(t), 0.05, 2.0), pos)
        i += 1
    return out / (np.abs(out).max() + 1e-9) * 0.8


def make_vocals(seed: int, seconds: float) -> np.ndarray:
    """Speech-like audio: pitched pulses through shifting vowel formants, in syllables."""
    rng = np.random.default_rng(seed + 1000)
    n = int(SR * seconds)
    t = np.arange(n) / SR
    pitch = 140 + 40 * np.sin(2 * np.pi * 0.3 * t) + 20 * rng.standard_normal() * np.sin(2 * np.pi * 1.7 * t)
    phase = 2 * np.pi * np.cumsum(pitch) / SR
    source = sum(np.sin(k * phase) / k for k in range(1, 25))
    out = np.zeros(n)
    formants = [(730, 1090), (270, 2290), (530, 1840), (300, 870), (660, 1720)]
    syl = int(SR * 0.18)
    for start in range(0, n - syl, syl):
        f1, f2 = formants[rng.integers(len(formants))]
        seg = source[start:start + syl]
        spec = np.fft.rfft(seg)
        freqs = np.fft.rfftfreq(syl, 1 / SR)
        shape = np.exp(-((freqs - f1) / 90) ** 2) + 0.6 * np.exp(-((freqs - f2) / 120) ** 2)
        out[start:start + syl] += np.fft.irfft(spec * shape, syl) * np.hanning(syl) * (rng.random() > 0.15)
    return out / (np.abs(out).max() + 1e-9) * 0.8


def make_stolen_song(beat: np.ndarray, beat_from: float, beat_to: float, intro_seed: int,
                     intro_seconds: float = 8.0, vocal_level: float = 1.0) -> np.ndarray:
    """An 'industry song': a different intro, then a slice of the beat with vocals on top."""
    piece = beat[int(beat_from * SR):int(beat_to * SR)]
    intro = make_beat(intro_seed, intro_seconds) * 0.6
    vocals = make_vocals(intro_seed, len(piece) / SR)[: len(piece)] * vocal_level
    rng = np.random.default_rng(intro_seed)
    body = 0.6 * piece + 0.6 * vocals + 0.01 * rng.standard_normal(len(piece))
    song = np.concatenate([intro, body])
    return song / (np.abs(song).max() + 1e-9) * 0.9
