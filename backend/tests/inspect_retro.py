"""
Inspect raw cwgame output to verify field mappings.
Run from the backend/ folder.
"""

import subprocess, zipfile, tempfile, requests
from pathlib import Path

YEAR = 1960
URL = f"https://www.retrosheet.org/events/{YEAR}eve.zip"

print(f"Downloading {YEAR}...")
r = requests.get(URL, timeout=60, headers={"User-Agent": "Mozilla/5.0"})

with tempfile.TemporaryDirectory() as tmp:
    tmp = Path(tmp)
    zpath = tmp / "test.zip"
    zpath.write_bytes(r.content)

    out_dir = tmp / str(YEAR)
    out_dir.mkdir()
    with zipfile.ZipFile(zpath) as z:
        z.extractall(out_dir)

    # Pick one EVA file
    evf = next(f for f in out_dir.iterdir() if f.suffix.upper() == '.EVA')
    print(f"Using: {evf.name}")

    # Run cwgame with our field list
    result = subprocess.run(
        ["cwgame", "-y", str(YEAR),
         "-f", "0,7,8,34,35,36,37,18,32,42,43,44",
         str(evf)],
        capture_output=True, text=True, timeout=120,
        cwd=str(out_dir)
    )

    lines = result.stdout.strip().split('\n')
    print(f"\nTotal lines: {len(lines)}")
    print(f"\nFirst 5 rows:")
    for line in lines[:5]:
        fields = line.split(',')
        print(f"\n  Raw: {line}")
        for i, val in enumerate(fields):
            print(f"    col[{i}] = {val}")