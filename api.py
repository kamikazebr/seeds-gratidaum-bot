import aiohttp
from ppretty import ppretty


async def api_get(account, memo=''):
    memo = memo if memo else ''
    json = {
        "actions": [
            {
                "account": "gratz.seeds",
                "name": "acknowledge",
                "authorization": [
                    {
                        "actor": "............1",
                        "permission": "............2"
                    }
                ],
                "data": {
                    "from": "............1",
                    "to": account,
                    "memo": memo
                }
            }
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post('https://api-esr.hypha.earth/qr',
                                json=json) as response:
            print("Status:", response.status)
            print("Content-type:", response.headers['content-type'])

            json = await response.json()
            print("Body:", ppretty(json))
            return json
