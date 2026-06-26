import requests, pandas as pd
from io import StringIO

r = requests.get(
    "https://www.retrosheet.org/BIOFILE.TXT",
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=60
)

df = pd.read_csv(StringIO(r.text), quotechar='"', skipinitialspace=True)

print("Column names:")
for col in df.columns:
    print(f"  '{col}'")

print(f"\nFirst 3 rows of key columns:")
for _, row in df.head(3).iterrows():
    print(f"  ID={row['PLAYERID']}  LAST={row['LAST']}  FIRST={row['FIRST']}")