"""Find which registered beats appear inside a suspect song, and where."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from .fingerprint import FRAME_SECONDS

MIN_ALIGNED = 50          # aligned hashes needed before we call it a match
MIN_RATIO = 10.0          # best offset must beat the background by this much
MIN_DENSITY = 15.0        # aligned hashes per second of matched audio
MIN_COVERAGE = 0.5        # share of the matched span that actually has hits
WINDOW_SECONDS = 1.0      # resolution for the "coverage" measurement
MIN_WINDOW_HITS = 5       # hits a 1-second window needs to count as matched
MAX_GAP_WINDOWS = 2       # unmatched seconds allowed inside one matched section
STRONG_SHARE = 0.5        # alignments at least this strong count as loop repeats


@dataclass
class Match:
    track_id: int
    aligned: int                 # hashes that line up at the same time offset
    ratio: float                 # how far above random noise the match stands
    song_start: float            # where the beat starts/ends in the suspect song
    song_end: float
    beat_start: float            # which part of the beat was used
    beat_end: float
    coverage: float              # % of 1-second windows in that span with hits
    speed: float = 1.0           # playback speed of the beat inside the song
    loops: bool = False          # beat repeats, so it lines up at several points

    @property
    def speed_label(self) -> str:
        pct = (self.speed - 1) * 100
        if abs(pct) < 0.25:
            return "original speed"
        return f"{abs(pct):.1f}% {'faster' if pct > 0 else 'slower'} (likely sped up/slowed to disguise it)"

    @property
    def confidence(self) -> str:
        if self.ratio >= 20 and self.coverage >= 0.6:
            return "Very strong"
        if self.ratio >= 10 and self.coverage >= 0.4:
            return "Strong"
        return "Possible"


def find_matches(rows, speed: float = 1.0) -> list[Match]:
    """rows: (track_id, db_frame, query_frame) tuples from db.lookup().
    speed: the factor the query was slowed by before fingerprinting; used to map
    times back to the original song."""
    by_track = defaultdict(list)
    for track_id, db_frame, q_frame in rows:
        by_track[track_id].append((db_frame, q_frame))

    matches = []
    for track_id, pairs in by_track.items():
        arr = np.array(pairs)
        offsets = arr[:, 0] - arr[:, 1]                     # beat time - song time
        values, counts = np.unique(offsets, return_counts=True)
        # allow +/-1 frame of jitter around the peak offset
        smoothed = counts.copy()
        smoothed[1:] += counts[:-1] * (np.diff(values) == 1)
        smoothed[:-1] += counts[1:] * (np.diff(values) == 1)
        best = int(np.argmax(smoothed))
        best_offset = values[best]
        best_mask = np.abs(offsets - best_offset) <= 1
        background = np.median(counts) if len(counts) > 1 else 1.0
        ratio = best_mask.sum() / max(background, 1.0)
        if best_mask.sum() < MIN_ALIGNED or ratio < MIN_RATIO:
            continue

        # Beats loop, so the same copied section can line up at several offsets
        # (one per repeat of the loop). Use every alignment nearly as strong as the best.
        strong = values[smoothed >= STRONG_SHARE * smoothed[best]]
        union_mask = np.zeros(len(offsets), bool)
        for o in strong:
            union_mask |= np.abs(offsets - o) <= 1
        loop_groups = int(np.sum(np.diff(np.sort(strong)) > 2)) + 1

        run = _dense_run(arr[union_mask][:, 1] * FRAME_SECONDS / speed)
        if run is None:
            continue
        start, end, coverage = run
        song_t = arr[:, 1] * FRAME_SECONDS / speed
        in_run = (song_t >= start) & (song_t <= end)
        aligned = int((union_mask & in_run).sum())
        span = max(end - start, WINDOW_SECONDS)
        if aligned / span < MIN_DENSITY or coverage < MIN_COVERAGE:
            continue  # scattered hits: shared drum samples, not a copied beat

        beat_t = arr[best_mask & in_run][:, 0] * FRAME_SECONDS
        if len(beat_t) == 0:
            continue
        matches.append(Match(
            track_id=track_id, aligned=aligned, ratio=float(ratio),
            song_start=start, song_end=end,
            beat_start=float(beat_t.min()), beat_end=float(beat_t.max()),
            coverage=coverage, speed=speed, loops=loop_groups > 1,
        ))
    return sorted(matches, key=lambda m: m.aligned, reverse=True)


def _dense_run(times: np.ndarray):
    """Find the longest stretch of 1-second windows that are densely matched,
    allowing short gaps. Returns (start, end, coverage) or None. This keeps a few
    stray hits (e.g. a shared kick drum in the intro) from stretching the span."""
    if len(times) == 0:
        return None
    first = int(times.min() // WINDOW_SECONDS)
    bins = (times // WINDOW_SECONDS).astype(int) - first
    counts = np.bincount(bins)
    dense = np.nonzero(counts >= MIN_WINDOW_HITS)[0]
    if len(dense) == 0:
        return None
    runs, run_start, prev = [], dense[0], dense[0]
    for w in dense[1:]:
        if w - prev > MAX_GAP_WINDOWS + 1:
            runs.append((run_start, prev))
            run_start = w
        prev = w
    runs.append((run_start, prev))
    a, b = max(runs, key=lambda r: counts[r[0]:r[1] + 1].sum())
    in_run = times[(bins >= a) & (bins <= b)]
    windows = b - a + 1
    coverage = float(np.sum(counts[a:b + 1] >= MIN_WINDOW_HITS)) / windows
    return float(in_run.min()), float(in_run.max()), coverage


def speed_factors(max_percent: float, step: float = 0.5) -> list[float]:
    """1.0 first, then outward: 1.005, 0.995, 1.01, 0.99, ..."""
    out = [1.0]
    k = 1
    while k * step <= max_percent + 1e-9:
        out += [1 + k * step / 100, 1 - k * step / 100]
        k += 1
    return out


def check_audio(conn, audio, max_speed_change: float = 6.0) -> list[Match]:
    """Check a song at its original speed and at small speed changes; keep the
    best result per registered beat."""
    from . import db
    from .fingerprint import change_speed, fingerprint_audio

    best: dict[int, Match] = {}
    for factor in speed_factors(max_speed_change):
        # A beat sped up by x% is restored by slowing the song by the same factor.
        hashes = fingerprint_audio(change_speed(audio, factor))
        for m in find_matches(db.lookup(conn, hashes), speed=factor):
            m.speed = factor
            if m.track_id not in best or m.aligned > best[m.track_id].aligned:
                best[m.track_id] = m
    return sorted(best.values(), key=lambda m: m.aligned, reverse=True)
