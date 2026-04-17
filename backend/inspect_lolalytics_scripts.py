import httpx
import re

def inspect_scripts():
    headers = {"User-Agent": "Mozilla/5.0"}
    r = httpx.get('https://lolalytics.com/lol/tierlist/?tier=emerald&patch=16.8', headers=headers)
    
    # Find all <script> tags
    scripts = re.findall(r'<script[^>]*>(.*?)</script>', r.text, re.DOTALL)
    print(f"Found {len(scripts)} scripts")
    
    for i, s in enumerate(scripts):
        print(f"Script {i} length: {len(s)}")
        if len(s) > 1000:
            print(f"  Snippet: {s[:100]}...{s[-100:]}")
            # Look for JSON-like arrays/objects
            if '[' in s and ']' in s:
                print(f"  Contains arrays")
            if '{' in s and '}' in s:
                print(f"  Contains objects")

if __name__ == "__main__":
    inspect_scripts()
