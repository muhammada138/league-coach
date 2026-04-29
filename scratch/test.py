import asyncio, httpx, re, json

async def test_lux_no_lane():
    url = 'https://lolalytics.com/lol/tierlist/?tier=bronze'
    headers = {'User-Agent': 'Mozilla/5.0'}
    async with httpx.AsyncClient() as c:
        resp = await c.get(url, headers=headers)
        html = resp.text
        m = re.search(r'<script type="qwik/json">(.*?)</script>', html, re.DOTALL)
        if m:
            state = json.loads(m.group(1))
            objs = state.get('objs', [])
            def _res(val):
                if isinstance(val, str):
                    try: return objs[int(val, 36)]
                    except: pass
                return val
            lanes_found = set()
            for raw in objs:
                if isinstance(raw, dict) and 'cid' in raw and 'row' in raw:
                    cid_val = _res(raw['cid'])
                    if str(cid_val) == '99': # Lux
                        stats = objs[int(raw['row'], 36)]
                        lanes_found.add(_res(stats.get('lane')))
            print('Lanes found for Lux in default query:', lanes_found)

asyncio.run(test_lux_no_lane())
