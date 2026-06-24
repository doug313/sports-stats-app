from sqlalchemy import create_engine, text

db_path = r'C:\Users\thaddious.douthit\PycharmProjects\sports-stats-app\backend\lahman.db'
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    r1 = conn.execute(text("SELECT DISTINCT batter_id FROM retro_events WHERE batter_id LIKE 'mant%'")).fetchall()
    r2 = conn.execute(text("SELECT COUNT(*) FROM retro_events WHERE game_id LIKE 'NYA%'")).scalar()
    r3 = conn.execute(text("SELECT DISTINCT batter_id FROM retro_events WHERE batter_id LIKE 'mant%' OR batter_id LIKE 'judg%' OR batter_id LIKE 'bond%'")).fetchall()
    print(f'Mantle-like IDs: {r1}')
    print(f'NYA home events: {r2}')
    print(f'Famous players:  {r3}')