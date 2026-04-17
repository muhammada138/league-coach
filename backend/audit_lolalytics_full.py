import httpx
import re
import json

def audit_html():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://lolalytics.com/"
    }
    r = httpx.get('https://lolalytics.com/lol/tierlist/?tier=emerald&patch=16.8', headers=headers)
    html = r.text
    
    # 1. Find all build links
    # The links look like: href="/lol/aatrox/build/"
    links = re.findall(r'href="/lol/([^/"]+)/build/', html)
    unique_names = list(dict.fromkeys(links))
    print(f"Unique champion names found: {len(unique_names)}")
    print(f"First 20 names: {unique_names[:20]}")
    
    # 2. Find the tier average winrate
    # Text looks like: Average Emerald Win Rate: <!--t=2k-->50.96<!---->%
    avg_match = re.search(r'Average \w+ Win Rate:.*?([0-9\.]+)', html, re.DOTALL)
    if avg_match:
        print(f"Found Average Win Rate: {avg_match.group(1)}%")
    else:
        print("Average Win Rate NOT FOUND")
        # Try a wider search
        wide_avg = re.search(r'Average.*?Win Rate.*?([0-9\.]+)', html, re.DOTALL | re.IGNORECASE)
        if wide_avg:
            print(f"Found Wide Average Win Rate: {wide_avg.group(1)}%")

    # 3. Test data extraction for a few specific names
    for name in unique_names[:5]:
        # Lolalytics typically has: >Sona< ... Win 52.66
        # The space between tags can vary.
        # Looking at the previous HTML read, it's very dense.
        pattern = re.compile(rf'>{name.capitalize()}<.*?Win\s*([0-9\.]+)', re.IGNORECASE | re.DOTALL)
        match = pattern.search(html)
        if match:
            print(f"  {name}: {match.group(1)}%")
        else:
            # Fallback: search for the name then the first decimal
            pattern = re.compile(rf'{name}.*?([456][0-9]\.[0-9]+)', re.IGNORECASE | re.DOTALL)
            match = pattern.search(html)
            if match:
                print(f"  {name} (fallback): {match.group(1)}%")

if __name__ == "__main__":
    audit_html()
