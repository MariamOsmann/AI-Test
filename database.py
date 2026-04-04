import sqlite3
import pandas as pd

DB_FILE  = "interview.db"
CSV_FILE = "sql_questions.csv"

def init_db():
    """بيعمل الـ database ويحمّل الأسئلة من الـ CSV"""
    conn   = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id       INTEGER PRIMARY KEY,
            level    TEXT NOT NULL,
            question TEXT NOT NULL
        )
    """)

    df = pd.read_csv(CSV_FILE)
    df.to_sql("questions", conn, if_exists="replace", index=False)

    conn.commit()
    conn.close()
    print("✅ Database ready! questions loaded from CSV.")

def get_questions():
    """بيرجع كل الأسئلة كـ DataFrame"""
    conn = sqlite3.connect(DB_FILE)
    df   = pd.read_sql("SELECT * FROM questions", conn)
    conn.close()
    return df

if __name__ == "__main__":
    init_db()