import httpx
import re

def check_lane_tables():
    url = "https://lolalytics.com/lol/aatrox/counters/?tier=emerald&patch=16.8"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get(url, headers=headers)
    html = r.text
    
    # Let's find sections that look like they contain "Versus" or opponent tables
    # Often they group by lane: "Top Lane", "Middle Lane", etc.
    # We saw "Aatrox top versus top Counters" in the title.
    
    # Try searching for champion names specifically in the context of lane headers
    for lane in ["Top", "Jungle", "Middle", "Bottom", "Support"]:
        # Search for "Top" then look for champions nearby
        pattern = re.compile(rf'{lane}.*?([A-Z][a-z]+)<.*?([34567][0-9]\.[0-9]+)', re.DOTALL)
        matches = pattern.findall(html)
        if matches:
            print(f"--- Possible {lane} Matchups ---")
            for m in matches[:5]:
                print(f"  {m[0]}: {m[1]}%")

if __name__ == "__main__":
    check_lane_tables()
