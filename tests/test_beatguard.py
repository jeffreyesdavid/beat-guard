"""End-to-end tests using generated beats, so no real music is needed.

Every suspect song goes through MP3 compression first, like a real release.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample

sys.path.insert(0, str(Path(__file__).parent))
from synth import SR, make_beat, make_stolen_song, make_vocals  # noqa: E402

from beatguard import db, proof  # noqa: E402
from beatguard.fingerprint import fingerprint, load_audio  # noqa: E402
from beatguard.match import check_audio, speed_factors  # noqa: E402
from beatguard.report import build_report  # noqa: E402


def speed_up(audio, percent):
    return resample(audio, int(len(audio) / (1 + percent / 100)))


class BeatGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp())
        cls.conn = db.connect(cls.dir / "lib.db")
        cls.beats, cls.ids = {}, {}
        for seed in range(4):
            audio = make_beat(seed)
            path = cls.dir / f"beat{seed}.wav"
            sf.write(path, audio, SR)
            hashes, duration = fingerprint(str(path))
            cls.beats[seed] = audio
            cls.ids[seed] = db.add_track(cls.conn, f"beat{seed}", str(path), proof.sha256_file(str(path)),
                                         duration, "2026-10-02", hashes)

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()
        shutil.rmtree(cls.dir)

    def check(self, song):
        """Write the song as an MP3 (lossy, like a real release), then check it."""
        path = self.dir / "suspect.mp3"
        sf.write(path, song, SR, format="MP3")
        return check_audio(self.conn, load_audio(str(path)))

    def assert_found(self, matches, seed):
        self.assertEqual([m.track_id for m in matches], [self.ids[seed]])

    # --- should catch -----------------------------------------------------
    def test_beat_with_vocals_and_intro(self):
        matches = self.check(make_stolen_song(self.beats[2], 6, 34, intro_seed=99))
        self.assert_found(matches, 2)
        m = matches[0]
        self.assertAlmostEqual(m.song_start, 8.0, delta=1.0)   # after the 8 s intro
        # sampled from 0:06; a looping beat may also report one of the loop's repeats
        self.assertTrue(abs(m.beat_start - 6.0) <= 1.0 or m.loops)
        self.assertEqual(m.confidence, "Very strong")

    def test_vocals_much_louder_than_beat(self):
        self.assert_found(self.check(make_stolen_song(self.beats[1], 0, 25, 51, vocal_level=3.0)), 1)

    def test_short_five_second_sample(self):
        self.assert_found(self.check(make_stolen_song(self.beats[3], 2, 7, 52)), 3)

    def test_quiet_beat_under_vocals(self):
        song = np.concatenate([make_beat(53, 5) * 0.5,
                               0.25 * self.beats[0][: SR * 20] + 0.6 * make_vocals(53, 20)])
        self.assert_found(self.check(song), 0)

    def test_sped_up_beat_and_reports_speed(self):
        matches = self.check(make_stolen_song(speed_up(self.beats[2], 4), 5, 30, 54))
        self.assert_found(matches, 2)
        self.assertAlmostEqual(matches[0].speed, 1.04, delta=0.006)
        self.assertIn("faster", matches[0].speed_label)
        self.assertAlmostEqual(matches[0].song_start, 8.0, delta=1.0)  # not pulled into the intro

    def test_slowed_down_beat(self):
        matches = self.check(make_stolen_song(speed_up(self.beats[0], -3), 5, 30, 55))
        self.assert_found(matches, 0)
        self.assertIn("slower", matches[0].speed_label)

    # --- should NOT flag --------------------------------------------------
    def test_unrelated_songs_are_clean(self):
        for seed in (70, 71, 72):
            with self.subTest(seed=seed):
                self.assertEqual(self.check(make_stolen_song(make_beat(seed + 100), 0, 30, seed)), [])

    # --- supporting pieces ------------------------------------------------
    def test_speed_factors_start_at_original(self):
        f = speed_factors(1.0)
        self.assertEqual(f[0], 1.0)
        self.assertEqual(len(f), 5)

    def test_duplicate_file_detected_by_hash(self):
        path = str(self.dir / "beat0.wav")
        self.assertIsNotNone(db.find_by_sha(self.conn, proof.sha256_file(path)))

    def test_report_hides_full_paths(self):
        matches = self.check(make_stolen_song(self.beats[2], 6, 20, 56))
        tracks = {t["id"]: t for t in db.all_tracks(self.conn)}
        html = build_report(str(self.dir / "suspect.mp3"), 20.0, "abc", matches, tracks)
        self.assertIn("beat2.wav", html)
        self.assertNotIn(str(self.dir), html)


if __name__ == "__main__":
    unittest.main()
