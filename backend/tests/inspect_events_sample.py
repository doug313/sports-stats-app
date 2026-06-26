from sqlalchemy import create_engine, text

db_path = r'C:\Users\thaddious.douthit\PycharmProjects\sports-stats-app\backend\lahman.db'
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT game_id, event_num, inning, batting_team,
               batter_id, pitcher_id, event_cd, rbi, play_text
        FROM retro_events
        LIMIT 5
    """)).fetchall()
    for row in rows:
        print(row)