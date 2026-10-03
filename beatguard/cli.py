"""Command line: python -m beatguard register | list | check | verify"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import db, proof
from .fingerprint import SAMPLE_RATE, fingerprint, load_audio
from .match import check_audio
from .report import build_report


def _mmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def cmd_register(args, conn):
    added = 0
    for raw in args.files:
        path = str(Path(raw).expanduser().resolve())
        if not Path(path).is_file():
            print(f"  ✗ {raw}: file not found")
            continue
        sha = proof.sha256_file(path)
        existing = db.find_by_sha(conn, sha)
        if existing:
            print(f"  • {Path(path).name}: already registered as '{existing['name']}' on {existing['registered_at']}")
            continue
        try:
            hashes, duration = fingerprint(path)
        except Exception as e:
            print(f"  ✗ {Path(path).name}: couldn't read audio ({e})")
            continue
        if len(hashes) < 100:
            print(f"  ✗ {Path(path).name}: too quiet or too short to fingerprint")
            continue
        name = args.name if (args.name and len(args.files) == 1) else Path(path).stem
        registered_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        ots_path = proof.stamp(path) if not args.no_timestamp else None
        db.add_track(conn, name, path, sha, duration, registered_at, hashes, ots_path)
        added += 1
        stamp_note = "blockchain timestamp requested" if ots_path else "no blockchain timestamp"
        print(f"  ✓ {name}  ({_mmss(duration)}, {len(hashes):,} fingerprint points, {stamp_note})")
    if added and not proof.ots_available() and not args.no_timestamp:
        print("\n  Tip: `pip install opentimestamps-client` to also anchor each beat's hash on Bitcoin.")


def cmd_list(args, conn):
    tracks = db.all_tracks(conn)
    if not tracks:
        print("  No beats registered yet. Run: python -m beatguard register your_beat.wav")
        return
    for t in tracks:
        mark = "⛓" if t["ots_path"] else " "
        print(f"  {mark} {t['name']:<30} {_mmss(t['duration']):>6}   registered {t['registered_at']}")


def cmd_check(args, conn):
    path = str(Path(args.song).expanduser().resolve())
    if not Path(path).is_file():
        sys.exit(f"Error: {args.song} not found")
    if not db.all_tracks(conn):
        sys.exit("Error: no beats registered yet. Run `register` first.")
    audio = load_audio(path)
    duration = len(audio) / SAMPLE_RATE
    print(f"  Checking {Path(path).name} ({_mmss(duration)})...")
    matches = check_audio(conn, audio, max_speed_change=args.max_speed)
    tracks = {t["id"]: t for t in db.all_tracks(conn)}

    if not matches:
        print("\n  ✅ No registered beats found in this song.")
    for m in matches:
        t = tracks[m.track_id]
        print(f"\n  🚨 MATCH: '{t['name']}' ({m.confidence})")
        print(f"     In the song:    {_mmss(m.song_start)} to {_mmss(m.song_end)}")
        loop = "  (your beat loops; matches its repeats too)" if m.loops else ""
        print(f"     Your beat used: {_mmss(m.beat_start)} to {_mmss(m.beat_end)}{loop}")
        print(f"     Speed:          {m.speed_label}")
        print(f"     Evidence:       {m.aligned:,} matching points, {m.coverage:.0%} coverage")

    if args.report:
        out = Path(args.report).expanduser()
        out.write_text(build_report(path, duration, proof.sha256_file(path), matches, tracks), encoding="utf-8")
        print(f"\n  Report saved: {out}")
    sys.exit(2 if matches else 0)


def cmd_verify(args, conn):
    path = str(Path(args.file).expanduser().resolve())
    sha = proof.sha256_file(path)
    t = db.find_by_sha(conn, sha)
    if not t:
        sys.exit("  ✗ This exact file is not registered (even a re-export changes the hash).")
    print(f"  ✓ '{t['name']}' registered {t['registered_at']}")
    print(f"    SHA-256: {sha}")
    if t["ots_path"]:
        ok, msg = proof.verify_ots(t["ots_path"])
        print(f"    Blockchain timestamp: {'✓ ' if ok else ''}{msg}")
        if not ok:
            print("    (New timestamps take a few hours to confirm on Bitcoin. Try again later.)")


def main(argv=None):
    p = argparse.ArgumentParser(prog="beatguard", description="Fingerprint your beats and catch them in other songs.")
    p.add_argument("--db", default=str(db.DEFAULT_DB), help="library file (default: ~/.beatguard/library.db)")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("register", help="Fingerprint and timestamp your beats")
    r.add_argument("files", nargs="+")
    r.add_argument("--name", help="display name (single file only)")
    r.add_argument("--no-timestamp", action="store_true", help="skip the OpenTimestamps proof")

    sub.add_parser("list", help="Show registered beats")

    c = sub.add_parser("check", help="Check a song for your beats")
    c.add_argument("song")
    c.add_argument("--report", help="save an HTML evidence report to this path")
    c.add_argument("--max-speed", type=float, default=6.0, help="max speed change to search, in %% (default 6)")

    v = sub.add_parser("verify", help="Confirm a file is registered and check its timestamp")
    v.add_argument("file")

    args = p.parse_args(argv)
    conn = db.connect(args.db)
    {"register": cmd_register, "list": cmd_list, "check": cmd_check, "verify": cmd_verify}[args.cmd](args, conn)


if __name__ == "__main__":
    main()
