import sqlite3
from pathlib import Path

# Path to the database file
DB_PATH = Path(__file__).parent / "data" / "league_coach.db"


def check_data():
    """Checks the database for training data in both the clean and legacy tables."""
    if not DB_PATH.exists():
        print(f"❌ Error: Database not found at {DB_PATH}")
        print("Ensure you are running this from the backend directory.")
        return

    print(f"🔍 Inspecting database: {DB_PATH}\n")

    try:
        with sqlite3.connect(DB_PATH) as conn:
            # Check for existsing tables
            cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            print(f"📊 Tables found: {', '.join(tables)}")
            print("-" * 40)

            # Check training_matches (New Clean Data)
            if "training_matches" in tables:
                count = conn.execute(
                    "SELECT COUNT(*) FROM training_matches"
                ).fetchone()[0]
                print(f"✅ Table 'training_matches': {count} rows (New Clean Data)")
            else:
                print("⚠️ Table 'training_matches' not found.")

            # Check training_matches_v1 (Legacy 11k Data)
            if "training_matches_v1" in tables:
                count = conn.execute(
                    "SELECT COUNT(*) FROM training_matches_v1"
                ).fetchone()[0]
                print(f"✅ Table 'training_matches_v1': {count} rows (Legacy Data)")
                if count > 0:
                    print("   ✨ This is likely where your 11k data points are stored!")
            else:
                print(
                    "ℹ️ Table 'training_matches_v1' not found. (Migration might not have run yet)"
                )

            # Check ingestion status
            if "ingestion_status" in tables:
                status = conn.execute(
                    "SELECT processed_count, total_target, is_paused FROM ingestion_status WHERE id = 1"
                ).fetchone()
                if status:
                    print("-" * 40)
                    print(f"📈 Ingestion Progress: {status[0]} / {status[1]}")
                    print(f"⏸️  Status: {'Paused' if status[2] else 'Active'}")

    except Exception as e:
        print(f"❌ An error occurred: {e}")


if __name__ == "__main__":
    check_data()
