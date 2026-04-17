import sqlite3
import os
from app.state import DB_PATH

def wipe_data():
    print(f"Checking DB at: {DB_PATH}")
    if not os.path.exists(DB_PATH):
        print("DB file does not exist yet.")
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"Found tables: {[t[0] for t in tables]}")
    
    for table_name in [t[0] for t in tables]:
        if table_name != 'sqlite_sequence':
            print(f"Wiping table: {table_name}")
            cursor.execute(f"DELETE FROM {table_name}")
    
    conn.commit()
    conn.close()
    print("Wipe complete.")

if __name__ == "__main__":
    wipe_data()
