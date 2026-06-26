from sqlalchemy import create_engine, text

db_path = r'C:\Users\thaddious.douthit\PycharmProjects\sports-stats-app\backend\lahman.db'
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    # Check if any game_id + event_num combos are duplicated
    dupes = conn.execute(text("""
        SELECT game_id, event_num, COUNT(*) as cnt
        FROM retro_events
        GROUP BY game_id, event_num
        HAVING COUNT(*) > 1
        LIMIT 10
    """)).fetchall()

    # Sample a game to see event_num sequence
    sample = conn.execute(text("""
        SELECT game_id, event_num, inning, batter_id, event_cd
        FROM retro_events
        WHERE game_id = (SELECT game_id FROM retro_games LIMIT 1)
        ORDER BY event_num
        LIMIT 15
    """)).fetchall()

    total = conn.execute(text("SELECT COUNT(*) FROM retro_events")).scalar()
    games = conn.execute(text("SELECT COUNT(*) FROM retro_games")).scalar()

    print(f"Total events: {total:,}")
    print(f"Total games:  {games:,}")
    print(f"\nDuplicate game_id+event_num pairs: {len(dupes)}")
    if dupes:
        for d in dupes:
            print(f"  {d}")

    print(f"\nSample game event sequence:")
    for row in sample:
        print(f"  {row}")