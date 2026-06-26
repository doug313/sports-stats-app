import requests

url = "https://www.retrosheet.org/BIOFILE.TXT"
r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
print(f"Status: {r.status_code}")
print(f"Size: {len(r.content)}")
print("\nFirst 5 lines:")
for line in r.text.split('\n')[:5]:
    print(repr(line))