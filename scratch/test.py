import asyncio, httpx, re, json

async def test_jinx():
    url = 'https://lolalytics.com/lol/tierlist/?tier=gold&patch=16.9'
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
            for raw in objs:
                if isinstance(raw, dict) and 'cid' in raw and 'row' in raw:
                    cid_val = _res(raw['cid'])
                    if str(cid_val) == '222': # Jinx
                        stats = objs[int(raw['row'], 36)]
                        print('Jinx games on 16.9:', _res(stats['games']))
                        break

    url = 'https://lolalytics.com/lol/tierlist/?tier=gold&patch=16.8'
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
            for raw in objs:
                if isinstance(raw, dict) and 'cid' in raw and 'row' in raw:
                    cid_val = _res(raw['cid'])
                    if str(cid_val) == '222': # Jinx
                        stats = objs[int(raw['row'], 36)]
                        print('Jinx games on 16.8:', _res(stats['games']))
                        break

asyncio.run(test_jinx())
