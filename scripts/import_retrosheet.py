#!/usr/bin/env python3
"""
Import Retrosheet play-by-play data into Postgres/SQLite.

Requirements:
  - chadwick CLI tool (cwevent, cwgame must be on PATH)
  - pip install pandas sqlalchemy psycopg2-binary requests tqdm

Usage:
  DATABASE_URL=sqlite:///./lahman.db python import_retrosheet.py --years 1960 1970
  DATABASE_URL=sqlite:///./lahman.db python import_retrosheet.py --from-year 1950 --to-year 2025
  DATABASE_URL=sqlite:///./lahman.db python import_retrosheet.py --all
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
ERROR: '{cmd}' not found. Install chadwick first:
  Windows: download from https://github.com/chadwickbureau/chadwick/releases
           unzip and add folder to your PATH
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
                home_team       VARCHAR(10),
                away_team       VARCHAR(10),
                home_score      INTEGER,
                away_score      INTEGER,
                home_hits       INTEGER,
                away_hits       INTEGER,
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
                batting_team    VARCHAR(10),
                outs            INTEGER,
                balls           INTEGER,
                strikes         INTEGER,
                batter_id       VARCHAR(20),
                pitcher_id      VARCHAR(20),
                event_cd        INTEGER,
                hit_value       INTEGER,
                rbi             INTEGER,
                runs_scored     INTEGER,
                play_text       TEXT
            )
        """))

        for idx_sql in [
            "CREATE INDEX IF NOT EXISTS idx_retro_games_year  ON retro_games(year)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_home  ON retro_games(home_team)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_away  ON retro_games(away_team)",
            "CREATE INDEX IF NOT EXISTS idx_retro_games_date  ON retro_games(date)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_game    ON retro_events(game_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_batter  ON retro_events(batter_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_pitcher ON retro_events(pitcher_id)",
            "CREATE INDEX IF NOT EXISTS idx_retro_evt_type    ON retro_events(event_cd)",
        ]:
            conn.execute(text(idx_sql))

        conn.commit()
    print("  OK  Tables and indexes created")

# ── download ──────────────────────────────────────────────────────────────────

def download_year(year: int, tmpdir: Path):
    url = f"{RETROSHEET_BASE}/{year}eve.zip"
    dest = tmpdir / f"{year}eve.zip"
    out_dir = tmpdir / str(year)
    out_dir.mkdir(exist_ok=True)

    print(f"  Downloading {year}...", end=" ", flush=True)
    try:
        r = requests.get(url, timeout=60,
                         headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 404:
            print("not available (404)")
            return None
        r.raise_for_status()
        dest.write_bytes(r.content)
        with zipfile.ZipFile(dest, "r") as z:
            z.extractall(out_dir)
        print(f"OK ({dest.stat().st_size // 1024}KB)")
        return out_dir
    except Exception as e:
        print(f"FAILED: {e}")
        return None

# ── parse games ───────────────────────────────────────────────────────────────

def parse_games(event_dir: Path, year: int) -> pd.DataFrame:
    """Use cwgame to parse game-level data."""
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
            "game_id": combined[0],
            "date": pd.to_datetime(
                combined[0].str[3:11],
                format="%Y%m%d", errors="coerce"),
            "year": year,
            "away_team": combined[1],
            "home_team": combined[2],
            "attendance": pd.to_numeric(combined[3], errors="coerce"),
            "duration_mins": pd.to_numeric(combined[4], errors="coerce"),
            "away_score": pd.to_numeric(combined[5], errors="coerce"),
            "home_score": pd.to_numeric(combined[6], errors="coerce"),
            "away_hits": pd.to_numeric(combined[7], errors="coerce"),
            "home_hits": pd.to_numeric(combined[8], errors="coerce"),
            "winning_pitcher": combined[9],
            "losing_pitcher": combined[10],
            "save_pitcher": combined[11],
        })
        games = games.drop_duplicates(subset=["game_id"])
        return games.dropna(subset=["game_id"])
    except Exception as e:
        print(f"    WARN game parse: {e}")
        return pd.DataFrame()


def parse_events(event_dir: Path, year: int) -> pd.DataFrame:
    """Use cwevent to parse play-by-play events."""
    eve_files = [f for f in event_dir.iterdir()
                 if f.suffix.upper() in ('.EVA', '.EVN', '.EVE')]

    if not eve_files:
        return pd.DataFrame()

    rows = []
    for evf in eve_files:
        try:
            result = subprocess.run(
                ["cwevent", "-y", str(year),
                 "-f", "0,2,3,4,5,6,10,14,34,37,40,43,58,96,29",
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
            "game_id":      combined[0],
            "inning":       pd.to_numeric(combined[1], errors="coerce"),
            "batting_team": combined[2],
            "outs":         pd.to_numeric(combined[3], errors="coerce"),
            "balls":        pd.to_numeric(combined[4], errors="coerce"),
            "strikes":      pd.to_numeric(combined[5], errors="coerce"),
            "batter_id":    combined[6],
            "pitcher_id":   combined[7],
            "event_cd":     pd.to_numeric(combined[8],  errors="coerce"),
            "hit_value":    pd.to_numeric(combined[9],  errors="coerce"),
            "runs_scored":  pd.to_numeric(combined[10], errors="coerce"),
            "rbi":          pd.to_numeric(combined[11], errors="coerce"),
            "event_num":    pd.to_numeric(combined[13], errors="coerce"),
            "play_text":    combined[14],
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

    is_sqlite = DATABASE_URL.startswith("sqlite")
    chunk = 50 if is_sqlite else 5000

    # Delete existing rows for this year first
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

    # Deduplicate the dataframe itself before inserting
    if table == "retro_events":
        before = len(df)
        df = df.drop_duplicates(subset=["game_id", "event_num"])
        dupes = before - len(df)
        if dupes > 0:
            print(f"    INFO dropped {dupes} duplicate events")

    if table == "retro_games":
        df = df.drop_duplicates(subset=["game_id"])

    df = df.where(pd.notnull(df), None)
    df.to_sql(table, engine, if_exists="append", index=False,
              chunksize=chunk)
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
    parser.add_argument("--years",     nargs="+", type=int,
                        help="Specific years e.g. 1960 1970 1980")
    parser.add_argument("--from-year", type=int, default=1950,
                        help="Start year for range")
    parser.add_argument("--to-year",   type=int, default=2025,
                        help="End year for range")
    parser.add_argument("--all",       action="store_true",
                        help="Import everything 1910-2025")
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