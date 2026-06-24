# ⚾ Diamond Stats

Search 150 years of baseball history. Structured filters + AI natural language
search powered by the Lahman database and Claude.

---

## Project structure

```
baseball-app/
├── frontend/          React + Vite (deploys to Vercel)
├── backend/           FastAPI (deploys to Railway)
└── scripts/           Database import utilities
```

---

## Local development

### 1. Clone and set up

```bash
git clone https://github.com/YOUR_USERNAME/baseball-app.git
cd baseball-app
```

### 2. Get the Lahman database

```bash
# Download the latest release
curl -L https://github.com/chadwickbureau/baseballdatabank/archive/master.zip -o lahman.zip
unzip lahman.zip
mv baseballdatabank-master/core ./lahman-csvs

# Import into local SQLite (takes ~30 seconds)
cd scripts
pip install pandas sqlalchemy
python import_lahman.py --csv-dir ../lahman-csvs
mv lahman.db ../backend/
```

### 3. Start the backend

```bash
cd backend
pip install -r requirements.txt

# Set your Claude API key (get one at console.anthropic.com)
export ANTHROPIC_API_KEY=sk-ant-...

uvicorn main:app --reload
# API now running at http://localhost:8000
```

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
# App now running at http://localhost:5173
```

---

## Deploying

### Backend → Railway

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub
2. Select this repo, set root directory to `backend/`
3. Add environment variables in Railway dashboard:
   - `ANTHROPIC_API_KEY` = your key
   - `DATABASE_URL` = Railway provides this automatically when you add a Postgres plugin
4. Add a **Postgres** plugin in Railway — copy the `DATABASE_URL` it gives you
5. Run the import script once, pointed at your Railway Postgres URL:
   ```bash
   DATABASE_URL=postgresql://... python scripts/import_lahman.py --csv-dir ./lahman-csvs
   ```
6. Every `git push` to `main` auto-redeploys the backend

### Frontend → Vercel

1. Go to [vercel.com](https://vercel.com) → New Project → Import from GitHub
2. Set root directory to `frontend/`
3. Add environment variable:
   - `VITE_API_URL` = your Railway backend URL (e.g. `https://your-app.railway.app/api`)
4. Every `git push` to `main` auto-redeploys the frontend

---

## Updating the database each year

When Lahman releases a new annual update (usually April–May):

```bash
# Download fresh CSVs
curl -L https://github.com/chadwickbureau/baseballdatabank/archive/master.zip -o lahman.zip
unzip -o lahman.zip
mv baseballdatabank-master/core ./lahman-csvs

# Push to your cloud Postgres (swap in your Railway DATABASE_URL)
DATABASE_URL=postgresql://... python scripts/import_lahman.py --csv-dir ./lahman-csvs
```

That's it — no code changes, no redeployment needed.

---

## AI search examples

The AI search understands natural language and converts it to SQL automatically:

- "Players with 4 hits and no runs in a game" 
- "Pitchers with ERA under 2 and 200+ strikeouts"
- "Hall of Famers born in the Dominican Republic"
- "Seasons where a player hit .400 or better"
- "Most stolen bases in a single season since 1980"
- "Teams with more than 100 wins and a losing World Series"

---

## Cost estimate (friends & family scale)

| Service  | Cost        | Notes                        |
|----------|-------------|------------------------------|
| Vercel   | Free        | Frontend, global CDN         |
| Railway  | ~$5/mo      | Backend + Postgres, always on|
| Claude API | ~$1–3/mo  | At casual usage levels       |
| **Total** | **~$6–8/mo** |                             |

---

## Retrosheet (historical play-by-play 1910–2007)

Retrosheet gives you game-level and play-by-play data from 1910 through 2025 —
no-hitters, complete game shutouts, player game logs, individual at-bats.
This covers ALL completed games including recent seasons.

### Step 1 — Install chadwick

chadwick is a free CLI tool that parses Retrosheet's raw event files.

```bash
# macOS
brew install chadwick-bureau/chadwick/chadwick

# Ubuntu / Codespaces
sudo apt-get install chadwick

# Windows — download from:
# https://github.com/chadwickbureau/chadwick/releases
# Add the folder to your PATH
```

### Step 2 — Import data

Start with a small range to test — each decade takes about 5 minutes:

```bash
cd scripts

# Import 1950s–1990s (recommended starting range)
DATABASE_URL=postgresql://... python import_retrosheet.py --from-year 1950 --to-year 1999

# Add specific years
DATABASE_URL=postgresql://... python import_retrosheet.py --years 2008 2009 2010 2011 2012 2013 2014 2015 2016 2017 2018 2019 2020 2021 2022 2023 2024 2025

# Everything (1910–2025) — takes 30-60 min
DATABASE_URL=postgresql://... python import_retrosheet.py --all
```

### What Retrosheet unlocks

After import, the AI search handles queries like:
- "No-hitters in the 1960s"
- "Complete game shutouts with 10+ strikeouts before 1980"
- "Babe Ruth game log 1927"
- "Games where a player had 4 hits and the team scored 0 runs"
- "Sandy Koufax play-by-play 1965 World Series"

### Attribution required

Per Retrosheet's license, any public display must include:
> "The information used here was obtained free of charge from and is
>  copyrighted by Retrosheet. Interested parties may contact Retrosheet
>  at www.retrosheet.org"

Consider adding this to your app's footer.
