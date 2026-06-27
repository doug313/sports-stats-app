from db.database import query
from fastapi import APIRouter

router = APIRouter()

@router.get("/players/{player_id}")
def get_player(player_id: str):
    sql = """
        SELECT p.*,
               (SELECT COUNT(*) FROM allstarfull a WHERE a.playerid = p.playerid) as all_star_count,
               (SELECT COUNT(*) FROM awardsplayers a WHERE a.playerid = p.playerid) as awards_count,
               (SELECT inducted FROM halloffame h WHERE h.playerid = p.playerid AND h.inducted = 'Y' LIMIT 1) as hof
        FROM people p
        WHERE p.playerid = :pid
    """
    rows = query(sql, {"pid": player_id})
    if not rows:
        return {"error": "Player not found"}
    player = rows[0]

    bat_sql = """
        SELECT yearid, teamid, g, ab, h, hr, rbi, sb, bb, so,
               ROUND((CAST(h AS FLOAT) / NULLIF(ab, 0))::NUMERIC, 3) as avg
        FROM batting WHERE playerid = :pid ORDER BY yearid
    """
    player["batting"] = query(bat_sql, {"pid": player_id})

    pit_sql = """
        SELECT yearid, teamid, w, l, g, gs, sv,
               ROUND(era::NUMERIC, 2) as era, so, bb,
               ROUND((CAST(ipouts AS FLOAT) / 3)::NUMERIC, 1) as ip
        FROM pitching WHERE playerid = :pid ORDER BY yearid
    """
    player["pitching"] = query(pit_sql, {"pid": player_id})

    award_sql = """
        SELECT awardid, yearid FROM awardsplayers WHERE playerid = :pid ORDER BY yearid
    """
    player["awards"] = query(award_sql, {"pid": player_id})

    return player