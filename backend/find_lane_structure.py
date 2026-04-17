import httpx
import re

def find_lane_structure():
    url = "https://lolalytics.com/lol/aatrox/counters/?tier=emerald&patch=16.8"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get(url, headers=headers)
    html = r.text
    
    # Search for "TOP", "JUNGLE" etc and see what surrounds them
    for lane in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "SUPPORT"]:
        idx = html.upper().find(lane)
        if idx != -1:
            print(f"--- Context for {lane} ---")
            print(html[idx-100:idx+300])

if __name__ == "__main__":
    find_lane_structure()
