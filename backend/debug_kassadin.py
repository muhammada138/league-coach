import httpx
import re

def debug_kassadin():
    url = "https://lolalytics.com/lol/tierlist/?tier=emerald&patch=16.8"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get(url, headers=headers)
    html = r.text
    
    print(f"HTML Length: {len(html)}")
    
    # Let's find all occurrences of Kassadin
    # Note: Lolalytics uses lowercase in URLs
    target = "kassadin"
    
    # Find the specific row for Kassadin
    # Rows start with build links, which may contain parameters
    rows = re.split(r'href="/lol/([^/"]+)/build/\??[^"]*"', html)
    print(f"Found {len(rows)//2} potential rows")
    
    print(f"Found {len(rows)//2} potential rows")
    
    for i in range(1, min(len(rows), 11), 2):
        name = rows[i]
        content = rows[i+1][:2000]
        print(f"Row {i//2 + 1}: {name}")
        wr_match = re.search(r'q:key="5".*?>([0-9\.]+)<', content, re.DOTALL)
        if wr_match:
            print(f"  Win Rate: {wr_match.group(1)}%")
        else:
            print("  Win Rate NOT FOUND")

if __name__ == "__main__":
    debug_kassadin()
