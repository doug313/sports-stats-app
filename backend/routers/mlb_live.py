"""
MLB StatsAPI integration — no API key required.
Covers live games, play-by-play, box scores, and game search (2008–today).
"""

from datetime import date, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()

BASE = "https://statsapi.mlb.com/api/v1"
BASE_11 = "https://statsapi.mlb.com/api/v1.1"


MLB_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; baseball-stats-app/1.0)",
    "Accept": "application/json",
}

async def mlb_get(path: str, params: dict = {}) -> dict:
    url = path if path.startswith("http") else f"{BASE}{path}"
    async with httpx.AsyncClient(timeout=15, headers=MLB_HEADERS) as client:
        r = await client.get(url, params=params)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"MLB API error: {r.status_code}")
    return r.json()


# ── live scoreboard ───────────────────────────────────────────────────────────

@router.get("/mlb/live")
async def live_games():
    """Today's games with live scores and status."""
    today = date.today().strftime("%Y-%m-%d")
    data = await mlb_get("/schedule", {
        "sportId": 1,
        "date": today,
        "hydrate": "linescore,team",
    })

    games = []
    for date_entry in data.get("dates", []):
        for g in date_entry.get("games", []):
            ls = g.get("linescore", {})
            games.append({
                "game_pk":    g["gamePk"],
                "status":     g["status"]["detailedState"],
                "away_team":  g["teams"]["away"]["team"]["name"],
                "home_team":  g["teams"]["home"]["team"]["name"],
                "away_score": g["teams"]["away"].get("score"),
                "home_score": g["teams"]["home"].get("score"),
                "inning":     ls.get("currentInning"),
                "inning_half":ls.get("inningHalf"),
                "away_hits":  ls.get("teams", {}).get("away", {}).get("hits"),
                "home_hits":  ls.get("teams", {}).get("home", {}).get("hits"),
                "away_errors":ls.get("teams", {}).get("away", {}).get("errors"),
                "home_errors":ls.get("teams", {}).get("home", {}).get("errors"),
                "venue":      g.get("venue", {}).get("name"),
            })
    return games


# ── box score ─────────────────────────────────────────────────────────────────

@router.get("/mlb/game/{game_pk}/boxscore")
async def box_score(game_pk: int):
    """Full box score for a game."""
    data = await mlb_get(f"{BASE_11}/game/{game_pk}/feed/live")
    box  = data.get("liveData", {}).get("boxscore", {})
    linescore = data.get("liveData", {}).get("linescore", {})
    game_info = data.get("gameData", {})

    result = {
        "game_pk":   game_pk,
        "date":      game_info.get("datetime", {}).get("officialDate"),
        "venue":     game_info.get("venue", {}).get("name"),
        "status":    game_info.get("status", {}).get("detailedState"),
        "linescore": {
            "innings": linescore.get("innings", []),
            "away":    linescore.get("teams", {}).get("away", {}),
            "home":    linescore.get("teams", {}).get("home", {}),
        },
        "teams": {},
    }

    for side in ["away", "home"]:
        team_data = box.get("teams", {}).get(side, {})
        team_name = team_data.get("team", {}).get("name", side)
        batters, pitchers = [], []

        for pid, pdata in team_data.get("players", {}).items():
            pos  = pdata.get("position", {}).get("abbreviation", "")
            name = pdata.get("person", {}).get("fullName", "")
            stats = pdata.get("stats", {})

            if pos != "P" and stats.get("batting"):
                b = stats["batting"]
                batters.append({
                    "name":    name,
                    "pos":     pos,
                    "ab":      b.get("atBats", 0),
                    "h":       b.get("hits", 0),
                    "r":       b.get("runs", 0),
                    "rbi":     b.get("rbi", 0),
                    "bb":      b.get("baseOnBalls", 0),
                    "so":      b.get("strikeOuts", 0),
                    "hr":      b.get("homeRuns", 0),
                    "avg":     b.get("avg", "---"),
                    "order":   pdata.get("battingOrder", 999),
                })

            if stats.get("pitching") and pdata.get("stats", {}).get("pitching", {}).get("inningsPitched"):
                p = stats["pitching"]
                pitchers.append({
                    "name": name,
                    "ip":   p.get("inningsPitched", "0.0"),
                    "h":    p.get("hits", 0),
                    "r":    p.get("runs", 0),
                    "er":   p.get("earnedRuns", 0),
                    "bb":   p.get("baseOnBalls", 0),
                    "so":   p.get("strikeOuts", 0),
                    "era":  p.get("era", "---"),
                    "note": pdata.get("stats", {}).get("pitching", {}).get("note", ""),
                })

        batters.sort(key=lambda x: x["order"])
        result["teams"][side] = {
            "name":     team_name,
            "batters":  batters,
            "pitchers": pitchers,
        }

    return result


# ── play-by-play ──────────────────────────────────────────────────────────────

@router.get("/mlb/game/{game_pk}/plays")
async def play_by_play(
    game_pk: int,
    inning: Optional[int] = None,
    filter: Optional[str] = None,   # "hits", "hr", "so", "runs", "errors"
):
    """
    Full play-by-play for a game.
    Optionally filter by inning or event type.
    """
    data = await mlb_get(f"{BASE_11}/game/{game_pk}/feed/live")
    all_plays = data.get("liveData", {}).get("plays", {}).get("allPlays", [])

    EVENT_FILTERS = {
        "hits":   ["Single", "Double", "Triple", "Home Run"],
        "hr":     ["Home Run"],
        "so":     ["Strikeout"],
        "runs":   None,   # handled by rbi > 0 check
        "errors": ["Field Error"],
        "walks":  ["Walk", "Intent Walk"],
    }

    results = []
    for play in all_plays:
        about  = play.get("about", {})
        result = play.get("result", {})
        match  = play.get("matchup", {})

        play_inning = about.get("inning")
        event_type  = result.get("event", "")
        rbi         = result.get("rbi", 0)

        # Inning filter
        if inning and play_inning != inning:
            continue

        # Event filter
        if filter:
            if filter == "runs" and rbi == 0:
                continue
            elif filter in EVENT_FILTERS and EVENT_FILTERS[filter]:
                if event_type not in EVENT_FILTERS[filter]:
                    continue

        results.append({
            "inning":      play_inning,
            "half":        about.get("halfInning", "").capitalize(),
            "batter":      match.get("batter", {}).get("fullName", ""),
            "pitcher":     match.get("pitcher", {}).get("fullName", ""),
            "event":       event_type,
            "description": result.get("description", ""),
            "rbi":         rbi,
            "away_score":  result.get("awayScore"),
            "home_score":  result.get("homeScore"),
            "outs":        about.get("outs", 0),
        })

    return {
        "game_pk":    game_pk,
        "play_count": len(results),
        "plays":      results,
    }


# ── game search (historical) ──────────────────────────────────────────────────

@router.get("/mlb/games/search")
async def search_games(
    team: Optional[str]  = None,         # team name fragment, e.g. "Yankees"
    date_from: Optional[str] = None,     # YYYY-MM-DD
    date_to: Optional[str]   = None,
    season: Optional[int]    = None,
    limit: int = Query(default=20, le=50),
):
    """Search for games by team and date range."""
    if season:
        date_from = date_from or f"{season}-03-01"
        date_to   = date_to   or f"{season}-11-30"
    else:
        date_from = date_from or (date.today() - timedelta(days=7)).strftime("%Y-%m-%d")
        date_to   = date_to   or date.today().strftime("%Y-%m-%d")

    data = await mlb_get("/schedule", {
        "sportId":   1,
        "startDate": date_from,
        "endDate":   date_to,
        "hydrate":   "linescore,team",
        "gameType":  "R",  # regular season
    })

    games = []
    for date_entry in data.get("dates", []):
        for g in date_entry.get("games", []):
            away = g["teams"]["away"]["team"]["name"]
            home = g["teams"]["home"]["team"]["name"]

            if team and team.lower() not in away.lower() and team.lower() not in home.lower():
                continue

            ls = g.get("linescore", {})
            games.append({
                "game_pk":    g["gamePk"],
                "date":       date_entry["date"],
                "away_team":  away,
                "home_team":  home,
                "away_score": g["teams"]["away"].get("score"),
                "home_score": g["teams"]["home"].get("score"),
                "away_hits":  ls.get("teams", {}).get("away", {}).get("hits"),
                "home_hits":  ls.get("teams", {}).get("home", {}).get("hits"),
                "status":     g["status"]["detailedState"],
                "venue":      g.get("venue", {}).get("name"),
            })
            if len(games) >= limit:
                break
        if len(games) >= limit:
            break

    return games
