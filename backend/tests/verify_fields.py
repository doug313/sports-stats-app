"""
Verify cwevent field list — dynamically checks actual output.
"""

import subprocess, zipfile, tempfile, requests, pandas as pd
from pathlib import Path
from io import StringIO

YEAR = 2024
FIELDS = "0,2,3,4,5,6,7,8,9,10,11,14,15,26,27,28,29,34,35,36,37,38,39,40,41,42,43,44,45,46,51,58,59,60,61"

# What we WANT each column to be — we'll verify by checking sample values
NAMES = [
    "game_id", "inning", "batting_team", "outs", "balls", "strikes",
    "pitch_sequence", "vis_score", "home_score", "batter_id", "batter_hand",
    "pitcher_id", "pitcher_hand", "runner_1b", "runner_2b", "runner_3b",
    "play_text", "event_cd", "batter_event_fl", "ab_flag", "hit_value",
    "sh_flag", "sf_flag", "outs_on_play", "dp_flag", "tp_flag", "rbi",
    "wp_flag", "pb_flag", "runs_scored", "fielded_by", "num_errors",
    "batter_dest", "runner_1b_dest", "runner_2b_dest", "runner_3b_dest",
]

field_list = FIELDS.split(',')
print(f"Fields requested: {len(field_list)}")
print(f"Names defined:    {len(NAMES)}")

print(f"\nDownloading {YEAR}...")
url = f"https://www.retrosheet.org/events/{YEAR}eve.zip"
r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    zpath = tmp / "test.zip"
    zpath.write_bytes(r.content)
    out_dir = tmp / str(YEAR)
    out_dir.mkdir()
    with zipfile.ZipFile(zpath) as z:
        z.extractall(out_dir)

    eve_files = [f for f in out_dir.iterdir()
                 if f.suffix.upper() in ('.EVA', '.EVN', '.EVE')]

    all_rows = []
    for evf in sorted(eve_files):
        result = subprocess.run(
            ["cwevent", "-y", str(YEAR), "-f", FIELDS, str(evf)],
            capture_output=True, text=True, timeout=300,
            cwd=str(out_dir)
        )
        if result.returncode == 0 and result.stdout.strip():
            df = pd.read_csv(StringIO(result.stdout), header=None)
            all_rows.append(df)

    combined = pd.concat(all_rows, ignore_index=True)
    actual_cols = len(combined.columns)

    print(f"Actual columns:   {actual_cols}")
    print(f"\nAll columns with sample values:")
    first = combined.iloc[0].tolist()
    for i in range(actual_cols):
        name = NAMES[i] if i < len(NAMES) else f"UNKNOWN_{i}"
        null_pct = (combined[i].isna().sum() / len(combined)) * 100
        print(f"  col[{i:2}] {name:20} null={null_pct:4.1f}%  sample={str(first[i])[:20]}")

    print(f"\nKey sanity checks:")
    ev_cd  = pd.to_numeric(combined[17], errors="coerce")
    print(f"  event_cd  (col17): nulls={ev_cd.isna().sum():,}  range={ev_cd.min():.0f}–{ev_cd.max():.0f}")
    hv     = pd.to_numeric(combined[20], errors="coerce")
    print(f"  hit_value (col20): unique={sorted(hv.dropna().unique().astype(int).tolist())}")
    rbi    = pd.to_numeric(combined[26], errors="coerce")
    print(f"  rbi       (col26): max={rbi.max():.0f}")

    # Dedupe check
    game_col = combined[0]
    # Assign sequential event_num per game
    combined["event_num"] = combined.groupby(0).cumcount() + 1
    print(f"\n  event_num derived: min={combined['event_num'].min()}  max={combined['event_num'].max()}")
    print(f"  Total rows: {len(combined):,}")
    print(f"\nREADY TO IMPORT — update NAMES list if any columns look wrong above")