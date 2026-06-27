"""
Retrosheet router — play-by-play and game logs for ALL completed games (1920–2025).
Covers everything except live in-progress games (handled by mlb_live.py).

Tables:
  retro_games   — one row per game
  retro_events  — one row per play (36 verified fields + derived event_num)
  retro_people  — Retrosheet player ID → full name (from BIOFILE)

Event codes (event_cd):
  2=Out  3=Strikeout  14=Walk  15=Int Walk  16=HBP
  20=Single  21=Double  22=Triple  23=Home Run

Hit values (hit_value):
  0=no hit  1=single  2=double  3=triple  4=home run

Destination codes (batter_dest, runner_*_dest):
  0=out  1=1B  2=2B  3=3B  4=scored(earned)  5=scored(unearned)  6=scored(team unearned)
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from db.database import query

router = APIRouter()

# ── event code lookup ─────────────────────────────────────────────────────────

EVENT_LABELS = {
    2:  "Out",
    3:  "Strikeout",
    6:  "Generic Out",
    14: "Walk",
    15: "Intentional Walk",
    16: "Hit by Pitch",
    20: "Single",
    21: "Double",
    22: "Triple",
    23: "Home Run",
}

FILTER_CODES = {
    "hits":   [20, 21, 22, 23],
    "hr":     [23],
    "so":     [3],
    "bb":     [14, 15],
    "walk":   [14, 15],
    "hbp":    [16],
    "single": [20],
    "double": [21],
    "triple": [22],
    "out":    [2],
}

# ── error helper ──────────────────────────────────────────────────────────────

def _retro_error(e):
    msg = str(e)
    if any(t in msg for t in ["retro_games", "retro_events", "retro_people"]):
        raise HTTPException(status_code=503,
            detail="Retrosheet data not loaded. Run scripts/import_retrosheet.py first.")
    raise e

# ── game search ───────────────────────────────────────────────────────────────

@router.get("/retro/games")
def search_games(
    team:       Optional[str] = None,
    year_from:  Optional[int] = None,
    year_to:    Optional[int] = None,
    date_from:  Optional[str] = None,
    date_to:    Optional[str] = None,
    min_runs:   Optional[int] = None,
    limit:      int           = Query(default=50, le=200),
):
    """Search historical games from Retrosheet (1920–2025)."""
    conditions = ["1=1"]
    params: dict = {}

    if team:
        conditions.append("(home_team = :team OR away_team = :team)")
        params["team"] = team.upper()
    if year_from:
        conditions.append("year >= :year_from")
        params["year_from"] = year_from
    if year_to:
        conditions.append("year <= :year_to")
        params["year_to"] = year_to
    if date_from:
        conditions.append("date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        conditions.append("date <= :date_to")
        params["date_to"] = date_to
    if min_runs is not None:
        conditions.append("(COALESCE(home_score,0) + COALESCE(away_score,0)) >= :min_runs")
        params["min_runs"] = min_runs

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            game_id, date, year,
            away_team, away_score, away_hits,
            home_team, home_score, home_hits,
            (COALESCE(home_score,0) + COALESCE(away_score,0)) AS total_runs,
            attendance, duration_mins,
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
        _retro_error(e)


# ── game play-by-play ─────────────────────────────────────────────────────────

@router.get("/retro/game/{game_id}/plays")
def game_plays(
    game_id: str,
    inning:  Optional[int] = None,
    event:   Optional[str] = None,
):
    """Full play-by-play for a historical game with player names."""
    conditions = ["e.game_id = :game_id"]
    params: dict = {"game_id": game_id.upper()}

    if inning:
        conditions.append("e.inning = :inning")
        params["inning"] = inning

    if event:
        codes = FILTER_CODES.get(event.lower())
        if codes:
            conditions.append(f"e.event_cd IN ({','.join(str(c) for c in codes)})")

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            e.event_num,
            e.inning,
            CASE e.batting_team
                WHEN '0' THEN g.away_team
                ELSE g.home_team
            END                                          AS batting_team,
            e.outs,
            e.balls,
            e.strikes,
            e.pitch_sequence,
            e.vis_score,
            e.home_score,
            COALESCE(bp.full_name, e.batter_id)         AS batter,
            e.batter_id,
            e.batter_hand,
            COALESCE(pp.full_name, e.pitcher_id)        AS pitcher,
            e.pitcher_id,
            e.pitcher_hand,
            COALESCE(r1.full_name, e.runner_1b)         AS runner_1b,
            COALESCE(r2.full_name, e.runner_2b)         AS runner_2b,
            COALESCE(r3.full_name, e.runner_3b)         AS runner_3b,
            e.play_text,
            e.event_cd,
            e.hit_value,
            e.ab_flag,
            e.sh_flag,
            e.sf_flag,
            e.outs_on_play,
            e.dp_flag,
            e.tp_flag,
            e.rbi,
            e.wp_flag,
            e.pb_flag,
            e.fielded_by,
            e.num_errors,
            e.batter_dest,
            e.runner_1b_dest,
            e.runner_2b_dest,
            e.runner_3b_dest,
            e.runs_scored
        FROM retro_events e
        JOIN retro_games g        ON e.game_id   = g.game_id
        LEFT JOIN retro_people bp ON e.batter_id = bp.retro_id
        LEFT JOIN retro_people pp ON e.pitcher_id = pp.retro_id
        LEFT JOIN retro_people r1 ON e.runner_1b = r1.retro_id
        LEFT JOIN retro_people r2 ON e.runner_2b = r2.retro_id
        LEFT JOIN retro_people r3 ON e.runner_3b = r3.retro_id
        WHERE {where}
        ORDER BY e.event_num
    """
    try:
        plays = query(sql, params)
    except Exception as ex:
        _retro_error(ex)

    for play in plays:
        play["event_type"] = EVENT_LABELS.get(play.get("event_cd"), "Play")

    game = query("SELECT * FROM retro_games WHERE game_id = :g",
                 {"g": game_id.upper()})
    return {
        "game":       game[0] if game else {},
        "play_count": len(plays),
        "plays":      plays,
    }


# ── player batting game log ───────────────────────────────────────────────────

@router.get("/retro/player/{player_id}/gamelog")
def player_gamelog(
    player_id: str,
    year_from: Optional[int] = None,
    year_to:   Optional[int] = None,
    min_hits:  Optional[int] = None,
    min_hr:    Optional[int] = None,
    min_rbi:   Optional[int] = None,
    limit:     int           = Query(default=100, le=500),
):
    """
    Game-by-game batting log for a player.
    Uses Retrosheet player IDs (e.g. mantm101 for Mickey Mantle).
    Aggregates all plate appearances per game from retro_events.
    """
    conditions = ["e.batter_id = :pid"]
    params: dict = {"pid": player_id}

    if year_from:
        conditions.append("g.year >= :year_from")
        params["year_from"] = year_from
    if year_to:
        conditions.append("g.year <= :year_to")
        params["year_to"] = year_to

    having = []
    if min_hits is not None:
        having.append("SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END) >= :min_hits")
        params["min_hits"] = min_hits
    if min_hr is not None:
        having.append("SUM(CASE WHEN e.event_cd = 23 THEN 1 ELSE 0 END) >= :min_hr")
        params["min_hr"] = min_hr
    if min_rbi is not None:
        having.append("SUM(COALESCE(e.rbi, 0)) >= :min_rbi")
        params["min_rbi"] = min_rbi

    where      = " AND ".join(conditions)
    having_sql = f"HAVING {' AND '.join(having)}" if having else ""

    sql = f"""
        SELECT
            g.date,
            g.year,
            CASE e.batting_team
                WHEN '0' THEN g.away_team
                ELSE g.home_team
            END                                                            AS team,
            CASE e.batting_team WHEN '0' THEN 'Away' ELSE 'Home' END      AS home_away,
            CASE e.batting_team
                WHEN '0' THEN g.home_team
                ELSE g.away_team
            END                                                            AS opponent,
            g.away_score,
            g.home_score,
            SUM(CASE WHEN e.ab_flag = 'T' THEN 1 ELSE 0 END)             AS ab,
            SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END)             AS hits,
            SUM(CASE WHEN e.event_cd = 20 THEN 1 ELSE 0 END)             AS singles,
            SUM(CASE WHEN e.event_cd = 21 THEN 1 ELSE 0 END)             AS doubles,
            SUM(CASE WHEN e.event_cd = 22 THEN 1 ELSE 0 END)             AS triples,
            SUM(CASE WHEN e.event_cd = 23 THEN 1 ELSE 0 END)             AS hr,
            SUM(COALESCE(e.rbi, 0))                                       AS rbi,
            SUM(CASE WHEN e.event_cd IN (14,15) THEN 1 ELSE 0 END)       AS walks,
            SUM(CASE WHEN e.event_cd = 3 THEN 1 ELSE 0 END)              AS strikeouts,
            SUM(COALESCE(e.runs_scored, 0))                               AS runs,
            SUM(CASE WHEN e.sh_flag = 'T' THEN 1 ELSE 0 END)             AS sac_hits,
            SUM(CASE WHEN e.sf_flag = 'T' THEN 1 ELSE 0 END)             AS sac_flies,
            e.game_id
        FROM retro_events e
        JOIN retro_games g ON e.game_id = g.game_id
        WHERE {where}
        GROUP BY
            e.game_id, g.date, g.year, e.batting_team,
            g.away_team, g.home_team, g.away_score, g.home_score
        {having_sql}
        ORDER BY g.date DESC
        LIMIT :limit
    """
    params["limit"] = limit
    try:
        return query(sql, params)
    except Exception as ex:
        _retro_error(ex)


# ── player pitching game log ──────────────────────────────────────────────────

@router.get("/retro/player/{player_id}/pitching")
def player_pitching_log(
    player_id: str,
    year_from: Optional[int]   = None,
    year_to:   Optional[int]   = None,
    min_so:    Optional[int]   = None,
    min_ip:    Optional[float] = None,
    limit:     int             = Query(default=100, le=500),
):
    """
    Game-by-game pitching log for a player.
    Uses Retrosheet player IDs (e.g. koufasa01 for Sandy Koufax).
    Aggregates all events where this player was the pitcher per game.
    """
    conditions = ["e.pitcher_id = :pid", "e.batter_event_fl = 'T'"]
    params: dict = {"pid": player_id}

    if year_from:
        conditions.append("g.year >= :year_from")
        params["year_from"] = year_from
    if year_to:
        conditions.append("g.year <= :year_to")
        params["year_to"] = year_to

    having = []
    if min_so is not None:
        having.append("SUM(CASE WHEN e.event_cd = 3 THEN 1 ELSE 0 END) >= :min_so")
        params["min_so"] = min_so
    if min_ip is not None:
        having.append("SUM(e.outs_on_play) / 3.0 >= :min_ip")
        params["min_ip"] = min_ip

    where      = " AND ".join(conditions)
    having_sql = f"HAVING {' AND '.join(having)}" if having else ""

    sql = f"""
        SELECT
            g.date,
            g.year,
            CASE e.batting_team
                WHEN '0' THEN g.home_team
                ELSE g.away_team
            END                                                            AS team,
            CASE e.batting_team WHEN '0' THEN 'Home' ELSE 'Away' END      AS home_away,
            CASE e.batting_team
                WHEN '0' THEN g.away_team
                ELSE g.home_team
            END                                                            AS opponent,
            g.away_score,
            g.home_score,
            ROUND((SUM(e.outs_on_play) / 3.0)::NUMERIC, 1)               AS ip,
            COUNT(DISTINCT e.event_num)                                    AS bf,
            SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END)             AS hits_allowed,
            SUM(COALESCE(e.runs_scored, 0))                               AS runs_allowed,
            SUM(CASE WHEN e.event_cd = 3 THEN 1 ELSE 0 END)              AS strikeouts,
            SUM(CASE WHEN e.event_cd IN (14,15) THEN 1 ELSE 0 END)       AS walks,
            SUM(CASE WHEN e.event_cd = 23 THEN 1 ELSE 0 END)             AS hr_allowed,
            SUM(CASE WHEN e.wp_flag = 'T' THEN 1 ELSE 0 END)             AS wild_pitches,
            SUM(CASE WHEN e.num_errors > 0 THEN e.num_errors ELSE 0 END) AS errors_behind,
            CASE
                WHEN g.winning_pitcher = e.pitcher_id THEN 'W'
                WHEN g.losing_pitcher  = e.pitcher_id THEN 'L'
                WHEN g.save_pitcher    = e.pitcher_id THEN 'S'
                ELSE ''
            END                                                            AS decision,
            e.game_id
        FROM retro_events e
        JOIN retro_games g ON e.game_id = g.game_id
        WHERE {where}
        GROUP BY
            e.game_id, e.pitcher_id, g.date, g.year, e.batting_team,
            g.away_team, g.home_team, g.away_score, g.home_score,
            g.winning_pitcher, g.losing_pitcher, g.save_pitcher
        {having_sql}
        ORDER BY g.date DESC
        LIMIT :limit
    """
    params["limit"] = limit
    try:
        return query(sql, params)
    except Exception as ex:
        _retro_error(ex)


# ── advanced search ───────────────────────────────────────────────────────────

@router.get("/retro/search")
def advanced_search(
    team:             Optional[str]  = None,
    year_from:        Optional[int]  = None,
    year_to:          Optional[int]  = None,
    min_hits_game:    Optional[int]  = None,
    max_runs_game:    Optional[int]  = None,
    min_hr_game:      Optional[int]  = None,
    min_rbi_game:     Optional[int]  = None,
    shutout:          Optional[bool] = None,
    no_hitter:        Optional[bool] = None,
    min_k_game:       Optional[int]  = None,
    max_hits_allowed: Optional[int]  = None,
    complete_game:    Optional[bool] = None,
    limit:            int            = Query(default=50, le=200),
):
    """
    Advanced game-level search derived entirely from retro_events + retro_games.
    Batting: find games where a player had X hits, Y HR, etc.
    Pitching: find shutouts, no-hitters, high strikeout games.
    """
    params: dict = {"limit": limit}

    is_batting  = any(v is not None for v in
        [min_hits_game, max_runs_game, min_hr_game, min_rbi_game])
    is_pitching = any(v is not None for v in
        [shutout, no_hitter, min_k_game, max_hits_allowed, complete_game])

    if is_batting:
        g_conds = ["1=1"]
        having  = []

        if team:
            g_conds.append("(g.home_team = :team OR g.away_team = :team)")
            params["team"] = team.upper()
        if year_from:
            g_conds.append("g.year >= :year_from")
            params["year_from"] = year_from
        if year_to:
            g_conds.append("g.year <= :year_to")
            params["year_to"] = year_to
        if min_hits_game is not None:
            having.append("SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END) >= :min_hits")
            params["min_hits"] = min_hits_game
        if max_runs_game is not None:
            having.append("SUM(COALESCE(e.runs_scored, 0)) <= :max_runs")
            params["max_runs"] = max_runs_game
        if min_hr_game is not None:
            having.append("SUM(CASE WHEN e.event_cd = 23 THEN 1 ELSE 0 END) >= :min_hr_game")
            params["min_hr_game"] = min_hr_game
        if min_rbi_game is not None:
            having.append("SUM(COALESCE(e.rbi, 0)) >= :min_rbi_game")
            params["min_rbi_game"] = min_rbi_game

        where      = " AND ".join(g_conds)
        having_sql = f"HAVING {' AND '.join(having)}" if having else ""

        sql = f"""
            SELECT
                g.date,
                g.year,
                CASE e.batting_team
                    WHEN '0' THEN g.away_team
                    ELSE g.home_team
                END                                                        AS team,
                COALESCE(rp.full_name, e.batter_id)                       AS player_name,
                e.batter_id                                                AS player_id,
                CASE e.batting_team
                    WHEN '0' THEN g.home_team
                    ELSE g.away_team
                END                                                        AS opponent,
                g.away_team, g.away_score,
                g.home_team, g.home_score,
                SUM(CASE WHEN e.ab_flag = 'T' THEN 1 ELSE 0 END)         AS ab,
                SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END)         AS hits,
                SUM(CASE WHEN e.event_cd = 21 THEN 1 ELSE 0 END)         AS doubles,
                SUM(CASE WHEN e.event_cd = 22 THEN 1 ELSE 0 END)         AS triples,
                SUM(CASE WHEN e.event_cd = 23 THEN 1 ELSE 0 END)         AS hr,
                SUM(COALESCE(e.rbi, 0))                                   AS rbi,
                SUM(COALESCE(e.runs_scored, 0))                           AS runs,
                SUM(CASE WHEN e.event_cd IN (14,15) THEN 1 ELSE 0 END)   AS walks,
                SUM(CASE WHEN e.event_cd = 3 THEN 1 ELSE 0 END)          AS strikeouts,
                e.game_id
            FROM retro_events e
            JOIN retro_games g        ON e.game_id   = g.game_id
            LEFT JOIN retro_people rp ON e.batter_id = rp.retro_id
            WHERE {where}
            GROUP BY
                e.game_id, e.batter_id, g.date, g.year,
                e.batting_team, g.away_team, g.home_team,
                g.away_score, g.home_score, rp.full_name
            {having_sql}
            ORDER BY g.date DESC
            LIMIT :limit
        """

    elif is_pitching:
        g_conds = ["1=1"]
        having  = []

        if team:
            g_conds.append("(g.home_team = :team OR g.away_team = :team)")
            params["team"] = team.upper()
        if year_from:
            g_conds.append("g.year >= :year_from")
            params["year_from"] = year_from
        if year_to:
            g_conds.append("g.year <= :year_to")
            params["year_to"] = year_to
        if shutout:
            having.append("SUM(COALESCE(e.runs_scored, 0)) = 0")
        if no_hitter:
            having.append("SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END) = 0")
        if min_k_game is not None:
            having.append("SUM(CASE WHEN e.event_cd = 3 THEN 1 ELSE 0 END) >= :min_k")
            params["min_k"] = min_k_game
        if max_hits_allowed is not None:
            having.append("SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END) <= :max_h")
            params["max_h"] = max_hits_allowed

        where      = " AND ".join(g_conds)
        having_sql = f"HAVING {' AND '.join(having)}" if having else ""

        sql = f"""
            SELECT
                g.date,
                g.year,
                g.away_team, g.away_score,
                g.home_team, g.home_score,
                g.winning_pitcher,
                COALESCE(rp.full_name, g.winning_pitcher)                  AS winning_pitcher_name,
                SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END)          AS hits_allowed,
                SUM(COALESCE(e.runs_scored, 0))                            AS runs_allowed,
                SUM(CASE WHEN e.event_cd = 3 THEN 1 ELSE 0 END)           AS strikeouts,
                SUM(CASE WHEN e.event_cd IN (14,15) THEN 1 ELSE 0 END)    AS walks,
                SUM(CASE WHEN e.num_errors > 0 THEN e.num_errors ELSE 0 END) AS errors,
                g.game_id
            FROM retro_events e
            JOIN retro_games g        ON e.game_id          = g.game_id
            LEFT JOIN retro_people rp ON g.winning_pitcher  = rp.retro_id
            WHERE {where}
            GROUP BY
                g.game_id, e.batting_team, g.date, g.year,
                g.away_team, g.away_score,
                g.home_team, g.home_score,
                g.winning_pitcher, rp.full_name
            {having_sql}
            ORDER BY g.date DESC
            LIMIT :limit
        """

    else:
        g_conds = ["1=1"]
        if team:
            g_conds.append("(home_team = :team OR away_team = :team)")
            params["team"] = team.upper()
        if year_from:
            g_conds.append("year >= :year_from")
            params["year_from"] = year_from
        if year_to:
            g_conds.append("year <= :year_to")
            params["year_to"] = year_to

        where = " AND ".join(g_conds)
        sql = f"""
            SELECT
                game_id, date, year,
                away_team, away_score, away_hits,
                home_team, home_score, home_hits,
                (COALESCE(home_score,0) + COALESCE(away_score,0)) AS total_runs,
                attendance, duration_mins,
                winning_pitcher, losing_pitcher, save_pitcher
            FROM retro_games
            WHERE {where}
            ORDER BY date DESC
            LIMIT :limit
        """

    try:
        return query(sql, params)
    except Exception as ex:
        _retro_error(ex)