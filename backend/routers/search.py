from fastapi import APIRouter, Query
from typing import Optional
from db.database import query

router = APIRouter()

TEAM_NAME_MAP = {
    "yankees": "NYA", "new york yankees": "NYA",
    "mets": "NYN", "new york mets": "NYN",
    "red sox": "BOS", "boston red sox": "BOS",
    "dodgers": "LAN", "los angeles dodgers": "LAN",
    "giants": "SFN", "san francisco giants": "SFN",
    "cubs": "CHN", "chicago cubs": "CHN",
    "white sox": "CHA", "chicago white sox": "CHA",
    "cardinals": "SLN", "st louis cardinals": "SLN",
    "st. louis cardinals": "SLN",
    "braves": "ATL", "atlanta braves": "ATL",
    "phillies": "PHI", "philadelphia phillies": "PHI",
    "astros": "HOU", "houston astros": "HOU",
    "rangers": "TEX", "texas rangers": "TEX",
    "mariners": "SEA", "seattle mariners": "SEA",
    "padres": "SDN", "san diego padres": "SDN",
    "angels": "ANA", "los angeles angels": "ANA",
    "athletics": "OAK", "oakland athletics": "OAK", "as": "OAK",
    "tigers": "DET", "detroit tigers": "DET",
    "twins": "MIN", "minnesota twins": "MIN",
    "royals": "KCA", "kansas city royals": "KCA",
    "orioles": "BAL", "baltimore orioles": "BAL",
    "blue jays": "TOR", "toronto blue jays": "TOR",
    "rays": "TBA", "tampa bay rays": "TBA",
    "nationals": "WAS", "washington nationals": "WAS",
    "marlins": "MIA", "miami marlins": "MIA",
    "reds": "CIN", "cincinnati reds": "CIN",
    "pirates": "PIT", "pittsburgh pirates": "PIT",
    "brewers": "MIL", "milwaukee brewers": "MIL",
    "rockies": "COL", "colorado rockies": "COL",
    "diamondbacks": "ARI", "arizona diamondbacks": "ARI",
    "guardians": "CLE", "cleveland guardians": "CLE",
    "indians": "CLE", "cleveland indians": "CLE",
}

def resolve_team(team: str) -> str:
    if not team:
        return team
    if len(team) <= 3:
        return team.upper()
    return TEAM_NAME_MAP.get(team.lower().strip(), team.upper())


@router.get("/search/batting")
def search_batting(
    player_name:   Optional[str]   = None,
    team:          Optional[str]   = None,
    year_from:     Optional[int]   = None,
    year_to:       Optional[int]   = None,
    bats:          Optional[str]   = None,
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
    min_avg:       Optional[float] = None,   max_avg: Optional[float] = None,
    min_obp:       Optional[float] = None,
    min_slg:       Optional[float] = None,
    min_ops:       Optional[float] = None,
    sort_by:       Optional[str]   = "year",
    sort_dir:      Optional[str]   = "desc",
    limit:         int             = Query(default=50, le=200),
):
    conditions = ["1=1", "b.ab > 0"]
    params = {}

    if player_name:
        conditions.append("LOWER(p.namefirst || ' ' || p.namelast) LIKE :name")
        params["name"] = f"%{player_name.lower()}%"
    if team:
        conditions.append("b.teamid = :team")
        params["team"] = resolve_team(team)
    if year_from:
        conditions.append("b.yearid >= :year_from")
        params["year_from"] = year_from
    if year_to:
        conditions.append("b.yearid <= :year_to")
        params["year_to"] = year_to
    if bats:
        conditions.append("p.bats = :bats")
        params["bats"] = bats.upper()
    if min_g is not None:
        conditions.append("b.g >= :min_g"); params["min_g"] = min_g
    if min_ab is not None:
        conditions.append("b.ab >= :min_ab"); params["min_ab"] = min_ab
    if min_hr is not None:
        conditions.append("b.hr >= :min_hr"); params["min_hr"] = min_hr
    if max_hr is not None:
        conditions.append("b.hr <= :max_hr"); params["max_hr"] = max_hr
    if min_hits is not None:
        conditions.append("b.h >= :min_hits"); params["min_hits"] = min_hits
    if min_rbi is not None:
        conditions.append("b.rbi >= :min_rbi"); params["min_rbi"] = min_rbi
    if min_sb is not None:
        conditions.append("b.sb >= :min_sb"); params["min_sb"] = min_sb
    if min_bb is not None:
        conditions.append("b.bb >= :min_bb"); params["min_bb"] = min_bb
    if min_so is not None:
        conditions.append("b.so >= :min_so"); params["min_so"] = min_so
    if max_so is not None:
        conditions.append("b.so <= :max_so"); params["max_so"] = max_so
    if min_runs is not None:
        conditions.append("b.r >= :min_runs"); params["min_runs"] = min_runs
    if min_2b is not None:
        conditions.append("b.b2 >= :min_2b"); params["min_2b"] = min_2b
    if min_3b is not None:
        conditions.append("b.b3 >= :min_3b"); params["min_3b"] = min_3b

    avg_expr  = "CAST(b.h AS FLOAT) / NULLIF(b.ab, 0)"
    obp_expr  = "CAST(b.h + COALESCE(b.bb,0) + COALESCE(b.hbp,0) AS FLOAT) / NULLIF(b.ab + COALESCE(b.bb,0) + COALESCE(b.hbp,0) + COALESCE(b.sf,0), 0)"
    slg_expr  = "CAST(b.h + COALESCE(b.b2,0) + 2*COALESCE(b.b3,0) + 3*b.hr AS FLOAT) / NULLIF(b.ab, 0)"
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
        "year": "b.yearid", "hr": "b.hr", "avg": avg_expr, "rbi": "b.rbi",
        "hits": "b.h", "sb": "b.sb", "obp": obp_expr, "slg": slg_expr,
        "ops": ops_expr, "bb": "b.bb", "so": "b.so", "runs": "b.r",
    }
    order_col = sort_map.get(sort_by or "year", "b.yearid")
    direction = "ASC" if (sort_dir or "desc").lower() == "asc" else "DESC"

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            p.namefirst || ' ' || p.namelast AS player_name,
            p.playerid,
            b.yearid  AS year,
            b.teamid  AS team,
            p.bats,
            b.g       AS games,
            b.ab      AS at_bats,
            b.r       AS runs,
            b.h       AS hits,
            b.b2      AS doubles,
            b.b3      AS triples,
            b.hr      AS home_runs,
            b.rbi     AS rbi,
            b.sb      AS stolen_bases,
            b.cs      AS caught_stealing,
            b.bb      AS walks,
            b.so      AS strikeouts,
            b.hbp     AS hbp,
            b.sf      AS sac_flies,
            b.gidp    AS gidp,
            ROUND(({avg_expr})::NUMERIC, 3)  AS avg,
            ROUND(({obp_expr})::NUMERIC, 3)  AS obp,
            ROUND(({slg_expr})::NUMERIC, 3)  AS slg,
            ROUND(({ops_expr})::NUMERIC, 3)  AS ops
        FROM batting b
        JOIN people p ON b.playerid = p.playerid
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
    throws:        Optional[str]   = None,
    starter:       Optional[str]   = None,
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
    min_k9:        Optional[float] = None,
    sort_by:       Optional[str]   = "year",
    sort_dir:      Optional[str]   = "desc",
    limit:         int             = Query(default=50, le=200),
):
    conditions = ["1=1", "pt.ipouts > 0"]
    params = {}

    if player_name:
        conditions.append("LOWER(p.namefirst || ' ' || p.namelast) LIKE :name")
        params["name"] = f"%{player_name.lower()}%"
    if team:
        conditions.append("pt.teamid = :team")
        params["team"] = resolve_team(team)
    if year_from:
        conditions.append("pt.yearid >= :year_from"); params["year_from"] = year_from
    if year_to:
        conditions.append("pt.yearid <= :year_to"); params["year_to"] = year_to
    if throws:
        conditions.append("p.throws = :throws"); params["throws"] = throws.upper()
    if starter == "yes":
        conditions.append("pt.gs > 0")
    elif starter == "no":
        conditions.append("(pt.gs = 0 OR pt.gs IS NULL)")
    if min_g is not None:
        conditions.append("pt.g >= :min_g"); params["min_g"] = min_g
    if min_gs is not None:
        conditions.append("pt.gs >= :min_gs"); params["min_gs"] = min_gs
    if min_wins is not None:
        conditions.append("pt.w >= :min_wins"); params["min_wins"] = min_wins
    if max_losses is not None:
        conditions.append("pt.l <= :max_losses"); params["max_losses"] = max_losses
    if min_sv is not None:
        conditions.append("pt.sv >= :min_sv"); params["min_sv"] = min_sv
    if max_era is not None:
        conditions.append("pt.era <= :max_era"); params["max_era"] = max_era
    if min_era is not None:
        conditions.append("pt.era >= :min_era"); params["min_era"] = min_era
    if min_so is not None:
        conditions.append("pt.so >= :min_so"); params["min_so"] = min_so
    if max_bb is not None:
        conditions.append("pt.bb <= :max_bb"); params["max_bb"] = max_bb
    if min_ip is not None:
        conditions.append("CAST(pt.ipouts AS FLOAT)/3 >= :min_ip"); params["min_ip"] = min_ip
    if min_cg is not None:
        conditions.append("pt.cg >= :min_cg"); params["min_cg"] = min_cg
    if min_sho is not None:
        conditions.append("pt.sho >= :min_sho"); params["min_sho"] = min_sho

    ip_expr   = "CAST(pt.ipouts AS FLOAT) / 3"
    whip_expr = f"CAST(pt.h + pt.bb AS FLOAT) / NULLIF(({ip_expr}), 0)"
    k9_expr   = f"pt.so * 9.0 / NULLIF(({ip_expr}), 0)"

    if max_whip is not None:
        conditions.append(f"({whip_expr}) <= :max_whip"); params["max_whip"] = max_whip
    if min_k9 is not None:
        conditions.append(f"({k9_expr}) >= :min_k9"); params["min_k9"] = min_k9

    sort_map = {
        "year": "pt.yearid", "era": "pt.era", "wins": "pt.w", "so": "pt.so",
        "sv": "pt.sv", "ip": ip_expr, "whip": whip_expr, "k9": k9_expr,
    }
    order_col = sort_map.get(sort_by or "year", "pt.yearid")
    direction = "ASC" if (sort_dir or "desc").lower() == "asc" else "DESC"

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            p.namefirst || ' ' || p.namelast AS player_name,
            p.playerid,
            pt.yearid  AS year,
            pt.teamid  AS team,
            p.throws,
            pt.w       AS wins,
            pt.l       AS losses,
            pt.g       AS games,
            pt.gs      AS games_started,
            pt.cg      AS complete_games,
            pt.sho     AS shutouts,
            pt.sv      AS saves,
            ROUND(({ip_expr})::NUMERIC, 1)   AS innings_pitched,
            pt.h       AS hits_allowed,
            pt.er      AS earned_runs,
            pt.hr      AS hr_allowed,
            pt.bb      AS walks,
            pt.so      AS strikeouts,
            pt.hbp     AS hbp,
            pt.wp      AS wild_pitches,
            ROUND(pt.era::NUMERIC, 2)        AS era,
            ROUND(({whip_expr})::NUMERIC, 3) AS whip,
            ROUND(({k9_expr})::NUMERIC, 1)   AS k_per_9
        FROM pitching pt
        JOIN people p ON pt.playerid = p.playerid
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
        conditions.append("LOWER(p.namefirst || ' ' || p.namelast) LIKE :name")
        params["name"] = f"%{player_name.lower()}%"
    if team:
        conditions.append("f.teamid = :team")
        params["team"] = resolve_team(team)
    if year_from:
        conditions.append("f.yearid >= :year_from"); params["year_from"] = year_from
    if year_to:
        conditions.append("f.yearid <= :year_to"); params["year_to"] = year_to
    if position:
        conditions.append("f.pos = :pos"); params["pos"] = position.upper()
    if min_g is not None:
        conditions.append("f.g >= :min_g"); params["min_g"] = min_g
    if max_errors is not None:
        conditions.append("f.e <= :max_errors"); params["max_errors"] = max_errors

    where = " AND ".join(conditions)
    sql = f"""
        SELECT
            p.namefirst || ' ' || p.namelast AS player_name,
            p.playerid,
            f.yearid AS year,
            f.teamid AS team,
            f.pos    AS position,
            f.g      AS games,
            f.gs     AS games_started,
            f.po     AS putouts,
            f.a      AS assists,
            f.e      AS errors,
            f.dp     AS double_plays,
            ROUND((CAST(f.po + f.a AS FLOAT) / NULLIF(f.po + f.a + f.e, 0))::NUMERIC, 3) AS fielding_pct
        FROM fielding f
        JOIN people p ON f.playerid = p.playerid
        WHERE {where}
        ORDER BY f.yearid DESC, f.g DESC
        LIMIT :limit
    """
    params["limit"] = limit
    return query(sql, params)


@router.get("/teams")
def get_teams():
    sql = "SELECT DISTINCT teamid FROM teams ORDER BY teamid"
    return [r["teamid"] for r in query(sql)]

@router.get("/years")
def get_years():
    sql = "SELECT MIN(yearid) as min_year, MAX(yearid) as max_year FROM batting"
    return query(sql)[0]