"""Build a self-contained HTML evidence report for a check."""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path


def _mmss(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    return f"{seconds // 60}:{seconds % 60:02d}"


def _bar(start: float, end: float, total: float, color: str) -> str:
    total = max(total, 0.001)
    left = max(0.0, min(100.0, start / total * 100))
    width = max(0.8, min(100.0 - left, (end - start) / total * 100))
    return (f'<div class="track"><div class="fill" style="left:{left:.2f}%;width:{width:.2f}%;'
            f'background:{color}"></div></div>')


def build_report(song_path: str, song_duration: float, song_sha: str, matches, tracks: dict) -> str:
    """tracks: {track_id: sqlite Row from the tracks table}."""
    e = html.escape
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    if matches:
        verdict = f"{len(matches)} registered beat{'s' if len(matches) > 1 else ''} found in this song"
        verdict_class = "hit"
    else:
        verdict, verdict_class = "No registered beats found in this song", "clear"

    cards = []
    for m in matches:
        t = tracks[m.track_id]
        loop_note = ('<br><span class="small">Your beat loops, so this section also matches its other repeats.</span>'
                     if m.loops else "")
        ots = (f'OpenTimestamps proof: <code>{e(Path(t["ots_path"]).name)}</code> (anchored on Bitcoin)' if t["ots_path"]
               else "No blockchain timestamp on file for this beat.")
        cards.append(f"""
<section class="card">
  <div class="head"><h2>{e(t["name"])}</h2><span class="badge">{e(m.confidence)} match</span></div>
  <table>
    <tr><th>In the suspect song</th><td>{_mmss(m.song_start)} to {_mmss(m.song_end)}</td></tr>
    <tr><th>Part of your beat used</th><td>{_mmss(m.beat_start)} to {_mmss(m.beat_end)}{loop_note}</td></tr>
    <tr><th>Speed</th><td>{e(m.speed_label)}</td></tr>
    <tr><th>Matching fingerprint points</th><td>{m.aligned:,} (signal is {m.ratio:,.0f}x above random chance)</td></tr>
    <tr><th>Coverage of that span</th><td>{m.coverage:.0%}</td></tr>
  </table>
  <p class="label">Suspect song ({_mmss(song_duration)})</p>{_bar(m.song_start, m.song_end, song_duration, "#d9534f")}
  <p class="label">Your beat ({_mmss(t["duration"])})</p>{_bar(m.beat_start, m.beat_end, t["duration"], "#2f8f6f")}
  <h3>Proof of creation</h3>
  <table>
    <tr><th>Registered</th><td>{e(t["registered_at"])}</td></tr>
    <tr><th>Original file</th><td><code>{e(Path(t["path"]).name)}</code></td></tr>
    <tr><th>SHA-256 of original file</th><td><code class="hash">{e(t["sha256"])}</code></td></tr>
  </table>
  <p class="small">{ots}</p>
</section>""")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>beat-guard report</title>
<style>
  :root {{ --bg:#f6f7f9; --card:#fff; --text:#14181f; --muted:#5b6476; --line:#e2e5eb; }}
  @media (prefers-color-scheme: dark) {{ :root {{ --bg:#0e1116; --card:#161b22; --text:#e8ebf0; --muted:#9aa4b2; --line:#2a313c; }} }}
  body {{ margin:0; background:var(--bg); color:var(--text); font:15px/1.5 system-ui,-apple-system,sans-serif; }}
  main {{ max-width:820px; margin:0 auto; padding:32px 16px 48px; }}
  h1 {{ margin:0 0 4px; font-size:26px; }} h2 {{ margin:0; font-size:19px; }} h3 {{ font-size:15px; margin:20px 0 6px; }}
  .verdict {{ padding:14px 16px; border-radius:10px; font-weight:600; margin:18px 0; }}
  .hit {{ background:#fbe9e8; color:#8a1f1a; }} .clear {{ background:#e5f2ee; color:#1f5e4a; }}
  @media (prefers-color-scheme: dark) {{ .hit {{ background:#3a1614; color:#f3b4b0; }} .clear {{ background:#15302a; color:#9fe0c8; }} }}
  .card {{ background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px; margin:14px 0; }}
  .head {{ display:flex; justify-content:space-between; align-items:center; gap:10px; flex-wrap:wrap; }}
  .badge {{ font-size:13px; font-weight:600; padding:3px 10px; border-radius:999px; background:#d9534f; color:#fff; }}
  table {{ border-collapse:collapse; width:100%; margin-top:10px; }}
  th {{ text-align:left; color:var(--muted); font-weight:500; padding:4px 12px 4px 0; width:42%; vertical-align:top; }}
  td {{ padding:4px 0; }} code {{ font-size:12.5px; }} .hash {{ word-break:break-all; }}
  .label {{ margin:14px 0 4px; font-size:13px; color:var(--muted); }}
  .track {{ position:relative; height:12px; background:var(--line); border-radius:6px; overflow:hidden; }}
  .fill {{ position:absolute; top:0; bottom:0; border-radius:6px; }}
  .meta, .small {{ color:var(--muted); font-size:13px; }}
  .note {{ margin-top:28px; font-size:13px; color:var(--muted); border-top:1px solid var(--line); padding-top:14px; }}
</style></head>
<body><main>
  <h1>beat-guard evidence report</h1>
  <div class="meta">Generated {now}</div>
  <div class="verdict {verdict_class}">{e(verdict)}</div>
  <table>
    <tr><th>Suspect song</th><td><code>{e(Path(song_path).name)}</code></td></tr>
    <tr><th>Length</th><td>{_mmss(song_duration)}</td></tr>
    <tr><th>SHA-256 of suspect file</th><td><code class="hash">{e(song_sha)}</code></td></tr>
  </table>
  {''.join(cards)}
  <p class="note">This report shows that the audio of a registered beat appears in the suspect recording, based on
  acoustic fingerprint matching. It is supporting evidence, not a legal determination. For legal protection,
  register your work with the U.S. Copyright Office and consult an entertainment attorney.</p>
</main></body></html>
"""
