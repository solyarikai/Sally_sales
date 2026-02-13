"""Check latest SmartLead Deliryo campaigns."""
import asyncio, httpx, os

async def main():
    api_key = os.environ.get('SMARTLEAD_API_KEY')
    async with httpx.AsyncClient(timeout=30) as c:
        all_camps = []
        for offset in range(0, 2000, 100):
            r = await c.get(
                'https://server.smartlead.ai/api/v1/campaigns',
                params={'api_key': api_key, 'limit': 100, 'offset': offset}
            )
            data = r.json()
            if isinstance(data, list):
                if not data:
                    break
                all_camps.extend(data)
            elif isinstance(data, dict) and 'data' in data:
                if not data['data']:
                    break
                all_camps.extend(data['data'])
            else:
                break

        deliryo = [x for x in all_camps if isinstance(x, dict) and 'deliryo' in (x.get('name', '') or '').lower()]
        deliryo.sort(key=lambda x: x.get('id', 0), reverse=True)
        print("TOTAL_CAMPAIGNS:", len(all_camps))
        print("DELIRYO_CAMPAIGNS:", len(deliryo))
        print("LATEST 15:")
        for camp in deliryo[:15]:
            cid = camp['id']
            name = camp['name']
            status = camp.get('status', 'unknown')
            print("  #" + str(cid) + " | " + str(status) + " | " + name)

asyncio.run(main())
