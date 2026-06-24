#!/usr/bin/env python3
"""
Import Retrosheet play-by-play data into Postgres.

Requirements:
  - chadwick CLI tool (install instructions printed below)
  - pip install pandas sqlalchemy psycopg2-binary requests tqdm

Usage:
  # Import specific years (recommended to start — each year is ~50-100MB parsed)
  DATABASE_URL=postgresql://... python import_retrosheet.py --years 2000 2001 2002

  # Import a range
  DATABASE_URL=postgresql://... python import_retrosheet.py --from-year 1990 --to-year 2023

  # Import everything (1910–present, will take 30-60 min)
  DATABASE_URL=postgresql://... python import_retrosheet.py --all

Retrosheet data is free but requires attribution:
  "The information used here was obtained free of charge from and is
   copyrighted by Retrosheet. Interested parties may contact Retrosheet
   at www.retrosheet.org"
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
    """Chadwick converts Retrosheet .EVA/.EVN files to CSV."""
    for cmd in ["cwevent", "cwgame", "cwsub"]:
        if shutil.which(cmd) is None:
            print(f"""
ERROR: '{cmd}' not found. Install chadwick first:

  macOS:   brew install chadwick-bureau/chadwick/chadwick
  Ubuntu:  sudo apt-get install chadwick
  Windows: download from https://github.com/chadwickbureau/chadwick/releases
           and add to your PATH

Then re-run this script.
""")
            sys.exit(1)
    print("  OK  chadwick tools found")

# ── schema creation ───────────────────────────────────────────────────────────

def create_tables():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS retro_games (
                game_id         VARCHAR(20) PRIMARY KEY,
                date            DATE,
                year            INTEGER,
                home_team       VARCHAR(10),
                away_team       VARCHAR(10),
                home_score      INTEGER,
                away_score      INTEGER,
                innings         INTEGER,
                park_id         VARCHAR(10),
                attendance      INTEGER,
                duration_mins   INTEGER,
                winning_pitcher VARCHAR(20),
                losing_pitcher  VARCHAR(20),
                save_pitcher    VARCHAR(20),
                ump_home        VARCHAR(20),
                ump_1b          VARCHAR(20),
                ump_2b          VARCHAR(20),
                ump_3b          VARCHAR(20)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS retro_batting (
                game_id         VARCHAR(20),
                player_id       VARCHAR(20),
                team            VARCHAR(10),
                home_away       CHAR(1),
                batting_order   INTEGER,
                ab              INTEGER,
                r               INTEGER,
                h               INTEGER,
                doubles         INTEGER,
                triples         INTEGER,
                hr              INTEGER,
                rbi             INTEGER,
                bb              INTEGER,
                so              INTEGER,
                sb              INTEGER,
                cs              INTEGER,
                hbp             INTEGER,
                sh              INTEGER,
                sf              INTEGER,
                gdp             INTEGER,
                PRIMARY KEY (game_id, player_id, batting_order)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS retro_pitching (
                game_id         VARCHAR(20),
                player_id       VARCHAR(20),
                team            VARCHAR(10),
                home_away       CHAR(1),
                seq             INTEGER,
                outs            INTEGER,
                bf              INTEGER,
                h               INTEGER,
                doubles         INTEGER,
                triples         INTEGER,
                hr              INTEGER,
                r               INTEGER,
                er              INTEGER,
                bb              INTEGER,
                ibb             INTEGER,
                so              INTEGER,
                hbp             INTEGER,
                wp              INTEGER,
                bk              INTEGER,
                win             BOOLEAN,
                loss            BOOLEAN,
                save            BOOLEAN,
                PRIMARY KEY (game_id, player_id, seq)
            )
        """))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS retro_events (
                game_id         VARCHAR(20),
                event_num       INTEGER,
                inning          INTEGER,
                batting_team    CHAR(1),
                outs            INTEGER,
                balls           INTEGER,
                strikes         INTEGER,
                batter_id       VARCHAR(20),
                pitcher_id      VARCHAR(20),
                event_type      INTEGER,
                event_cd        INTEGER,
                hit_value       INTEGER,
                rbi             INTEGER,
                runs_scored     INTEGER,
                play_text       TEXT,
                description     TEXT,
                PRIMARY KEY (game_id, event_num)
            )
        """))

        # Indexes for fast querying
        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_retro_games_date     ON retro_games(date)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_year     ON retro_games(year)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_home     ON retro_games(home_team)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_away     ON retro_games(away_team)",
            "CREATE INDEX IF NOT EXISTS idx_retro_bat_player     ON retro_batting(player_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_bat_game       ON retro_batting(game_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_pit_player     ON retro_pitching(player_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_pit_game       ON retro_pitching(game_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_game       ON retro_events(game_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_batter     ON retro_events(batter_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_pitcher    ON retro_events(pitcher_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_type       ON retro_events(event_cd)",
        ]:
            conn.execute(text(idx_sql))

        conn.commit()
    print("  OK  Tables and indexes created")

# ── download year ─────────────────────────────────────────────────────────────

def download_year(year: int, tmpdir: Path) -> Path | None:
    """Download and unzip one year of Retrosheet event files."""
    url = f"{RETROSHEET_BASE}/{year}eve.zip"
    dest = tmpdir / f"{year}eve.zip"
    out_dir = tmpdir / str(year)
    out_dir.mkdir(exist_ok=True)

    print(f"  Downloading {year}...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=60, stream=True)
        if r.status_code == 404:
            print(f"not available (404)")
            return None
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        with zipfile.ZipFile(dest, "r") as z:
            z.extractall(out_dir)
        print(f"OK ({dest.stat().st_size // 1024}KB)")
        return out_dir
    except Exception as e:
        print(f"FAILED: {e}")
        return None

# ── parse with chadwick ───────────────────────────────────────────────────────

def parse_games(event_dir: Path, year: int) -> pd.DataFrame:
    """Use cwgame to parse game-level data."""
    ros_files = list(event_dir.glob("*.ROS")) + list(event_dir.glob("*.ros"))
    eve_files = list(event_dir.glob("*.EV*")) + list(event_dir.glob("*.ev*"))
    eve_files = [f for f in eve_files if not f.suffix.upper() in ('.ROS', '.ZIP')]

    if not eve_files:
        return pd.DataFrame()

    rows = []
    for evf in eve_files:
        ros = [r for r in ros_files if r.stem[:3] == evf.stem[:3]]
        ros_args = []
        for r in ros:
            ros_args += ["-r", str(r)]
        try:
            result = subprocess.run(
                ["cwgame", "-y", str(year), "-f", "0-83"] + ros_args + [str(evf)],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and result.stdout.strip():
                from io import StringIO
                df = pd.read_csv(StringIO(result.stdout), header=None)
                rows.append(df)
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    combined = pd.concat(rows, ignore_index=True)
    # Map chadwick cwgame columns (0-indexed)
    # Col 0=game_id, 1=date, 3=away_team, 4=home_team, 10=away_score, 11=home_score
    # 17=park_id, 18=attendance, 19=duration, 36=winning_pitcher, 37=losing_pitcher, 38=save
    try:
        games = pd.DataFrame({
            "game_id":         combined[0],
            "date":            pd.to_datetime(combined[1].astype(str), format="%Y%m%d", errors="coerce"),
            "year":            year,
            "away_team":       combined[3],
            "home_team":       combined[4],
            "away_score":      pd.to_numeric(combined[10], errors="coerce"),
            "home_score":      pd.to_numeric(combined[11], errors="coerce"),
            "park_id":         combined[17],
            "attendance":      pd.to_numeric(combined[18], errors="coerce"),
            "duration_mins":   pd.to_numeric(combined[19], errors="coerce"),
            "winning_pitcher": combined[36] if len(combined.columns) > 36 else None,
            "losing_pitcher":  combined[37] if len(combined.columns) > 37 else None,
            "save_pitcher":    combined[38] if len(combined.columns) > 38 else None,
        })
        return games.dropna(subset=["game_id"])
    except Exception as e:
        print(f"    WARN game parse: {e}")
        return pd.DataFrame()


def parse_events(event_dir: Path, year: int) -> pd.DataFrame:
    """Use cwevent to parse play-by-play events."""
    ros_files = list(event_dir.glob("*.ROS")) + list(event_dir.glob("*.ros"))
    eve_files = [f for f in event_dir.glob("*") if f.suffix.upper() in ('.EVA', '.EVN', '.EVE')]

    if not eve_files:
        return pd.DataFrame()

    rows = []
    for evf in eve_files:
        ros = [r for r in ros_files if r.stem[:3] == evf.stem[:3]]
        ros_args = []
        for r in ros:
            ros_args += ["-r", str(r)]
        try:
            result = subprocess.run(
                ["cwevent", "-y", str(year), "-f", "0-6,8,10,16,34,36,58,74"] + ros_args + [str(evf)],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0 and result.stdout.strip():
                from io import StringIO
                df = pd.read_csv(StringIO(result.stdout), header=None)
                rows.append(df)
        except Exception:
            continue

    if not rows:
        return pd.DataFrame()

    combined = pd.concat(rows, ignore_index=True)
    try:
        events = pd.DataFrame({
            "game_id":      combined[0],
            "event_num":    pd.to_numeric(combined[1], errors="coerce"),
            "inning":       pd.to_numeric(combined[2], errors="coerce"),
            "batting_team": combined[3],
            "outs":         pd.to_numeric(combined[4], errors="coerce"),
            "balls":        pd.to_numeric(combined[5], errors="coerce"),
            "strikes":      pd.to_numeric(combined[6], errors="coerce"),
            "batter_id":    combined[7] if len(combined.columns) > 7 else None,
            "pitcher_id":   combined[8] if len(combined.columns) > 8 else None,
            "event_cd":     pd.to_numeric(combined[9],  errors="coerce") if len(combined.columns) > 9 else None,
            "hit_value":    pd.to_numeric(combined[10], errors="coerce") if len(combined.columns) > 10 else None,
            "rbi":          pd.to_numeric(combined[11], errors="coerce") if len(combined.columns) > 11 else None,
            "runs_scored":  pd.to_numeric(combined[12], errors="coerce") if len(combined.columns) > 12 else None,
            "play_text":    combined[13] if len(combined.columns) > 13 else None,
        })
        return events.dropna(subset=["game_id", "event_num"])
    except Exception as e:
        print(f"    WARN event parse: {e}")
        return pd.DataFrame()

# ── load to DB ────────────────────────────────────────────────────────────────

def load_df(df: pd.DataFrame, table: str, year: int):
    if df.empty:
        print(f"    SKIP {table} — no data")
        return
    # Delete existing rows for this year to allow re-runs
    with engine.connect() as conn:
        if table == "retro_events":
            conn.execute(text(f"""
                DELETE FROM {table} WHERE game_id IN (
                    SELECT game_id FROM retro_games WHERE year = :y
                )"""), {"y": year})
        else:
            conn.execute(text(f"DELETE FROM {table} WHERE year = :y"), {"y": year}) \
                if "year" in df.columns else None
        conn.commit()

    df = df.where(pd.notnull(df), None)
    df.to_sql(table, engine, if_exists="append", index=False, chunksize=5000, method="multi")
    print(f"    OK  {len(df):,} rows → {table}")

# ── main ──────────────────────────────────────────────────────────────────────

def import_year(year: int, tmpdir: Path):
    print(f"\n── {year} ──────────────────────────────────────")
    event_dir = download_year(year, tmpdir)
    if not event_dir:
        return

    print(f"  Parsing games...")
    games = parse_games(event_dir, year)
    load_df(games, "retro_games", year)

    print(f"  Parsing play-by-play events...")
    events = parse_events(event_dir, year)
    load_df(events, "retro_events", year)

    print(f"  Done — {year}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import Retrosheet data")
    parser.add_argument("--years",     nargs="+", type=int, help="Specific years e.g. 2000 2001 2002")
    parser.add_argument("--from-year", type=int,  default=1950, help="Start year for range")
    parser.add_argument("--to-year",   type=int,  default=2023, help="End year for range")
    parser.add_argument("--all",       action="store_true",     help="Import everything 1910–2023")
    args = parser.parse_args()

    print("Checking chadwick tools...")
    check_chadwick()

    print("Creating tables...")
    create_tables()

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
