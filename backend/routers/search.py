from fastapi import APIRouter, Query
from typing import Optional
from db.database import query

router = APIRouter()

@router.get("/search/batting")
def search_batting(
    player_name:   Optional[str]   = None,
    team:          Optional[str]   = None,
    year_from:     Optional[int]   = None,
    year_to:       Optional[int]   = None,
    bats:          Optional[str]   = None,   # L, R, B
    # Counting stats — min/max
    min_g:         Optional[int]   = None,
    min_ab:        Optional[int]   = None,
    min_hr:        Optional[int]   = None,   max_hr:  Optional[int]   = None,
    min_hits:      Optional[int]   = None,
    min_rbi:       Optional[int]   = None,
    min_sb:        Optional[int]   = None,
    min_bb:        Optional[int]   = None,
    min_so:        Optional[int]   = None,   max_so:  Optional[int]   = None,
    min_runs:      Optional[int]   = None,
    min_2b:        Optional[int]   = None,
    min_3b:        Optional[int]   = None,
    # Rate stats
    min_avg:       Optional[float] = None,   max_avg: Optional[float] = None,
    min_obp:       Optional[float] = None,
    min_slg:       Optional[float] = None,
    min_ops:       Optional[float] = None,
    # Sort
    sort_by:       Optional[str]   = "year",
    sort_dir:      Optional[str]   = "desc",
    limit:         int             = Query(default=50, le=200),
):
    conditions = ["1=1", "b.AB > 0"]
    params = {}

    if player_name:
        conditions.append("LOWER(p.nameFirst || ' ' || p.nameLast) LIKE :name")
        params["name"] = f"%{player_name.lower()}%"
    if team:
        conditions.append("b.teamID = :team")
        params["team"] = team.upper()
    if year_from:
        conditions.append("b.yearID >= :year_from")
        params["year_from"] = year_from
    if year_to:
        conditions.append("b.yearID <= :year_to")
        params["year_to"] = year_to
    if bats:
        conditions.append("p.bats = :bats")
        params["bats"] = bats.upper()
    if min_g is not None:
        conditions.append("b.G >= :min_g"); params["min_g"] = min_g
    if min_ab is not None:
        conditions.append("b.AB >= :min_ab"); params["min_ab"] = min_ab
    if min_hr is not None:
        conditions.append("b.HR >= :min_hr"); params["min_hr"] = min_hr
    if max_hr is not None:
        conditions.append("b.HR <= :max_hr"); params["max_hr"] = max_hr
    if min_hits is not None:
        conditions.append("b.H >= :min_hits"); params["min_hits"] = min_hits
    if min_rbi is not None:
        conditions.append("b.RBI >= :min_rbi"); params["min_rbi"] = min_rbi
    if min_sb is not None:
        conditions.append("b.SB >= :min_sb"); params["min_sb"] = min_sb
    if min_bb is not None:
        conditions.append("b.BB >= :min_bb"); params["min_bb"] = min_bb
    if min_so is not None:
        conditions.append("b.SO >= :min_so"); params["min_so"] = min_so
    if max_so is not None:
        conditions.append("b.SO <= :max_so"); params["max_so"] = max_so
    if min_runs is not None:
        conditions.append("b.R >= :min_runs"); params["min_runs"] = min_runs
    if min_2b is not None:
        conditions.append("b.\"2B\" >= :min_2b"); params["min_2b"] = min_2b
    if min_3b is not None:
        conditions.append("b.\"3B\" >= :min_3b"); params["min_3b"] = min_3b

    avg_expr  = "CAST(b.H AS FLOAT) / NULLIF(b.AB, 0)"
    obp_expr  = "CAST(b.H + COALESCE(b.BB,0) + COALESCE(b.HBP,0) AS FLOAT) / NULLIF(b.AB + COALESCE(b.BB,0) + COALESCE(b.HBP,0) + COALESCE(b.SF,0), 0)"
    slg_expr  = "CAST(b.H + COALESCE(b.\"2B\",0) + 2*COALESCE(b.\"3B\",0) + 3*b.HR AS FLOAT) / NULLIF(b.AB, 0)"
    ops_expr  = f"({obp_expr}) + ({slg_expr})"

    if min_avg is not None:
        conditions.append(f"({avg_expr}) >= :min_avg"); params["min_avg"] = min_avg
    if max_avg is not None:
        conditions.append(f"({avg_expr}) <= :max_avg"); params["max_avg"] = max_avg
    if min_obp is not None:
        conditions.append(f"({obp_expr}) >= :min_obp"); params["min_obp"] = min_obp
    if min_slg is not None:
        conditions.append(f"({slg_expr}) >= :min_slg"); params["min_slg"] = min_slg
    if min_ops is not None:
        conditions.append(f"({ops_expr}) >= :min_ops"); params["min_ops"] = min_ops

    sort_map = {
        "year": "b.yearID", "hr": "b.HR", "avg": avg_expr, "rbi": "b.RBI",
        "hits": "b.H", "sb": "b.SB", "obp": obp_expr, "slg": slg_expr,
        "ops": ops_expr, "bb": "b.BB", "so": "b.SO", "runs": "b.R",
    }
    order_col = sort_map.get(sort_by or "year", "b.yearID")
    direction = "ASC" if (sort_dir or "desc").lower() == "asc" else "DESC"

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            p.nameFirst || ' ' || p.nameLast AS player_name,
            p.playerID,
            b.yearID  AS year,
            b.teamID  AS team,
            p.bats,
            b.G       AS games,
            b.AB      AS at_bats,
            b.R       AS runs,
            b.H       AS hits,
            b."2B"    AS doubles,
            b."3B"    AS triples,
            b.HR      AS home_runs,
            b.RBI     AS rbi,
            b.SB      AS stolen_bases,
            b.CS      AS caught_stealing,
            b.BB      AS walks,
            b.SO      AS strikeouts,
            b.HBP     AS hbp,
            b.SF      AS sac_flies,
            b.GIDP    AS gidp,
            ROUND({avg_expr}, 3)  AS avg,
            ROUND({obp_expr}, 3)  AS obp,
            ROUND({slg_expr}, 3)  AS slg,
            ROUND({ops_expr}, 3)  AS ops
        FROM Batting b
        JOIN People p ON b.playerID = p.playerID
        WHERE {where}
        ORDER BY {order_col} {direction}
        LIMIT :limit
    """
    params["limit"] = limit
    return query(sql, params)


@router.get("/search/pitching")
def search_pitching(
    player_name:   Optional[str]   = None,
    team:          Optional[str]   = None,
    year_from:     Optional[int]   = None,
    year_to:       Optional[int]   = None,
    throws:        Optional[str]   = None,   # L, R
    starter:       Optional[str]   = None,   # "yes" = GS>0, "no" = GS=0 (relievers)
    min_g:         Optional[int]   = None,
    min_gs:        Optional[int]   = None,
    min_wins:      Optional[int]   = None,
    max_losses:    Optional[int]   = None,
    min_sv:        Optional[int]   = None,
    max_era:       Optional[float] = None,   min_era: Optional[float] = None,
    min_so:        Optional[int]   = None,
    max_bb:        Optional[int]   = None,
    min_ip:        Optional[float] = None,
    min_cg:        Optional[int]   = None,
    min_sho:       Optional[int]   = None,
    max_whip:      Optional[float] = None,
    min_k9:        Optional[float] = None,   # K/9
    sort_by:       Optional[str]   = "year",
    sort_dir:      Optional[str]   = "desc",
    limit:         int             = Query(default=50, le=200),
):
    conditions = ["1=1", "pt.IPouts > 0"]
    params = {}

    if player_name:
        conditions.append("LOWER(p.nameFirst || ' ' || p.nameLast) LIKE :name")
        params["name"] = f"%{player_name.lower()}%"
    if team:
        conditions.append("pt.teamID = :team"); params["team"] = team.upper()
    if year_from:
        conditions.append("pt.yearID >= :year_from"); params["year_from"] = year_from
    if year_to:
        conditions.append("pt.yearID <= :year_to"); params["year_to"] = year_to
    if throws:
        conditions.append("p.throws = :throws"); params["throws"] = throws.upper()
    if starter == "yes":
        conditions.append("pt.GS > 0")
    elif starter == "no":
        conditions.append("(pt.GS = 0 OR pt.GS IS NULL)")
    if min_g is not None:
        conditions.append("pt.G >= :min_g"); params["min_g"] = min_g
    if min_gs is not None:
        conditions.append("pt.GS >= :min_gs"); params["min_gs"] = min_gs
    if min_wins is not None:
        conditions.append("pt.W >= :min_wins"); params["min_wins"] = min_wins
    if max_losses is not None:
        conditions.append("pt.L <= :max_losses"); params["max_losses"] = max_losses
    if min_sv is not None:
        conditions.append("pt.SV >= :min_sv"); params["min_sv"] = min_sv
    if max_era is not None:
        conditions.append("pt.ERA <= :max_era"); params["max_era"] = max_era
    if min_era is not None:
        conditions.append("pt.ERA >= :min_era"); params["min_era"] = min_era
    if min_so is not None:
        conditions.append("pt.SO >= :min_so"); params["min_so"] = min_so
    if max_bb is not None:
        conditions.append("pt.BB <= :max_bb"); params["max_bb"] = max_bb
    if min_ip is not None:
        conditions.append("CAST(pt.IPouts AS FLOAT)/3 >= :min_ip"); params["min_ip"] = min_ip
    if min_cg is not None:
        conditions.append("pt.CG >= :min_cg"); params["min_cg"] = min_cg
    if min_sho is not None:
        conditions.append("pt.SHO >= :min_sho"); params["min_sho"] = min_sho

    ip_expr   = "CAST(pt.IPouts AS FLOAT) / 3"
    whip_expr = f"CAST(pt.H + pt.BB AS FLOAT) / NULLIF(({ip_expr}), 0)"
    k9_expr   = f"pt.SO * 9.0 / NULLIF(({ip_expr}), 0)"

    if max_whip is not None:
        conditions.append(f"({whip_expr}) <= :max_whip"); params["max_whip"] = max_whip
    if min_k9 is not None:
        conditions.append(f"({k9_expr}) >= :min_k9"); params["min_k9"] = min_k9

    sort_map = {
        "year": "pt.yearID", "era": "pt.ERA", "wins": "pt.W", "so": "pt.SO",
        "sv": "pt.SV", "ip": ip_expr, "whip": whip_expr, "k9": k9_expr,
    }
    order_col = sort_map.get(sort_by or "year", "pt.yearID")
    direction = "ASC" if (sort_dir or "desc").lower() == "asc" else "DESC"

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            p.nameFirst || ' ' || p.nameLast AS player_name,
            p.playerID,
            pt.yearID  AS year,
            pt.teamID  AS team,
            p.throws,
            pt.W       AS wins,
            pt.L       AS losses,
            pt.G       AS games,
            pt.GS      AS games_started,
            pt.CG      AS complete_games,
            pt.SHO     AS shutouts,
            pt.SV      AS saves,
            ROUND({ip_expr}, 1)   AS innings_pitched,
            pt.H       AS hits_allowed,
            pt.ER      AS earned_runs,
            pt.HR      AS hr_allowed,
            pt.BB      AS walks,
            pt.SO      AS strikeouts,
            pt.HBP     AS hbp,
            pt.WP      AS wild_pitches,
            ROUND(pt.ERA, 2)      AS era,
            ROUND({whip_expr}, 3) AS whip,
            ROUND({k9_expr}, 1)   AS k_per_9
        FROM Pitching pt
        JOIN People p ON pt.playerID = p.playerID
        WHERE {where}
        ORDER BY {order_col} {direction}
        LIMIT :limit
    """
    params["limit"] = limit
    return query(sql, params)


@router.get("/search/fielding")
def search_fielding(
    player_name: Optional[str] = None,
    team:        Optional[str] = None,
    year_from:   Optional[int] = None,
    year_to:     Optional[int] = None,
    position:    Optional[str] = None,
    min_g:       Optional[int] = None,
    max_errors:  Optional[int] = None,
    limit:       int           = Query(default=50, le=200),
):
    conditions = ["1=1"]
    params = {}
    if player_name:
        conditions.append("LOWER(p.nameFirst || ' ' || p.nameLast) LIKE :name")
        params["name"] = f"%{player_name.lower()}%"
    if team:
        conditions.append("f.teamID = :team"); params["team"] = team.upper()
    if year_from:
        conditions.append("f.yearID >= :year_from"); params["year_from"] = year_from
    if year_to:
        conditions.append("f.yearID <= :year_to"); params["year_to"] = year_to
    if position:
        conditions.append("f.POS = :pos"); params["pos"] = position.upper()
    if min_g is not None:
        conditions.append("f.G >= :min_g"); params["min_g"] = min_g
    if max_errors is not None:
        conditions.append("f.E <= :max_errors"); params["max_errors"] = max_errors

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            p.nameFirst || ' ' || p.nameLast AS player_name,
            p.playerID,
            f.yearID AS year,
            f.teamID AS team,
            f.POS    AS position,
            f.G      AS games,
            f.GS     AS games_started,
            f.PO     AS putouts,
            f.A      AS assists,
            f.E      AS errors,
            f.DP     AS double_plays,
            ROUND(CAST(f.PO + f.A AS FLOAT) / NULLIF(f.PO + f.A + f.E, 0), 3) AS fielding_pct
        FROM Fielding f
        JOIN People p ON f.playerID = p.playerID
        WHERE {where}
        ORDER BY f.yearID DESC, f.G DESC
        LIMIT :limit
    """
    params["limit"] = limit
    return query(sql, params)


@router.get("/teams")
def get_teams():
    sql = "SELECT DISTINCT teamID FROM Teams ORDER BY teamID"
    return [r["teamID"] for r in query(sql)]

@router.get("/years")
def get_years():
    sql = "SELECT MIN(yearID) as min_year, MAX(yearID) as max_year FROM Batting"
    return query(sql)[0]
