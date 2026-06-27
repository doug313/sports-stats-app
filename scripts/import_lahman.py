#!/usr/bin/env python3
"""
Import or update Lahman database CSV files into Postgres (or SQLite for local dev).

Usage:
  python import_lahman.py --csv-dir ./lahman-csvs

Download CSVs from: https://github.com/chadwickbureau/baseballdatabank/archive/master.zip
"""

import os
import sys
import argparse
import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./lahman.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Maps CSV filename → SQL table name
TABLES = {
    "People.csv":        "people",
    "Batting.csv":       "batting",
    "Pitching.csv":      "pitching",
    "Fielding.csv":      "fielding",
    "Teams.csv":         "teams",
    "AwardsPlayers.csv": "awardsplayers",
    "AllstarFull.csv":   "allstarfull",
    "HallOfFame.csv":    "halloffame",
    "Appearances.csv":   "appearances",
    "Salaries.csv":      "salaries",
}

def import_csvs(csv_dir: str):
    engine = create_engine(DATABASE_URL)

    for filename, table in TABLES.items():
        filepath = os.path.join(csv_dir, filename)
        if not os.path.exists(filepath):
            print(f"  SKIP  {filename} (not found)")
            continue

        print(f"  Loading {filename} → {table}...")
        df = pd.read_csv(filepath, low_memory=False)

        # Replace empty strings with None for clean nulls in DB
        df = df.where(pd.notnull(df), None)

        df.to_sql(
            table,
            engine,
            if_exists="replace",   # change to "append" for incremental updates
            index=False,
            chunksize=5000,
        )
        print(f"  ✓ {len(df):,} rows → {table}")

    print("\nDone! Database is ready.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", default="./lahman-csvs",
                        help="Directory containing Lahman CSV files")
    args = parser.parse_args()
    import_csvs(args.csv_dir)
