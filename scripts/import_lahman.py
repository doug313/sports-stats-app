#!/usr/bin/env python3
"""
Import Lahman database CSV files into Postgres with lowercase table and column names.
"""

import os
import argparse
import pandas as pd
from sqlalchemy import create_engine

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./lahman.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

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
        print(f"  Loading {filename} -> {table}...")
        df = pd.read_csv(filepath, low_memory=False)
        df = df.where(pd.notnull(df), None)
        # Lowercase all column names for Postgres compatibility
        df.columns = [c.lower() for c in df.columns]
        df.to_sql(table, engine, if_exists="replace", index=False, chunksize=5000)
        print(f"  OK {len(df):,} rows -> {table}")
    print("\nDone! Database is ready.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv-dir", default="./lahman-csvs")
    args = parser.parse_args()
    import_csvs(args.csv_dir)