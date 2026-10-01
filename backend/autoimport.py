import asyncio
import os
import httpx

async def run():
    async with httpx.AsyncClient(base_url='http://localhost:8001/api', timeout=600) as c:
        res = await c.post('/auth/login', json={
            'username': os.environ['IMPORT_ADMIN_USERNAME'],
            'password': os.environ['IMPORT_ADMIN_PASSWORD'],
        })
        if res.status_code != 200:
            print('Login failed:', res.text)
            return
        cookies = res.cookies
        
        for source in ['store', 'september']:
            print(f'\nMemproses dataset: {source}')
            res = await c.get(f'/imports/preview?source={source}', cookies=cookies)
            if res.status_code != 200:
                print('Preview error:', res.text)
                continue
                
            data = res.json()
            for group, info in data['summary'].items():
                if info['ready'] > 0 and not info['imported']:
                    print(f' -> Mengimpor {group} ({info["ready"]} baris)...')
                    payload = {'source': source, 'groups': [group], 'digest': data['digest'], 'confirmed': True}
                    res = await c.post('/imports/commit', json=payload, cookies=cookies)
                    print(f'    Selesai. Result: {res.status_code}')
                elif info['imported']:
                    print(f' -> {group} sudah terimpor sebelumnya.')
                else:
                    print(f' -> {group} tidak ada data siap impor.')

asyncio.run(run())
