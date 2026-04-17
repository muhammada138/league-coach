import httpx
import re

def debug_vayne():
    url = "https://lolalytics.com/lol/tierlist/?tier=emerald&patch=16.8"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get(url, headers=headers)
    html = r.text
    
    # Find Vayne
    idx = html.find("Vayne")
    if idx == -1:
        print("Vayne not found")
        return
        
    print("--- HTML around Vayne ---")
    print(html[idx:idx+2000])
    
    # Try the current regex
    name = "vayne"
    pattern = re.compile(rf'{name}.*?([456][0-9]\.[0-9]+)', re.IGNORECASE | re.DOTALL)
    match = pattern.search(html)
    if match:
        print(f"Regex match: {match.group(1)}")
    else:
        print("Regex did not match")

if __name__ == "__main__":
    debug_vayne()
