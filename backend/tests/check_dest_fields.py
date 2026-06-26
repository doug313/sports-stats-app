import subprocess, zipfile, tempfile, requests, pandas as pd
from pathlib import Path
from io import StringIO

YEAR = 2024
FIELDS_F = "0,2,3,4,5,6,7,8,9,10,11,14,15,26,27,28,29,34,35,36,37,38,39,40,41,42,43,44,45,46,51,58,59,60,61"
FIELDS_X = "45"

EXPECTED_NAMES = [
    "game_id","inning","batting_team","outs","balls","strikes",
    "pitch_sequence","vis_score","home_score","batter_id","batter_hand",
    "pitcher_id","pitcher_hand","runner_1b","runner_2b","runner_3b",
    "play_text","event_cd","batter_event_fl","ab_flag","hit_value",
    "sh_flag","sf_flag","outs_on_play","dp_flag","tp_flag","rbi",
    "wp_flag","pb_flag","fielded_by","num_errors","batter_dest",
    "runner_1b_dest","runner_2b_dest","runner_3b_dest","runs_scored",
]

url = f"https://www.retrosheet.org/events/{YEAR}eve.zip"
print("Downloading...")
r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    zpath = tmp / "test.zip"
    zpath.write_bytes(r.content)
    out_dir = tmp / str(YEAR)
    out_dir.mkdir()
    with zipfile.ZipFile(zpath) as z:
        z.extractall(out_dir)

    evf = next(f for f in out_dir.iterdir() if f.suffix.upper() == '.EVA')

    result = subprocess.run(
        ["cwevent", "-y", str(YEAR),
         "-f", FIELDS_F, "-x", FIELDS_X, str(evf)],
        capture_output=True, text=True, timeout=120,
        cwd=str(out_dir)
    )

    df = pd.read_csv(StringIO(result.stdout), header=None)
    print(f"Columns: {len(df.columns)} (expected {len(EXPECTED_NAMES)})")
    print(f"Match:   {'YES — READY TO IMPORT' if len(df.columns) == len(EXPECTED_NAMES) else 'NO — FIX NEEDED'}")
    print()

    first = df.iloc[0].tolist()
    for i, name in enumerate(EXPECTED_NAMES):
        val = first[i] if i < len(first) else "MISSING"
        print(f"  col[{i:2}] {name:20} = {val}")

    print(f"\nKey checks:")
    print(f"  event_cd range:   {pd.to_numeric(df[17],errors='coerce').min():.0f}–{pd.to_numeric(df[17],errors='coerce').max():.0f}")
    print(f"  hit_value unique: {sorted(pd.to_numeric(df[20],errors='coerce').dropna().unique().astype(int).tolist())}")
    print(f"  runs_scored max:  {pd.to_numeric(df[35],errors='coerce').max():.0f}")
    print(f"  batter_dest max:  {pd.to_numeric(df[31],errors='coerce').max():.0f}")