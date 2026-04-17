import httpx
import re
import json

def parse_massive_script():
    headers = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get('https://lolalytics.com/lol/tierlist/?tier=emerald&patch=16.8', headers=headers)
    
    # Script 6 was huge. Let's find it.
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
    huge_script = ""
    for s in scripts:
        if len(s) > 100000:
            huge_script = s
            break
    
    if not huge_script:
        print("Huge script not found")
        return

    # Let's see if we can find decimals that look like winrates (40-65)
    # or champion IDs (1-1000)
    winrates = re.findall(r'5\d\.\d+', huge_script)
    print(f"Found {len(winrates)} numbers that look like winrates (50%+). Samples: {winrates[:10]}")
    
    # Try to load as JSON
    try:
        data = json.loads(huge_script)
        print("SUCCESSFULLY LOADED JSON")
        # Recursively search for keys or patterns
        def find_stats(obj, depth=0):
            if depth > 10: return
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "wr" or k == "winrate":
                        print(f"Found WR key: {v}")
                    find_stats(v, depth + 1)
            elif isinstance(obj, list):
                for item in obj:
                    find_stats(item, depth + 1)
        
        # Look at top level keys
        print(f"Top level keys: {list(data.keys())}")
        if "objs" in data:
            print(f"Number of objects in 'objs': {len(data['objs'])}")
            # Sample a few objects
            for i in range(min(5, len(data['objs']))):
                print(f"  Obj {i}: {str(data['objs'][i])[:200]}")

    except Exception as e:
        print(f"JSON Parse failed: {e}")

if __name__ == "__main__":
    parse_massive_script()
