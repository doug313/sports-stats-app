from __future__ import annotations
"""
AI natural language search.
Routes queries to Lahman (career/season stats) or Retrosheet (game-level/play-by-play).
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
You are a baseball stats assistant. You have TWO data sources.
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

LAHMAN SCHEMA (all table AND column names are lowercase):
people       (playerid, namefirst, namelast, birthyear, birthcountry, weight, height, bats, throws, debut, finalgame)
batting      (playerid, yearid, teamid, g, ab, r, h, "2b", "3b", hr, rbi, sb, cs, bb, so, ibb, hbp, sh, sf, gidp)
             -- avg = CAST(h AS FLOAT)/NULLIF(ab,0)
             -- NOTE: 2B column is named "2b", 3B column is named "3b" (use double quotes)
pitching     (playerid, yearid, teamid, w, l, g, gs, cg, sho, sv, ipouts, h, er, hr, bb, so, era, wp, bk, bfp, r)
             -- ipouts/3 = innings pitched. Use era::NUMERIC for ROUND()
fielding     (playerid, yearid, teamid, pos, g, gs, innouts, po, a, e, dp)
teams        (yearid, teamid, franchid, divid, rank, g, w, l, r, ab, h, hr, bb, so, ra, er, era, name, park, attendance)
awardsplayers(playerid, awardid, yearid, lgid)
allstarfull  (playerid, yearid, teamid, lgid, gp, startingpos)
halloffame   (playerid, yearid, votedby, ballots, needed, votes, inducted, category)
appearances  (playerid, yearid, teamid, g_all, g_p, g_c, g_1b, g_2b, g_3b, g_ss, g_lf, g_cf, g_rf, g_of, g_dh)
salaries     (playerid, yearid, teamid, lgid, salary)
Always JOIN people for player names. Always LIMIT to 100 rows max.
CRITICAL: Use ::NUMERIC cast for ROUND() e.g. ROUND(era::NUMERIC, 2)

━━━ SOURCE 2: retrosheet ━━━
Game-level and play-by-play data. 1920–2025 (ALL completed games).
Use for: ANY specific game results, play-by-play, game logs, no-hitters, shutouts, cycles.
This covers ALL completed games including modern seasons 2024/2025.

{
  "source": "retrosheet",
  "action": "<search_games | game_plays | player_gamelog | player_pitching | advanced_search>",
  "params": { },
  "explanation": "<one sentence>"
}

ACTIONS:
search_games  — find games by team/date/score. Params:
  { "team": "NYA", "year_from": 1950, "year_to": 2024, "min_runs": 10, "limit": 50 }

game_plays    — play-by-play for one specific game. Params:
  { "game_id": "NYA196106180", "inning": 9, "event": "hr" }
  -- event: "hits" | "hr" | "so" | "bb" | "single" | "double" | "triple"

player_gamelog — game-by-game BATTING stats for a player. Params:
  { "player_id": "ruthba01", "year_from": 1926, "year_to": 1932,
    "min_hits": 3, "min_hr": 1, "min_rbi": 3 }
  -- IMPORTANT: uses Retrosheet player IDs (different from Lahman IDs)
  -- Common IDs: ruthba01=Babe Ruth, mantm101=Mickey Mantle, aaroh101=Hank Aaron
  -- bondsba01=Barry Bonds, judgeaa01=Aaron Judge, ohtansh01=Shohei Ohtani

player_pitching — game-by-game PITCHING stats for a player. Params:
  { "player_id": "koufasa01", "year_from": 1963, "year_to": 1966,
    "min_so": 10, "min_ip": 6.0 }
  -- Use for: pitcher game logs, individual starts, high strikeout games
  -- Common IDs: koufasa01=Sandy Koufax, gibsobo01=Bob Gibson, ryanno01=Nolan Ryan
  -- clemero02=Roger Clemens, johnsra05=Randy Johnson, maddugr02=Greg Maddux

advanced_search — MOST POWERFUL. Search by game-level performance. Params:
  { "team": "NYA", "year_from": 1950, "year_to": 2024,
    "min_hits_game": 4,       <- player had 4+ hits in a game
    "max_runs_game": 0,       <- player scored 0 runs
    "min_hr_game": 2,         <- player hit 2+ HR in a game
    "min_rbi_game": 5,        <- player had 5+ RBI in a game
    "shutout": true,          <- pitcher allowed 0 runs
    "min_k_game": 10,         <- pitcher struck out 10+
    "max_hits_allowed": 3,    <- pitcher allowed 3 or fewer hits
    "no_hitter": true,        <- no-hitter
    "limit": 50 }

━━━ ROUTING DECISION TREE ━━━

Career/season totals, awards, HOF, salaries? → lahman
Specific game results, play-by-play, game logs, individual game performances? → retrosheet

━━━ EXAMPLES ━━━
"most career home runs all time"                        → lahman
"Hall of Famers born in Dominican Republic"             → lahman
"Babe Ruth career stats"                                → lahman
"highest single season ERA ever"                        → lahman
"Yankees 2024 season results"                           → retrosheet search_games (team:NYA, year_from:2024, year_to:2024)
"4 hits and no runs in a game"                          → retrosheet advanced_search (min_hits_game:4, max_runs_game:0)
"no-hitters since 2010"                                 → retrosheet advanced_search (no_hitter:true, year_from:2010)
"complete game shutouts with 10+ strikeouts"            → retrosheet advanced_search (shutout:true, min_k_game:10)
"Babe Ruth game log 1927"                               → retrosheet player_gamelog (player_id:ruthba01, year_from:1927, year_to:1927)
"Aaron Judge games with 2+ HR in 2022"                 → retrosheet advanced_search (min_hr_game:2, year_from:2022, year_to:2022)
"Sandy Koufax 1965 pitching game log"                  → retrosheet player_pitching (player_id:koufasa01, year_from:1965, year_to:1965)
"Bob Gibson games with 10+ strikeouts"                  → retrosheet player_pitching (player_id:gibsobo01, min_so:10)
"Shohei Ohtani 2023 starts"                             → retrosheet player_pitching (player_id:ohtansh01, year_from:2023, year_to:2023)
"Yankees vs Red Sox games 1961"                         → retrosheet search_games (team:NYA, year_from:1961, year_to:1961)
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
            player_pitching_log,
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
                    player_id = pid,
                    year_from = params.get("year_from"),
                    year_to   = params.get("year_to"),
                    min_hits  = params.get("min_hits"),
                    min_hr    = params.get("min_hr"),
                    min_rbi   = params.get("min_rbi"),
                    limit     = min(params.get("limit", 100), 500),
                )

            elif action == "player_pitching":
                pid = params.get("player_id")
                if not pid:
                    raise HTTPException(status_code=400, detail="player_pitching requires player_id")
                results = player_pitching_log(
                    player_id = pid,
                    year_from = params.get("year_from"),
                    year_to   = params.get("year_to"),
                    min_so    = params.get("min_so"),
                    min_ip    = params.get("min_ip"),
                    limit     = min(params.get("limit", 100), 500),
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