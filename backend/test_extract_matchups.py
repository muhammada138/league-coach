import httpx
import re
import json

def test_extract_all_matchups():
    url = "https://lolalytics.com/lol/aatrox/counters/?tier=emerald&patch=16.8"
    headers = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get(url, headers=headers)
    html = r.text
    print(f"HTML Length: {len(html)}")

    # Lolalytics counter pages typically have a table with opponent names and winrates.
    # Let's search for champion names in the HTML.
    champ_names = ["camille", "jax", "fiora", "riven", "darius", "garen", "sett", "mordekaiser", "irelia", "renekton", "illaoi", "volibear", "sion", "ornn", "malphite"]
    
    found_count = 0
    for name in champ_names:
        # Look for the name followed by a percentage or a decimal that looks like a winrate
        pattern = re.compile(rf'>{name.capitalize()}<.*?([34567][0-9]\.[0-9]+)', re.IGNORECASE | re.DOTALL)
        match = pattern.search(html)
        if match:
            print(f"Found {name}: {match.group(1)}%")
            found_count += 1
        else:
            print(f"Did not find {name}")
            
    print(f"Found {found_count} out of {len(champ_names)} test champions.")

if __name__ == "__main__":
    test_extract_all_matchups()
