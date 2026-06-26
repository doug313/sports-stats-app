#!/usr/bin/env python3
"""
Import Retrosheet play-by-play data into Postgres/SQLite.

Requirements:
  - chadwick CLI (cwevent, cwgame on PATH)
  - pip install pandas sqlalchemy psycopg2-binary requests

Usage:
  DATABASE_URL=sqlite:///./lahman.db python import_retrosheet.py --years 1960 1970
  DATABASE_URL=sqlite:///./lahman.db python import_retrosheet.py --from-year 1920 --to-year 2025
  DATABASE_URL=sqlite:///./lahman.db python import_retrosheet.py --all
  DATABASE_URL=sqlite:///./lahman.db python import_retrosheet.py --years 2026 --skip-biofile
"""

import os, sys, subprocess, zipfile, shutil, argparse
import tempfile, requests, pandas as pd
from pathlib import Path
from sqlalchemy import create_engine, text

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./lahman.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

engine = create_engine(DATABASE_URL)

RETROSHEET_BASE = "https://www.retrosheet.org/events"

# ── chadwick check ────────────────────────────────────────────────────────────

def check_chadwick():
    for cmd in ["cwevent", "cwgame"]:
        if shutil.which(cmd) is None:
            print(f"""
ERROR: '{cmd}' not found. Install chadwick:
  Windows: https://github.com/chadwickbureau/chadwick/releases
  macOS:   brew install chadwick-bureau/chadwick/chadwick
  Ubuntu:  sudo apt-get install chadwick
""")
            sys.exit(1)
    print("  OK  chadwick tools found")

# ── schema ────────────────────────────────────────────────────────────────────

def create_tables():
    with engine.connect() as conn:

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS retro_games (
                game_id         VARCHAR(20) PRIMARY KEY,
                date            DATE,
                year            INTEGER,
                away_team       VARCHAR(10),
                home_team       VARCHAR(10),
                away_score      INTEGER,
                home_score      INTEGER,
                away_hits       INTEGER,
                home_hits       INTEGER,
                attendance      INTEGER,
                duration_mins   INTEGER,
                winning_pitcher VARCHAR(20),
                losing_pitcher  VARCHAR(20),
                save_pitcher    VARCHAR(20)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS retro_events (
                game_id         VARCHAR(20),
                event_num       INTEGER,
                inning          INTEGER,
                batting_team    VARCHAR(4),
                outs            INTEGER,
                balls           INTEGER,
                strikes         INTEGER,
                pitch_sequence  TEXT,
                vis_score       INTEGER,
                home_score      INTEGER,
                batter_id       VARCHAR(20),
                batter_hand     VARCHAR(2),
                pitcher_id      VARCHAR(20),
                pitcher_hand    VARCHAR(2),
                runner_1b       VARCHAR(20),
                runner_2b       VARCHAR(20),
                runner_3b       VARCHAR(20),
                play_text       TEXT,
                event_cd        INTEGER,
                batter_event_fl VARCHAR(2),
                ab_flag         VARCHAR(2),
                hit_value       INTEGER,
                sh_flag         VARCHAR(2),
                sf_flag         VARCHAR(2),
                outs_on_play    INTEGER,
                dp_flag         VARCHAR(2),
                tp_flag         VARCHAR(2),
                rbi             INTEGER,
                wp_flag         VARCHAR(2),
                pb_flag         VARCHAR(2),
                fielded_by      INTEGER,
                num_errors      INTEGER,
                batter_dest     INTEGER,
                runner_1b_dest  INTEGER,
                runner_2b_dest  INTEGER,
                runner_3b_dest  INTEGER,
                runs_scored     INTEGER
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS retro_people (
                retro_id   VARCHAR(20) PRIMARY KEY,
                first_name TEXT,
                last_name  TEXT,
                full_name  TEXT
            )
        """))

        for idx in [
            "CREATE INDEX IF NOT EXISTS idx_retro_games_year     ON retro_games(year)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_home     ON retro_games(home_team)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_away     ON retro_games(away_team)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_date     ON retro_games(date)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_game       ON retro_events(game_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_batter     ON retro_events(batter_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_pitcher    ON retro_events(pitcher_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_event_cd   ON retro_events(event_cd)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_inning     ON retro_events(inning)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_hit        ON retro_events(hit_value)",
            "CREATE INDEX IF NOT EXISTS idx_retro_people_id      ON retro_people(retro_id)",
        ]:
            conn.execute(text(idx))

        conn.commit()
    print("  OK  Tables and indexes created")

# ── biofile ───────────────────────────────────────────────────────────────────

def import_biofile():
    """Download Retrosheet BIOFILE and load player name lookup."""
    print("  Downloading BIOFILE.TXT...")
    try:
        r = requests.get(
            "https://www.retrosheet.org/BIOFILE.TXT",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=60
        )
        r.raise_for_status()
    except Exception as e:
        print(f"  WARN BIOFILE download failed: {e}")
        return

    from io import StringIO
    df = pd.read_csv(StringIO(r.text), quotechar='"', skipinitialspace=True)

    people = pd.DataFrame({
        "retro_id":   df["PLAYERID"].str.strip(),
        "first_name": df["FIRST"].str.strip(),
        "last_name":  df["LAST"].str.strip(),
        "full_name":  df["FIRST"].str.strip() + " " + df["LAST"].str.strip(),
    })
    people = people.dropna(subset=["retro_id"])
    people = people.drop_duplicates(subset=["retro_id"])

    with engine.connect() as conn:
        conn.execute(text("DELETE FROM retro_people"))
        conn.commit()

    is_sqlite = DATABASE_URL.startswith("sqlite")
    chunk = 500 if is_sqlite else 5000
    people.to_sql("retro_people", engine, if_exists="append",
                  index=False, chunksize=chunk)
    print(f"  OK  {len(people):,} rows → retro_people")

# ── download ──────────────────────────────────────────────────────────────────

def download_year(year: int, tmpdir: Path):
    url  = f"{RETROSHEET_BASE}/{year}eve.zip"
    dest = tmpdir / f"{year}eve.zip"
    out  = tmpdir / str(year)
    out.mkdir(exist_ok=True)

    print(f"  Downloading {year}...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=60,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 404:
            print("not available (404)")
            return None
        r.raise_for_status()
        dest.write_bytes(r.content)
        with zipfile.ZipFile(dest) as z:
            z.extractall(out)
        print(f"OK ({dest.stat().st_size // 1024}KB)")
        return out
    except Exception as e:
        print(f"FAILED: {e}")
        return None

# ── parse games ───────────────────────────────────────────────────────────────

def parse_games(event_dir: Path, year: int) -> pd.DataFrame:
    """
    cwgame field mapping (fields requested: 0,7,8,18,32,34,35,36,37,42,43,44):
      col[0]  = field 0  = game_id
      col[1]  = field 7  = away_team
      col[2]  = field 8  = home_team
      col[3]  = field 18 = attendance
      col[4]  = field 32 = duration_mins
      col[5]  = field 34 = away_score
      col[6]  = field 35 = home_score
      col[7]  = field 36 = away_hits
      col[8]  = field 37 = home_hits
      col[9]  = field 42 = winning_pitcher
      col[10] = field 43 = losing_pitcher
      col[11] = field 44 = save_pitcher
    """
    eve_files = [f for f in event_dir.iterdir()
                 if f.suffix.upper() in ('.EVA', '.EVN', '.EVE')]
    if not eve_files:
        return pd.DataFrame()

    rows = []
    for evf in eve_files:
        try:
            result = subprocess.run(
                ["cwgame", "-y", str(year),
                 "-f", "0,7,8,18,32,34,35,36,37,42,43,44",
                 str(evf)],
                capture_output=True, text=True, timeout=120,
                cwd=str(event_dir)
            )
            if result.returncode == 0 and result.stdout.strip():
                from io import StringIO
                df = pd.read_csv(StringIO(result.stdout), header=None)
                rows.append(df)
        except Exception as e:
            print(f"    WARN cwgame {evf.name}: {e}")
            continue

    if not rows:
        return pd.DataFrame()

    combined = pd.concat(rows, ignore_index=True)
    try:
        games = pd.DataFrame({
            "game_id":         combined[0],
            "date":            pd.to_datetime(
                                   combined[0].str[3:11],
                                   format="%Y%m%d", errors="coerce"),
            "year":            year,
            "away_team":       combined[1],
            "home_team":       combined[2],
            "attendance":      pd.to_numeric(combined[3], errors="coerce"),
            "duration_mins":   pd.to_numeric(combined[4], errors="coerce"),
            "away_score":      pd.to_numeric(combined[5], errors="coerce"),
            "home_score":      pd.to_numeric(combined[6], errors="coerce"),
            "away_hits":       pd.to_numeric(combined[7], errors="coerce"),
            "home_hits":       pd.to_numeric(combined[8], errors="coerce"),
            "winning_pitcher": combined[9],
            "losing_pitcher":  combined[10],
            "save_pitcher":    combined[11],
        })
        games = games.drop_duplicates(subset=["game_id"])
        return games.dropna(subset=["game_id"])
    except Exception as e:
        print(f"    WARN game parse: {e}")
        return pd.DataFrame()

# ── parse events ──────────────────────────────────────────────────────────────

def parse_events(event_dir: Path, year: int) -> pd.DataFrame:
    """
    cwevent field mapping — verified against cwevent 0.10.0 output.

    Basic fields (-f):
      0,2,3,4,5,6,7,8,9,10,11,14,15,26,27,28,29,34,35,36,37,38,39,40,41,42,43,44,45,46,51,58,59,60,61

    Extended fields (-x):
      45 = runs scored on play

    col[0]  = field 0   = game_id
    col[1]  = field 2   = inning
    col[2]  = field 3   = batting_team (0=visitor 1=home)
    col[3]  = field 4   = outs
    col[4]  = field 5   = balls
    col[5]  = field 6   = strikes
    col[6]  = field 7   = pitch_sequence
    col[7]  = field 8   = vis_score (score at time of play)
    col[8]  = field 9   = home_score (score at time of play)
    col[9]  = field 10  = batter_id
    col[10] = field 11  = batter_hand (L/R/B)
    col[11] = field 14  = pitcher_id
    col[12] = field 15  = pitcher_hand (L/R)
    col[13] = field 26  = runner_1b (id of runner on 1st, empty if none)
    col[14] = field 27  = runner_2b
    col[15] = field 28  = runner_3b
    col[16] = field 29  = play_text (e.g. "K", "S8", "HR", "W")
    col[17] = field 34  = event_cd (2=out,3=K,14=BB,20=1B,21=2B,22=3B,23=HR)
    col[18] = field 35  = batter_event_fl (T/F did plate appearance end)
    col[19] = field 36  = ab_flag (T/F official at-bat)
    col[20] = field 37  = hit_value (0=none,1=1B,2=2B,3=3B,4=HR)
    col[21] = field 38  = sh_flag (sacrifice hit)
    col[22] = field 39  = sf_flag (sacrifice fly)
    col[23] = field 40  = outs_on_play
    col[24] = field 41  = dp_flag (double play)
    col[25] = field 42  = tp_flag (triple play)
    col[26] = field 43  = rbi
    col[27] = field 44  = wp_flag (wild pitch)
    col[28] = field 45  = pb_flag (passed ball)
    col[29] = field 46  = fielded_by (position 1-9)
    col[30] = field 51  = num_errors
    col[31] = field 58  = batter_dest (0=out,1=1B,2=2B,3=3B,4=scored,5=unearned,6=team unearned)
    col[32] = field 59  = runner_1b_dest
    col[33] = field 60  = runner_2b_dest
    col[34] = field 61  = runner_3b_dest
    col[35] = x-field 45 = runs_scored (from extended fields)
    """
    eve_files = [f for f in event_dir.iterdir()
                 if f.suffix.upper() in ('.EVA', '.EVN', '.EVE')]
    if not eve_files:
        return pd.DataFrame()

    rows = []
    for evf in eve_files:
        try:
            result = subprocess.run(
                ["cwevent", "-y", str(year),
                 "-f", "0,2,3,4,5,6,7,8,9,10,11,14,15,26,27,28,29,34,35,36,37,38,39,40,41,42,43,44,45,46,51,58,59,60,61",
                 "-x", "45",
                 str(evf)],
                capture_output=True, text=True, timeout=300,
                cwd=str(event_dir)
            )
            if result.returncode == 0 and result.stdout.strip():
                from io import StringIO
                df = pd.read_csv(StringIO(result.stdout), header=None)
                rows.append(df)
        except Exception as e:
            print(f"    WARN cwevent {evf.name}: {e}")
            continue

    if not rows:
        return pd.DataFrame()

    combined = pd.concat(rows, ignore_index=True)
    try:
        events = pd.DataFrame({
            "game_id":          combined[0],
            "inning":           pd.to_numeric(combined[1],  errors="coerce"),
            "batting_team":     combined[2],
            "outs":             pd.to_numeric(combined[3],  errors="coerce"),
            "balls":            pd.to_numeric(combined[4],  errors="coerce"),
            "strikes":          pd.to_numeric(combined[5],  errors="coerce"),
            "pitch_sequence":   combined[6],
            "vis_score":        pd.to_numeric(combined[7],  errors="coerce"),
            "home_score":       pd.to_numeric(combined[8],  errors="coerce"),
            "batter_id":        combined[9],
            "batter_hand":      combined[10],
            "pitcher_id":       combined[11],
            "pitcher_hand":     combined[12],
            "runner_1b":        combined[13],
            "runner_2b":        combined[14],
            "runner_3b":        combined[15],
            "play_text":        combined[16],
            "event_cd":         pd.to_numeric(combined[17], errors="coerce"),
            "batter_event_fl":  combined[18],
            "ab_flag":          combined[19],
            "hit_value":        pd.to_numeric(combined[20], errors="coerce"),
            "sh_flag":          combined[21],
            "sf_flag":          combined[22],
            "outs_on_play":     pd.to_numeric(combined[23], errors="coerce"),
            "dp_flag":          combined[24],
            "tp_flag":          combined[25],
            "rbi":              pd.to_numeric(combined[26], errors="coerce"),
            "wp_flag":          combined[27],
            "pb_flag":          combined[28],
            "fielded_by":       pd.to_numeric(combined[29], errors="coerce"),
            "num_errors":       pd.to_numeric(combined[30], errors="coerce"),
            "batter_dest":      pd.to_numeric(combined[31], errors="coerce"),
            "runner_1b_dest":   pd.to_numeric(combined[32], errors="coerce"),
            "runner_2b_dest":   pd.to_numeric(combined[33], errors="coerce"),
            "runner_3b_dest":   pd.to_numeric(combined[34], errors="coerce"),
            "runs_scored":      pd.to_numeric(combined[35], errors="coerce"),
        })
        # Derive sequential event number per game
        events["event_num"] = events.groupby("game_id").cumcount() + 1
        return events.dropna(subset=["game_id"])
    except Exception as e:
        import traceback
        print(f"    WARN event parse: {e}")
        traceback.print_exc()
        return pd.DataFrame()

# ── load to DB ────────────────────────────────────────────────────────────────

def load_df(df: pd.DataFrame, table: str, year: int):
    if df.empty:
        print(f"    SKIP {table} — no data")
        return

    is_sqlite = DATABASE_URL.startswith("sqlite")
    chunk = 50 if is_sqlite else 5000

    with engine.connect() as conn:
        if table == "retro_events":
            conn.execute(text("""
                DELETE FROM retro_events WHERE game_id IN (
                    SELECT game_id FROM retro_games WHERE year = :y
                )"""), {"y": year})
        elif "year" in df.columns:
            conn.execute(text(f"DELETE FROM {table} WHERE year = :y"),
                         {"y": year})
        conn.commit()

    if table == "retro_events":
        before = len(df)
        df = df.drop_duplicates(subset=["game_id", "event_num"])
        dupes = before - len(df)
        if dupes > 0:
            print(f"    INFO dropped {dupes:,} duplicate events")

    if table == "retro_games":
        df = df.drop_duplicates(subset=["game_id"])

    df = df.where(pd.notnull(df), None)
    df.to_sql(table, engine, if_exists="append", index=False, chunksize=chunk)
    print(f"    OK  {len(df):,} rows → {table}")

# ── import one year ───────────────────────────────────────────────────────────

def import_year(year: int, tmpdir: Path):
    print(f"\n── {year} ──────────────────────────────────────")
    event_dir = download_year(year, tmpdir)
    if not event_dir:
        return

    print("  Parsing games...")
    games = parse_games(event_dir, year)
    load_df(games, "retro_games", year)

    print("  Parsing play-by-play events...")
    events = parse_events(event_dir, year)
    load_df(events, "retro_events", year)

    print(f"  Done — {year}")

# ── main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Retrosheet data")
    parser.add_argument("--years",        nargs="+", type=int,
                        help="Specific years e.g. 1960 1970 1980")
    parser.add_argument("--from-year",    type=int, default=1950,
                        help="Start year for range")
    parser.add_argument("--to-year",      type=int, default=2025,
                        help="End year for range")
    parser.add_argument("--all",          action="store_true",
                        help="Import everything 1910-2025")
    parser.add_argument("--skip-biofile", action="store_true",
                        help="Skip downloading BIOFILE player names")
    args = parser.parse_args()

    print("Checking chadwick tools...")
    check_chadwick()

    print("Creating tables...")
    create_tables()

    if not args.skip_biofile:
        print("Importing player names...")
        import_biofile()

    if args.years:
        years = args.years
    elif args.all:
        years = list(range(1910, 2026))
    else:
        years = list(range(args.from_year, args.to_year + 1))

    print(f"\nImporting {len(years)} year(s): {years[0]}–{years[-1]}")
    print("This may take a while for large ranges...\n")

    with tempfile.TemporaryDirectory() as tmpdir:
        for year in years:
            import_year(year, Path(tmpdir))

    print("\n✓ Retrosheet import complete.")
    print("\nNOTE: Retrosheet data attribution required:")
    print("  'The information used here was obtained free of charge from and is")
    print("   copyrighted by Retrosheet. www.retrosheet.org'")