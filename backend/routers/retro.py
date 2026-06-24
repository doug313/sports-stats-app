"""
Retrosheet router — play-by-play and game logs for ALL completed games (1910–2025).
Covers everything except live in-progress games (handled by mlb_live.py).
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from db.database import query

router = APIRouter()

# ── event code lookup ─────────────────────────────────────────────────────────
# Retrosheet cwevent event_cd values
EVENT_CODES = {
    2:  "Out",
    3:  "Strikeout",
    14: "Walk",
    15: "Intentional Walk",
    16: "Hit by Pitch",
    20: "Single",
    21: "Double",
    22: "Triple",
    23: "Home Run",
    24: "Missing Play",
}

REVERSE_EVENT = {v.lower(): k for k, v in EVENT_CODES.items()}
REVERSE_EVENT.update({
    "hr": 23, "single": 20, "double": 21, "triple": 22,
    "so": 3, "k": 3, "bb": 14, "walk": 14, "hbp": 16,
    "out": 2, "hits": [20, 21, 22, 23],
})


# ── game search ───────────────────────────────────────────────────────────────

@router.get("/retro/games")
def search_games(
    team:       Optional[str] = None,
    year_from:  Optional[int] = None,
    year_to:    Optional[int] = None,
    date_from:  Optional[str] = None,   # YYYY-MM-DD
    date_to:    Optional[str] = None,
    min_runs:   Optional[int] = None,   # total runs in game
    park:       Optional[str] = None,
    limit:      int           = Query(default=50, le=200),
):
    """Search historical games from Retrosheet (1910–2007)."""
    conditions = ["1=1"]
    params: dict = {}

    if team:
        conditions.append("(home_team = :team OR away_team = :team)")
        params["team"] = team.upper()
    if year_from:
        conditions.append("year >= :year_from"); params["year_from"] = year_from
    if year_to:
        conditions.append("year <= :year_to"); params["year_to"] = year_to
    if date_from:
        conditions.append("date >= :date_from"); params["date_from"] = date_from
    if date_to:
        conditions.append("date <= :date_to"); params["date_to"] = date_to
    if min_runs is not None:
        conditions.append("(home_score + away_score) >= :min_runs")
        params["min_runs"] = min_runs
    if park:
        conditions.append("park_id = :park"); params["park"] = park.upper()

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            game_id, date, year,
            away_team, away_score,
            home_team, home_score,
            (home_score + away_score) AS total_runs,
            park_id, attendance, duration_mins,
            winning_pitcher, losing_pitcher, save_pitcher
        FROM retro_games
        WHERE {where}
        ORDER BY date DESC
        LIMIT :limit
    """
    params["limit"] = limit
    try:
        return query(sql, params)
    except Exception as e:
        if "retro_games" in str(e):
            raise HTTPException(status_code=503,
                detail="Retrosheet data not loaded. Run scripts/import_retrosheet.py first.")
        raise


# ── game play-by-play ─────────────────────────────────────────────────────────

@router.get("/retro/game/{game_id}/plays")
def game_plays(
    game_id: str,
    inning:  Optional[int] = None,
    event:   Optional[str] = None,   # "hits", "hr", "so", "bb", "single" etc.
):
    """Full play-by-play for a historical game."""
    conditions = ["e.game_id = :game_id"]
    params: dict = {"game_id": game_id.upper()}

    if inning:
        conditions.append("e.inning = :inning"); params["inning"] = inning

    if event:
        ev = event.lower()
        if ev == "hits":
            conditions.append("e.event_cd IN (20, 21, 22, 23)")
        elif ev in REVERSE_EVENT:
            cd = REVERSE_EVENT[ev]
            if isinstance(cd, list):
                conditions.append(f"e.event_cd IN ({','.join(str(c) for c in cd)})")
            else:
                conditions.append("e.event_cd = :event_cd"); params["event_cd"] = cd

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            e.event_num,
            e.inning,
            CASE e.batting_team WHEN '0' THEN g.away_team ELSE g.home_team END AS batting_team,
            e.outs,
            e.balls,
            e.strikes,
            bp.nameFirst || ' ' || bp.nameLast AS batter,
            pp.nameFirst || ' ' || pp.nameLast AS pitcher,
            e.event_cd,
            COALESCE('{{"2":"Out","3":"Strikeout","14":"Walk","15":"Int Walk",
                "16":"HBP","20":"Single","21":"Double","22":"Triple","23":"Home Run"}}
                '::json->>e.event_cd::text, 'Play') AS event_type,
            e.hit_value,
            e.rbi,
            e.runs_scored,
            e.play_text
        FROM retro_events e
        JOIN retro_games g ON e.game_id = g.game_id
        LEFT JOIN People bp ON e.batter_id  = bp.playerID
        LEFT JOIN People pp ON e.pitcher_id = pp.playerID
        WHERE {where}
        ORDER BY e.event_num
    """
    try:
        plays = query(sql, params)
    except Exception as ex:
        if "retro_events" in str(ex):
            raise HTTPException(status_code=503,
                detail="Retrosheet data not loaded. Run scripts/import_retrosheet.py first.")
        raise

    # Get game header
    game = query("SELECT * FROM retro_games WHERE game_id = :g", {"g": game_id.upper()})
    return {
        "game": game[0] if game else {},
        "play_count": len(plays),
        "plays": plays,
    }


# ── player game log ───────────────────────────────────────────────────────────

@router.get("/retro/player/{player_id}/gamelog")
def player_gamelog(
    player_id:  str,
    year_from:  Optional[int] = None,
    year_to:    Optional[int] = None,
    stat_type:  str = Query(default="batting", regex="^(batting|pitching)$"),
    min_hits:   Optional[int] = None,
    min_hr:     Optional[int] = None,
    min_rbi:    Optional[int] = None,
    min_so:     Optional[int] = None,  # pitching
    limit:      int           = Query(default=100, le=500),
):
    """Game-by-game log for a player from Retrosheet."""
    if stat_type == "batting":
        conditions = ["b.player_id = :pid"]
        params: dict = {"pid": player_id}
        if year_from:
            conditions.append("g.year >= :year_from"); params["year_from"] = year_from
        if year_to:
            conditions.append("g.year <= :year_to"); params["year_to"] = year_to
        if min_hits is not None:
            conditions.append("b.h >= :min_hits"); params["min_hits"] = min_hits
        if min_hr is not None:
            conditions.append("b.hr >= :min_hr"); params["min_hr"] = min_hr
        if min_rbi is not None:
            conditions.append("b.rbi >= :min_rbi"); params["min_rbi"] = min_rbi
        where = " AND ".join(conditions)
        sql = f"""
            SELECT
                g.date, g.year, b.team,
                CASE b.home_away WHEN '0' THEN 'Away' ELSE 'Home' END AS home_away,
                CASE b.home_away
                    WHEN '0' THEN g.home_team
                    ELSE g.away_team
                END AS opponent,
                g.away_score, g.home_score,
                b.ab, b.r, b.h, b.doubles, b.triples, b.hr,
                b.rbi, b.bb, b.so, b.sb,
                ROUND(CAST(b.h AS FLOAT) / NULLIF(b.ab, 0), 3) AS avg,
                b.game_id
            FROM retro_batting b
            JOIN retro_games g ON b.game_id = g.game_id
            WHERE {where}
            ORDER BY g.date DESC
            LIMIT :limit
        """
        params["limit"] = limit
    else:
        conditions = ["p.player_id = :pid"]
        params = {"pid": player_id}
        if year_from:
            conditions.append("g.year >= :year_from"); params["year_from"] = year_from
        if year_to:
            conditions.append("g.year <= :year_to"); params["year_to"] = year_to
        if min_so is not None:
            conditions.append("p.so >= :min_so"); params["min_so"] = min_so
        where = " AND ".join(conditions)
        sql = f"""
            SELECT
                g.date, g.year, p.team,
                CASE p.home_away WHEN '0' THEN 'Away' ELSE 'Home' END AS home_away,
                CASE p.home_away
                    WHEN '0' THEN g.home_team
                    ELSE g.away_team
                END AS opponent,
                ROUND(CAST(p.outs AS FLOAT) / 3, 1) AS ip,
                p.bf, p.h, p.r, p.er, p.hr,
                p.bb, p.so, p.wp,
                CASE WHEN p.win  THEN 'W'
                     WHEN p.loss THEN 'L'
                     WHEN p.save THEN 'S'
                     ELSE '' END AS decision,
                ROUND(CAST(p.er * 27 AS FLOAT) / NULLIF(p.outs, 0), 2) AS era,
                p.game_id
            FROM retro_pitching p
            JOIN retro_games g ON p.game_id = g.game_id
            WHERE {where}
            ORDER BY g.date DESC
            LIMIT :limit
        """
        params["limit"] = limit

    try:
        return query(sql, params)
    except Exception as ex:
        if "retro_" in str(ex):
            raise HTTPException(status_code=503,
                detail="Retrosheet data not loaded. Run scripts/import_retrosheet.py first.")
        raise


# ── advanced game search ──────────────────────────────────────────────────────

@router.get("/retro/search")
def advanced_search(
    # game-level filters
    team:           Optional[str] = None,
    year_from:      Optional[int] = None,
    year_to:        Optional[int] = None,
    # batting performance in a game
    min_hits_game:  Optional[int] = None,   # "4 hits in a game"
    max_runs_game:  Optional[int] = None,   # "and no runs"
    min_hr_game:    Optional[int] = None,
    min_rbi_game:   Optional[int] = None,
    # pitching performance in a game
    complete_game:  Optional[bool] = None,
    shutout:        Optional[bool] = None,
    min_k_game:     Optional[int]  = None,
    max_hits_allowed: Optional[int] = None,
    no_hitter:      Optional[bool] = None,
    limit:          int            = Query(default=50, le=200),
):
    """
    Advanced game-level search — the heart of Retrosheet queries.
    'Find games where a player had 4 hits and the team scored 0 runs'
    'Find complete game shutouts with 10+ strikeouts'
    'Find no-hitters'
    """
    params: dict = {"limit": limit}

    if min_hits_game is not None or max_runs_game is not None or \
       min_hr_game is not None or min_rbi_game is not None:
        # Batting game search
        bat_conditions = ["1=1"]
        if team:
            bat_conditions.append("b.team = :team"); params["team"] = team.upper()
        if year_from:
            bat_conditions.append("g.year >= :year_from"); params["year_from"] = year_from
        if year_to:
            bat_conditions.append("g.year <= :year_to"); params["year_to"] = year_to
        if min_hits_game is not None:
            bat_conditions.append("b.h >= :min_hits"); params["min_hits"] = min_hits_game
        if max_runs_game is not None:
            bat_conditions.append("b.r <= :max_runs"); params["max_runs"] = max_runs_game
        if min_hr_game is not None:
            bat_conditions.append("b.hr >= :min_hr_game"); params["min_hr_game"] = min_hr_game
        if min_rbi_game is not None:
            bat_conditions.append("b.rbi >= :min_rbi_game"); params["min_rbi_game"] = min_rbi_game

        where = " AND ".join(bat_conditions)
        sql = f"""
            SELECT
                g.date, g.year, b.team,
                p2.nameFirst || ' ' || p2.nameLast AS player_name,
                b.player_id,
                CASE b.home_away WHEN '0' THEN g.home_team ELSE g.away_team END AS opponent,
                g.away_team, g.away_score, g.home_team, g.home_score,
                b.ab, b.r, b.h, b.doubles, b.triples, b.hr, b.rbi,
                b.bb, b.so, b.sb, b.game_id
            FROM retro_batting b
            JOIN retro_games g  ON b.game_id   = g.game_id
            LEFT JOIN People p2 ON b.player_id = p2.playerID
            WHERE {where}
            ORDER BY g.date DESC
            LIMIT :limit
        """

    elif complete_game or shutout or min_k_game or max_hits_allowed is not None or no_hitter:
        # Pitching game search
        pit_conditions = ["1=1"]
        if team:
            pit_conditions.append("p.team = :team"); params["team"] = team.upper()
        if year_from:
            pit_conditions.append("g.year >= :year_from"); params["year_from"] = year_from
        if year_to:
            pit_conditions.append("g.year <= :year_to"); params["year_to"] = year_to
        if complete_game:
            pit_conditions.append("p.win = true OR p.loss = true")  # started and finished
            pit_conditions.append("CAST(p.outs AS FLOAT)/3 >= 8.0")
        if shutout:
            pit_conditions.append("p.r = 0")
            pit_conditions.append("CAST(p.outs AS FLOAT)/3 >= 8.0")
        if no_hitter:
            pit_conditions.append("p.h = 0")
            pit_conditions.append("CAST(p.outs AS FLOAT)/3 >= 8.0")
        if min_k_game is not None:
            pit_conditions.append("p.so >= :min_k"); params["min_k"] = min_k_game
        if max_hits_allowed is not None:
            pit_conditions.append("p.h <= :max_h"); params["max_h"] = max_hits_allowed

        where = " AND ".join(pit_conditions)
        sql = f"""
            SELECT
                g.date, g.year, p.team,
                p2.nameFirst || ' ' || p2.nameLast AS player_name,
                p.player_id,
                CASE p.home_away WHEN '0' THEN g.home_team ELSE g.away_team END AS opponent,
                g.away_team, g.away_score, g.home_team, g.home_score,
                ROUND(CAST(p.outs AS FLOAT)/3, 1) AS ip,
                p.h AS hits_allowed, p.r AS runs, p.er, p.bb, p.so,
                CASE WHEN p.win  THEN 'W'
                     WHEN p.loss THEN 'L'
                     WHEN p.save THEN 'S' ELSE '' END AS decision,
                p.game_id
            FROM retro_pitching p
            JOIN retro_games g  ON p.game_id   = g.game_id
            LEFT JOIN People p2 ON p.player_id = p2.playerID
            WHERE {where}
            ORDER BY g.date DESC
            LIMIT :limit
        """
    else:
        # General game search
        g_conditions = ["1=1"]
        if team:
            g_conditions.append("(home_team = :team OR away_team = :team)")
            params["team"] = team.upper()
        if year_from:
            g_conditions.append("year >= :year_from"); params["year_from"] = year_from
        if year_to:
            g_conditions.append("year <= :year_to"); params["year_to"] = year_to
        where = " AND ".join(g_conditions)
        sql = f"""
            SELECT * FROM retro_games
            WHERE {where}
            ORDER BY date DESC
            LIMIT :limit
        """

    try:
        return query(sql, params)
    except Exception as ex:
        if "retro_" in str(ex):
            raise HTTPException(status_code=503,
                detail="Retrosheet data not loaded. Run scripts/import_retrosheet.py first.")
        raise
