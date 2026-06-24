from __future__ import annotations
"""
AI natural language search.

Routes queries to either:
  - Lahman Postgres (career/season stats, history)
  - MLB StatsAPI   (game-level, play-by-play, live, 2008–today)
"""

import os
import json
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db.database import query

router = APIRouter()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

SYSTEM_PROMPT = """
You are a baseball stats assistant. You have THREE data sources.
Choose the best one for each query and respond ONLY with a JSON object — no markdown.

━━━ SOURCE 1: lahman ━━━
Career and season-level stats, awards, Hall of Fame, salaries. 1871–present.
Use for: career totals, season stat lines, all-time records, awards, HOF, salaries.
NEVER use for individual game results or play-by-play.

{
  "source": "lahman",
  "sql": "<SELECT only — never INSERT/UPDATE/DELETE/DROP>",
  "explanation": "<one sentence>"
}

LAHMAN SCHEMA:
People       (playerID, nameFirst, nameLast, birthYear, birthCountry, weight, height, bats, throws, debut, finalGame)
Batting      (playerID, yearID, teamID, G, AB, R, H, 2B, 3B, HR, RBI, SB, CS, BB, SO, IBB, HBP, SH, SF, GIDP)
             -- avg = CAST(H AS FLOAT)/NULLIF(AB,0)
Pitching     (playerID, yearID, teamID, W, L, G, GS, CG, SHO, SV, IPouts, H, ER, HR, BB, SO, ERA, WP, BK, BFP, R)
             -- IPouts/3 = innings pitched
Fielding     (playerID, yearID, teamID, POS, G, GS, InnOuts, PO, A, E, DP)
Teams        (yearID, teamID, franchID, divID, Rank, G, W, L, R, AB, H, HR, BB, SO, RA, ER, ERA, name, park, attendance)
AwardsPlayers(playerID, awardID, yearID, lgID)
AllstarFull  (playerID, yearID, teamID, lgID, GP, startingPos)
HallOfFame   (playerID, yearID, votedBy, ballots, needed, votes, inducted, category)
Appearances  (playerID, yearID, teamID, G_all, G_p, G_c, G_1b, G_2b, G_3b, G_ss, G_lf, G_cf, G_rf, G_of, G_dh)
Salaries     (playerID, yearID, teamID, lgID, salary)
Always JOIN People for player names. Always LIMIT to 100 rows max.

━━━ SOURCE 2: retrosheet ━━━
Game-level and play-by-play data. 1910–2025 (ALL completed games including recent seasons).
Use for: ANY specific game results, play-by-play, game logs, no-hitters, shutouts, cycles.
This covers modern seasons too — use retrosheet for ALL completed games including 2024/2025.

{
  "source": "retrosheet",
  "action": "<search_games | game_plays | player_gamelog | advanced_search>",
  "params": { },
  "explanation": "<one sentence>"
}

ACTIONS:
search_games  — find games by team/date/score. Params:
  { "team": "NYA", "year_from": 1950, "year_to": 2024, "min_runs": 10, "limit": 50 }

game_plays    — play-by-play for one specific game. Params:
  { "game_id": "NYA192706300", "inning": 9, "event": "hr" }
  -- event: "hits" | "hr" | "so" | "bb" | "single" | "double" | "triple"

player_gamelog — game-by-game stats for a player. Params:
  { "player_id": "ruthba01", "year_from": 1926, "year_to": 1932,
    "stat_type": "batting", "min_hits": 3, "min_hr": 1 }
  -- stat_type: "batting" or "pitching"

advanced_search — MOST POWERFUL. Search by game-level performance. Params:
  { "team": "NYA", "year_from": 1950, "year_to": 2024,
    "min_hits_game": 4,      <- player had 4+ hits in a game
    "max_runs_game": 0,      <- player scored 0 runs
    "min_hr_game": 2,        <- player hit 2+ HR in a game
    "min_rbi_game": 5,       <- player had 5+ RBI
    "complete_game": true,   <- pitcher went the distance
    "shutout": true,         <- pitcher allowed 0 runs
    "min_k_game": 10,        <- pitcher struck out 10+
    "max_hits_allowed": 3,   <- pitcher allowed 3 or fewer hits
    "no_hitter": true,       <- no-hitter
    "limit": 50 }

━━━ ROUTING DECISION TREE ━━━

Is the user asking about career stats, season totals, awards, HOF, salaries? → lahman
Everything else (game results, play-by-play, game logs, specific performances)? → retrosheet

━━━ EXAMPLES ━━━
"most career home runs all time"                       → lahman
"Hall of Famers born in Dominican Republic"            → lahman
"Babe Ruth career stats"                               → lahman
"highest single season ERA ever"                       → lahman
"Yankees 2024 season results"                          → retrosheet search_games (year_from:2024, year_to:2024, team:NYA)
"4 hits and no runs in a game"                         → retrosheet advanced_search (min_hits_game:4, max_runs_game:0)
"no-hitters since 2010"                                → retrosheet advanced_search (no_hitter:true, year_from:2010)
"complete game shutouts with 10+ strikeouts"           → retrosheet advanced_search (shutout:true, min_k_game:10)
"Babe Ruth game log 1927"                              → retrosheet player_gamelog
"Aaron Judge games with 2+ HR in 2022"                → retrosheet advanced_search (min_hr_game:2, year_from:2022, year_to:2022)
"Shohei Ohtani 2023 pitching game log"                 → retrosheet player_gamelog (stat_type:pitching, year_from:2023)
"Yankees vs Red Sox games last September"              → retrosheet search_games

=== IF source is "retrosheet" ===
{
  "source": "retrosheet",
  "action": "<one of: search_games | game_plays | player_gamelog | advanced_search>",
  "params": { },
  "explanation": "<one sentence>"
}

RETROSHEET ACTIONS (historical play-by-play 1910–2007):

search_games — find historical games. Params:
  { "team": "NYA", "year_from": 1950, "year_to": 1960, "min_runs": 10, "limit": 50 }

game_plays — play-by-play for one game. Params:
  { "game_id": "NYA192706300", "inning": 9, "event": "hr" }
  -- event options: "hits" | "hr" | "so" | "bb" | "single" | "double" | "triple"

player_gamelog — game-by-game stats for a player. Params:
  { "player_id": "ruthba01", "year_from": 1926, "year_to": 1932,
    "stat_type": "batting", "min_hits": 3, "min_hr": 1 }
  -- stat_type: "batting" or "pitching"

advanced_search — the MOST POWERFUL action for specific game performances. Params:
  { "team": "NYA", "year_from": 1950, "year_to": 1970,
    "min_hits_game": 4, "max_runs_game": 0,   <- "4 hits and no runs in a game"
    "complete_game": true, "shutout": true,    <- complete game shutout
    "min_k_game": 10,                          <- 10+ strikeouts
    "no_hitter": true,                         <- no-hitter
    "min_hr_game": 2,                          <- 2+ HR in a game
    "limit": 50 }

ROUTING — use retrosheet when:
- Query involves individual GAME performances (not season totals) before 2008
- "4 hits in a game", "complete game shutout", "no-hitter", "cycle", "game log"
- Specific historical play-by-play
- Player's game-by-game performance in a specific season/era

Use lahman (not retrosheet) for: career/season totals, awards, HOF, salaries

ROUTING EXAMPLES:
"4 hits and no runs in a game" (historical) -> retrosheet advanced_search
"4 hits and no runs in a game"             -> retrosheet advanced_search
"most career home runs"                     -> lahman SQL
"Babe Ruth game log 1927"                   -> retrosheet player_gamelog
"no-hitters in the 1960s"                   -> retrosheet advanced_search
"complete game shutouts with 10+ strikeouts" -> retrosheet advanced_search
"Sandy Koufax 1965 World Series plays"      -> retrosheet game_plays
"Hall of Famers from Venezuela"             -> lahman SQL
"Yankees games last week"                   -> retrosheet search_games
"Yankees games in 1961"                     -> retrosheet search_games
"""


class AISearchRequest(BaseModel):
    query: str

class AISearchResponse(BaseModel):
    source: str
    explanation: str
    results: list
    row_count: int
    sql: str | None = None
    action: str | None = None


@router.post("/ai-search", response_model=AISearchResponse)
async def ai_search(req: AISearchRequest):
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")
    if len(req.query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Query too short")

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 1024,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": req.query}],
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Claude API error")

    raw = resp.json()["content"][0]["text"].strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        parsed = json.loads(raw)
    except Exception:
        raise HTTPException(status_code=502, detail="Could not parse Claude response")

    source      = parsed.get("source")
    explanation = parsed.get("explanation", "")

    if source == "lahman":
        sql = parsed.get("sql", "").strip()
        if not sql.upper().startswith("SELECT"):
            raise HTTPException(status_code=400, detail="Only SELECT queries allowed")
        try:
            results = query(sql)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"SQL error: {str(e)}")
        return AISearchResponse(
            source="lahman", explanation=explanation,
            results=results, row_count=len(results), sql=sql,
        )

    elif source == "retrosheet":
        action = parsed.get("action")
        params = parsed.get("params", {})

        from routers.retro import (
            search_games as retro_search_games,
            game_plays,
            player_gamelog,
            advanced_search,
        )

        try:
            if action == "search_games":
                results = retro_search_games(
                    team      = params.get("team"),
                    year_from = params.get("year_from"),
                    year_to   = params.get("year_to"),
                    date_from = params.get("date_from"),
                    date_to   = params.get("date_to"),
                    min_runs  = params.get("min_runs"),
                    limit     = min(params.get("limit", 50), 200),
                )

            elif action == "game_plays":
                game_id = params.get("game_id")
                if not game_id:
                    raise HTTPException(status_code=400, detail="game_plays requires game_id")
                data = game_plays(
                    game_id = game_id,
                    inning  = params.get("inning"),
                    event   = params.get("event"),
                )
                results = data.get("plays", [])

            elif action == "player_gamelog":
                pid = params.get("player_id")
                if not pid:
                    raise HTTPException(status_code=400, detail="player_gamelog requires player_id")
                results = player_gamelog(
                    player_id  = pid,
                    year_from  = params.get("year_from"),
                    year_to    = params.get("year_to"),
                    stat_type  = params.get("stat_type", "batting"),
                    min_hits   = params.get("min_hits"),
                    min_hr     = params.get("min_hr"),
                    min_rbi    = params.get("min_rbi"),
                    min_so     = params.get("min_so"),
                    limit      = min(params.get("limit", 100), 500),
                )

            elif action == "advanced_search":
                results = advanced_search(
                    team              = params.get("team"),
                    year_from         = params.get("year_from"),
                    year_to           = params.get("year_to"),
                    min_hits_game     = params.get("min_hits_game"),
                    max_runs_game     = params.get("max_runs_game"),
                    min_hr_game       = params.get("min_hr_game"),
                    min_rbi_game      = params.get("min_rbi_game"),
                    complete_game     = params.get("complete_game"),
                    shutout           = params.get("shutout"),
                    min_k_game        = params.get("min_k_game"),
                    max_hits_allowed  = params.get("max_hits_allowed"),
                    no_hitter         = params.get("no_hitter"),
                    limit             = min(params.get("limit", 50), 200),
                )
            else:
                raise HTTPException(status_code=400, detail=f"Unknown retrosheet action: {action}")

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Retrosheet error: {str(e)}")

        return AISearchResponse(
            source="retrosheet", explanation=explanation, action=action,
            results=results if isinstance(results, list) else [results],
            row_count=len(results) if isinstance(results, list) else 1,
        )

    raise HTTPException(status_code=502, detail=f"Unknown source: {source}")
