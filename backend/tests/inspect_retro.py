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

    evf = next(f for f in out_dir.iterdir() if f.suffix.upper() == '.EVA')
    print(f"Using: {evf.name}")

    result = subprocess.run(
        ["cwevent", "-y", str(YEAR),
         "-f", "0,2,3,4,5,6,10,14,34,37,40,43,58,96,29",
         str(evf)],
        capture_output=True, text=True, timeout=120,
        cwd=str(out_dir)
    )

    lines = result.stdout.strip().split('\n')
    print(f"\nFirst 5 rows with column indices:")
    for line in lines[:5]:
        fields = line.split(',')
        print(f"\n  Raw: {line}")
        for i, val in enumerate(fields):
            print(f"    col[{i}] = {val}")