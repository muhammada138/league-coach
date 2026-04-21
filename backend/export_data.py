import sqlite3
import csv
import json
from pathlib import Path

# Paths
DB_PATH = Path(__file__).parent / "data" / "league_coach.db"
EXPORT_PATH = Path(__file__).parent / "matches_export.csv"

def export():
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return

    print(f"📦 Exporting from {DB_PATH} using built-in CSV module...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM training_matches")
        rows = cursor.fetchall()
        
        if not rows:
            print("⚠️ No data found in 'training_matches' table.")
            return

        # Get column names
        fields = rows[0].keys()
        
        with open(EXPORT_PATH, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(fields) + ['blue_feats_flat', 'red_feats_flat'])
            writer.writeheader()
            
            for row in rows:
                d = dict(row)
                
                # Flatten features for readability
                try:
                    b_list = json.loads(d['blue_feats'])
                    d['blue_feats_flat'] = "|".join([f"{v:.3f}" for v in b_list])
                except:
                    d['blue_feats_flat'] = ""
                    
                try:
                    r_list = json.loads(d['red_feats'])
                    d['red_feats_flat'] = "|".join([f"{v:.3f}" for v in r_list])
                except:
                    d['red_feats_flat'] = ""
                
                writer.writerow(d)

        print(f"✅ Success! Data exported to: {EXPORT_PATH}")
        print(f"📊 Total Rows: {len(rows)}")
        conn.close()

    except Exception as e:
        print(f"❌ Export failed: {e}")

if __name__ == "__main__":
    export()
