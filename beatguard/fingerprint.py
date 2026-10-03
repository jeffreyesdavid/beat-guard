"""Audio fingerprinting: the same core idea Shazam uses.

1. Turn the audio into a spectrogram (which frequencies are loud at each moment).
2. Keep only the strongest peaks: the "constellation" that survives vocals,
   compression and background noise.
3. Pair peaks up. Each pair (freq1, freq2, time gap) becomes a hash.
4. A song containing your beat shares many hashes with it, all lined up at the
   same time offset. That alignment is what proves a match.
"""

from __future__ import annotations

import numpy as np
import soundfile as sf
from scipy.ndimage import maximum_filter
from scipy.signal import resample_poly, stft

SAMPLE_RATE = 11025      # plenty for fingerprinting; keeps things fast
N_FFT = 2048
HOP = 512                # one frame ~= 46 ms
PEAK_NEIGHBORHOOD = (15, 15)   # (freq bins, frames) a peak must dominate
FAN_OUT = 10             # how many partner peaks each anchor pairs with
MAX_DT = 63              # max frames between paired peaks (~2.9 s)
MIN_FREQ_BIN = 5         # ignore rumble below ~27 Hz
FRAME_SECONDS = HOP / SAMPLE_RATE


def load_audio(path: str) -> np.ndarray:
    """Load any WAV/MP3/FLAC as mono float audio at SAMPLE_RATE."""
    data, rate = sf.read(path, dtype="float32", always_2d=True)
    mono = data.mean(axis=1)
    if rate != SAMPLE_RATE:
        g = np.gcd(int(rate), SAMPLE_RATE)
        mono = resample_poly(mono, SAMPLE_RATE // g, int(rate) // g).astype("float32")
    return mono


def find_peaks(audio: np.ndarray) -> np.ndarray:
    """Return an (N, 2) array of (frame, freq_bin) spectrogram peaks."""
    if len(audio) < N_FFT:
        return np.empty((0, 2), dtype=int)
    _, _, z = stft(audio, fs=SAMPLE_RATE, nperseg=N_FFT, noverlap=N_FFT - HOP, boundary=None)
    spec = 20 * np.log10(np.abs(z) + 1e-10)          # (freq, time) in dB
    spec[:MIN_FREQ_BIN, :] = spec.min()
    local_max = maximum_filter(spec, size=PEAK_NEIGHBORHOOD) == spec
    loud = spec > (np.median(spec) + 10)              # skip near-silent bins
    freqs, frames = np.nonzero(local_max & loud)
    order = np.lexsort((freqs, frames))               # sort by time, then freq
    return np.stack([frames[order], freqs[order]], axis=1)


def hashes_from_peaks(peaks: np.ndarray):
    """Yield (hash, anchor_frame) pairs from a constellation of peaks."""
    n = len(peaks)
    for i in range(n):
        t1, f1 = peaks[i]
        paired = 0
        for j in range(i + 1, n):
            t2, f2 = peaks[j]
            dt = t2 - t1
            if dt == 0:
                continue
            if dt > MAX_DT or paired >= FAN_OUT:
                break
            # 11 bits per frequency (bins 0-1024), 6 bits for the time gap
            yield (int(f1) << 17) | (int(f2) << 6) | int(dt), int(t1)
            paired += 1


def fingerprint_audio(audio: np.ndarray) -> list[tuple[int, int]]:
    return list(hashes_from_peaks(find_peaks(audio)))


def fingerprint(path: str) -> tuple[list[tuple[int, int]], float]:
    """Fingerprint a file. Returns ([(hash, frame), ...], duration_seconds)."""
    audio = load_audio(path)
    return fingerprint_audio(audio), len(audio) / SAMPLE_RATE


def change_speed(audio: np.ndarray, factor: float) -> np.ndarray:
    """Undo a 'sped up' / 'slowed' edit. factor > 1 slows the audio down
    (lower pitch, longer), the way a turntable or a lazy speed-up works."""
    if factor == 1.0:
        return audio
    up = int(round(factor * 1000))
    g = np.gcd(up, 1000)
    return resample_poly(audio, up // g, 1000 // g).astype("float32")
