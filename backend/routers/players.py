from fastapi import APIRouter
from db.database import query

router = APIRouter()

@router.get("/players/{player_id}")
def get_player(player_id: str):
    sql = """
        SELECT p.*,
               (SELECT COUNT(*) FROM AllstarFull a WHERE a.playerID = p.playerID) as all_star_count,
               (SELECT COUNT(*) FROM AwardsPlayers a WHERE a.playerID = p.playerID) as awards_count,
               (SELECT inducted FROM HallOfFame h WHERE h.playerID = p.playerID AND h.inducted = 'Y' LIMIT 1) as hof
        FROM People p
        WHERE p.playerID = :pid
    """
    rows = query(sql, {"pid": player_id})
    if not rows:
        return {"error": "Player not found"}
    player = rows[0]

    # Career batting
    bat_sql = """
        SELECT yearID, teamID, G, AB, H, HR, RBI, SB, BB, SO,
               ROUND(CAST(H AS FLOAT) / NULLIF(AB, 0), 3) as avg
        FROM Batting WHERE playerID = :pid ORDER BY yearID
    """
    player["batting"] = query(bat_sql, {"pid": player_id})

    # Career pitching
    pit_sql = """
        SELECT yearID, teamID, W, L, G, GS, SV,
               ROUND(ERA, 2) as era, SO, BB,
               ROUND(CAST(IPouts AS FLOAT) / 3, 1) as ip
        FROM Pitching WHERE playerID = :pid ORDER BY yearID
    """
    player["pitching"] = query(pit_sql, {"pid": player_id})

    # Awards
    award_sql = """
        SELECT awardID, yearID FROM AwardsPlayers WHERE playerID = :pid ORDER BY yearID
    """
    player["awards"] = query(award_sql, {"pid": player_id})

    return player
