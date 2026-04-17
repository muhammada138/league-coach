import httpx
import re

def test_row_extraction():
    url = "https://lolalytics.com/lol/tierlist/?tier=emerald&patch=16.8"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get(url, headers=headers)
    html = r.text
    
    # Isolate the main table content
    # Look for rows: h-[52px]
    rows = re.findall(r'<div[^>]*h-\[52px\].*?</div></div></div></div>', html, re.DOTALL)
    print(f"Found {len(rows)} data rows")
    
    for i, row in enumerate(rows[:10]):
        # Find champion name in build link
        name_match = re.search(r'href="/lol/([^/"]+)/build/', row)
        if name_match:
            name = name_match.group(1)
            # Find winrate in column 5
            wr_match = re.search(r'q:key="5".*?>([0-9\.]+)', row, re.DOTALL)
            wr = wr_match.group(1) if wr_match else "N/A"
            print(f"Row {i+1}: {name} -> {wr}%")

if __name__ == "__main__":
    test_row_extraction()
