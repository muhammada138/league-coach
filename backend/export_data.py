import sqlite3
import pandas as pd
import json
from pathlib import Path

# Paths
DB_PATH = Path(__file__).parent / "data" / "league_coach.db"
EXPORT_PATH = Path(__file__).parent / "matches_export.csv"

def export():
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        return

    print(f"📦 Exporting from {DB_PATH}...")
    
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM training_matches", conn)
        
    if df.empty:
        print("⚠️ No data found in 'training_matches' table.")
        return

    # Optional: Flatten the JSON columns for easier reading in Excel
    print("🧹 Flattening features for readability...")
    def parse_feats(x):
        try:
            return "|".join([f"{v:.3f}" for v in json.loads(x)])
        except:
            return x

    df['blue_feats_flat'] = df['blue_feats'].apply(parse_feats)
    df['red_feats_flat'] = df['red_feats'].apply(parse_feats)

    df.to_csv(EXPORT_PATH, index=False)
    print(f"✅ Success! Data exported to: {EXPORT_PATH}")
    print(f"📊 Total Rows: {len(df)}")

if __name__ == "__main__":
    export()
