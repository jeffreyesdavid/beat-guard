# beat-guard 🎛️🛡️

**Prove your beat is yours, and catch it when someone else uses it.**

🌐 **[Project page](https://jeffreyesdavid.github.io/beat-guard/)** · ☕ **[Buy me a coffee](https://buymeacoffee.com/jeffreyesdavid)**

Bigger artists taking beats from small producers happens all the time, and the producer usually has no proof and no way to show *where* their beat was used. beat-guard fingerprints your beats the way Shazam does, timestamps them on the Bitcoin blockchain, and then scans any song to find your beat inside it, even with vocals rapped over it.

```
$ python -m beatguard check industry_song.mp3 --report report.html

  🚨 MATCH: 'cold_case' (Very strong)
     In the song:    0:08 to 0:38
     Your beat used: 0:11 to 0:40
     Speed:          3.0% faster (likely sped up/slowed to disguise it)
     Evidence:       6,781 matching points, 100% coverage
```

## Why I built this

I make music ([my SoundCloud](https://soundcloud.com/jeffreyesdavid)). Bigger artists taking beats from smaller, up-and-coming producers happens a lot, and the producer usually can't prove anything. I wanted a tool that gives producers like me real evidence: proof of when we made a beat, and proof of exactly where it shows up in someone else's song.

## What it does

| Step | Command | What happens |
|---|---|---|
| **Register** | `register beat.wav` | Fingerprints the beat, records the file's SHA-256 hash, and (optionally) anchors that hash on Bitcoin with [OpenTimestamps](https://opentimestamps.org): proof you had this exact file on this date |
| **Check** | `check song.mp3` | Finds which of your beats appear in a song, where they start and end, which part of your beat was used, and whether it was sped up or slowed down |
| **Report** | `check song.mp3 --report r.html` | Creates a clean evidence report you can share with a lawyer, a label, or attach to a copyright claim |
| **Verify** | `verify beat.wav` | Confirms a file is registered and checks its blockchain timestamp |

### What it catches
- Your beat with **vocals on top**, even when the vocals are 3x louder than the beat
- **Short samples**, down to about 5 seconds
- Beats **sped up or slowed down** by up to ±6% (a common way to disguise a stolen beat). It reports the exact speed change, which is evidence on its own.
- Songs that went through **MP3 compression**, as every release does

### What it doesn't catch (yet)
- A melody **re-played from scratch** on different instruments (that's a composition question, not a recording match)
- **Pitch changed without changing tempo**, or tempo changed without pitch (independent time-stretching)

## How it works

1. **Spectrogram:** the audio is turned into a map of which frequencies are loud at each moment.
2. **Constellation:** only the strongest peaks are kept. They're the parts that survive vocals, compression and noise.
3. **Hashes:** peaks are paired up; each pair (frequency 1, frequency 2, time gap) becomes a fingerprint hash.
4. **Alignment:** a song containing your beat shares thousands of hashes with it, **all lined up at the same time offset**. Random songs share a few scattered hashes at random offsets. That difference is what proves a match.
5. **Speed search:** the song is re-checked at small speed changes (0.5% steps) to undo a sped-up or slowed version.

Beats loop, so a copied section can line up with more than one repeat of your loop. beat-guard combines those and tells you when it happened.

## Install

Requires Python 3.9+.

```bash
git clone https://github.com/jeffreyesdavid/beat-guard.git
cd beat-guard
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Optional, to timestamp your beats on Bitcoin:

```bash
pip install opentimestamps-client
```

## Usage

```bash
# Register your beats (export from your DAW as WAV or MP3)
python -m beatguard register ~/Music/beats/*.wav

# See what's registered
python -m beatguard list

# Check a song you're suspicious about
python -m beatguard check suspect_song.mp3 --report report.html

# Later: confirm the blockchain timestamp went through (takes a few hours)
python -m beatguard verify ~/Music/beats/night_drive.wav
```

Your library is stored locally at `~/.beatguard/library.db`. Nothing is uploaded anywhere except the file's hash (never the audio) when you use OpenTimestamps.

> **Tip:** register the **exact file you send out** (to artists, BeatStars, YouTube). The SHA-256 hash proves that specific file existed at that time; a re-export creates a different hash.

### Try it without your own beats

```bash
python tests/make_demo.py
python -m beatguard --db demo/demo.db register demo/beat_*.wav
python -m beatguard --db demo/demo.db check demo/industry_song.mp3 --report demo/report.html
```

## Tests

```bash
python -m unittest discover -s tests -t .
```

10 end-to-end tests built on generated beats and speech-like "vocals". Every suspect song goes through MP3 compression first. They cover vocals over the beat, loud vocals, 5-second samples, quiet beats, sped-up and slowed beats, and unrelated songs that must **not** match.

## Project layout

```
beatguard/
  fingerprint.py   # spectrogram peaks -> hashes
  match.py         # offset alignment, loop handling, speed search
  db.py            # local SQLite library
  proof.py         # SHA-256 + OpenTimestamps
  report.py        # HTML evidence report
  cli.py           # command line
tests/
  synth.py         # generates test beats and vocals
  test_beatguard.py
  make_demo.py
```

## Roadmap
- [ ] Pitch-shift and time-stretch detection, handled independently
- [ ] Check a YouTube/SoundCloud link directly
- [ ] Batch-scan a folder or playlist of new releases against your catalog
- [ ] Simple web interface for producers who don't use the terminal

## Disclaimer

beat-guard provides supporting evidence based on acoustic fingerprint matching. It is not a legal determination. To protect your work legally, register it with the [U.S. Copyright Office](https://www.copyright.gov/registration/) and talk to an entertainment attorney.

## License

MIT
