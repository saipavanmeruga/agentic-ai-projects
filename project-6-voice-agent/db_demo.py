from database_init import engine, text


def run_sql(query: str) -> list[tuple]:
    with engine.connect() as conn: 
        result = conn.execute(text(query))
        conn.commit()
        return result.fetchall() if result.returns_rows else result.rowcount

if __name__ == "__main__":
    query = "CREATE TABLE IF NOT EXISTS appointments (id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, time TEXT, patient_name TEXT, reason TEXT)"
    print(run_sql(query))
    print("Table created successfully")

    query = "INSERT INTO appointments (date, time, patient_name, reason) VALUES ('2026-08-29', '10:00', 'John Doe', 'Checkup')"
    print(run_sql(query))
    print("Record inserted successfully")

    query = "SELECT * FROM appointments"
    print(run_sql(query))
    print("Records selected successfully")
