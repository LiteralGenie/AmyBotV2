import aiohttp
import asyncio


async def main():
    async def log(session, ctx, params):
        print(params.method, params.url)
        print(dict(params.response.request_info.headers))

    trace_config = aiohttp.TraceConfig()
    trace_config.on_request_end.append(log)
    session = aiohttp.ClientSession(
        trace_configs=[trace_config],
    )
    session.cookie_jar.update_cookies(dict(ipb_member_id="3950842"))

    async with session:
        resp = await session.get("https://httpbin.org/cookies")
        # resp = await session.post(
        #     "https://forums.e-hentai.org/index.php?act=Search&CODE=01",
        #     data="keywords=%5BAuction%5D&namesearch=SakiRaFubuKi&forums%5B%5D=77&searchsubs=1&prune=0&prune_type=newer&sort_key=last_post&sort_order=desc&search_in=titles&result_type=topics",
        # )
        resp = await session.post(
            "https://forums.e-hentai.org/index.php?act=Search&CODE=01",
            data={
                "keywords": "[Auction]",
                "namesearch": "SakiRaFubuKi",
                "forums[]": "77",
                "searchsubs": "1",
                "prune": "0",
                "prune_type": "newer",
                "sort_key": "last_post",
                "sort_order": "desc",
                "search_in": "titles",
                "result_type": "topics",
            }
            # data="keywords=&namesearch=&forums=77&searchsubs=1&prune=0&prune_type=newer&sort_key=last_post&sort_order=desc&search_in=titles&result_type=topics",
        )
        text = await resp.text()
        print(text)


asyncio.run(main())
