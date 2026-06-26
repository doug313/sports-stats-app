from sqlalchemy import create_engine, text

db_path = r'C:\Users\thaddious.douthit\PycharmProjects\sports-stats-app\backend\lahman.db'
engine = create_engine(f'sqlite:///{db_path}')

with engine.connect() as conn:
    # Look up famous players by last name
    for name in ["Ruth", "Mantle", "Aaron", "Koufax", "Gibson", "Jeter", "Judge", "Ohtani", "Bonds"]:
        rows = conn.execute(text(
            "SELECT retro_id, full_name FROM retro_people WHERE last_name = :n ORDER BY retro_id"
        ), {"n": name}).fetchall()
        for row in rows:
            print(f"  {row[0]:15} {row[1]}")
        if not rows:
            print(f"  NOT FOUND: {name}")