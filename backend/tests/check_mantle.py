from sqlalchemy import create_engine, text

db_path = r'C:\Users\thaddious.douthit\PycharmProjects\sports-stats-app\backend\lahman.db'
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    # Check what hit_value values look like for a known no-hitter
    # Nolan Ryan threw many — check 1973 season
    r1 = conn.execute(text("""
        SELECT g.game_id, g.date, g.home_team, g.away_team,
               SUM(CASE WHEN e.hit_value > 0 THEN 1 ELSE 0 END) as hits,
               SUM(CASE WHEN e.event_cd IN (20,21,22,23) THEN 1 ELSE 0 END) as hits_by_cd,
               COUNT(*) as total_plays
        FROM retro_games g
        JOIN retro_events e ON g.game_id = e.game_id
        WHERE g.year = 1973
        GROUP BY g.game_id, g.date, g.home_team, g.away_team
        HAVING hits = 0 AND hits_by_cd = 0
        LIMIT 5
    """)).fetchall()
    print("Games with 0 hits by hit_value AND event_cd in 1973:")
    for r in r1:
        print(f"  {r}")

    # Check what hit_value looks like overall
    r2 = conn.execute(text("""
        SELECT hit_value, COUNT(*) as cnt
        FROM retro_events
        WHERE hit_value IS NOT NULL
        GROUP BY hit_value
        ORDER BY hit_value
    """)).fetchall()
    print("\nhit_value distribution:")
    for r in r2:
        print(f"  hit_value={r[0]}  count={r[1]:,}")

    # Check event_cd distribution
    r3 = conn.execute(text("""
        SELECT event_cd, COUNT(*) as cnt
        FROM retro_events
        WHERE event_cd IN (20,21,22,23)
        GROUP BY event_cd
        ORDER BY event_cd
    """)).fetchall()
    print("\nHit event_cd distribution:")
    for r in r3:
        print(f"  event_cd={r[0]}  count={r[1]:,}")