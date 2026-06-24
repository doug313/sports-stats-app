from sqlalchemy import create_engine, text

db_path = r'C:\Users\thaddious.douthit\PycharmProjects\sports-stats-app\backend\lahman.db'
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    r1 = conn.execute(text("SELECT COUNT(*) FROM retro_games WHERE home_team='NYA' OR away_team='NYA'")).scalar()
    r2 = conn.execute(text("SELECT COUNT(*) FROM retro_games WHERE year BETWEEN 1960 AND 1962")).scalar()
    r3 = conn.execute(text("SELECT game_id, date, away_team, home_team, away_score, home_score FROM retro_games LIMIT 1")).fetchone()
    r4 = conn.execute(text("SELECT COUNT(*) FROM retro_events WHERE batter_id LIKE '%mantl%'")).scalar()
    r5 = conn.execute(text("SELECT DISTINCT batter_id FROM retro_events LIMIT 10")).fetchall()
    r6 = conn.execute(text("SELECT COUNT(*) FROM retro_events")).scalar()
    print(f'NYA games total:    {r1}')
    print(f'1960-1962 games:    {r2}')
    print(f'Sample row:         {r3}')
    print(f'Mantle events:      {r4}')
    print(f'Sample batter IDs:  {r5}')
    print(f'Total events:       {r6}')