import psycopg2

conn = psycopg2.connect("postgresql://postgres:jhJFzLrwBWMXepNrTNRGVOXDnEAqMZaR@hopper.proxy.rlwy.net:24866/railway")
cur = conn.cursor()

tables = ["Batting", "People", "Pitching", "Fielding", "Teams",
          "AwardsPlayers", "AllstarFull", "HallOfFame", "Appearances", "Salaries",
          "batting", "people", "pitching", "fielding", "teams",
          "awardsplayers", "allstarfull", "halloffame", "appearances", "salaries"]

for t in tables:
    try:
        cur.execute(f'DROP TABLE IF EXISTS "{t}" CASCADE')
        print(f"Dropped {t}")
    except Exception as e:
        print(f"Skip {t}: {e}")

conn.commit()
print("Done")