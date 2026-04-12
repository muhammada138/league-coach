import sqlite3
import os

# Path to production DB
DB_PATH = "backend/data/league_coach.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    print(f"Migrating {DB_PATH}...")
    
    with sqlite3.connect(DB_PATH) as conn:
        # Check if queue column exists
        cursor = conn.execute("PRAGMA table_info(lp_history)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'queue' not in columns:
            print("Adding 'queue' column...")
            conn.execute("ALTER TABLE lp_history ADD COLUMN queue TEXT NOT NULL DEFAULT 'RANKED_SOLO_5x5'")
            print("Column added.")
        else:
            print("'queue' column already exists.")

        # Ensure index exists (might have failed before)
        print("Ensuring index exists...")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_lp_puuid_q_ts ON lp_history(puuid, queue, timestamp)")
        print("Migration complete.")

if __name__ == "__main__":
    migrate()
