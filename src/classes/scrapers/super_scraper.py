import re
from datetime import datetime

import bs4
from bs4 import BeautifulSoup
from classes.db import DB, create_tables
from config import paths
from utils.json_cache import JsonCache
from utils.scrape import fetch_page
from yarl import URL
from utils.rate_limit import limit

super_limit = limit(calls=1, period=5, scope="super")


class SuperScraper:
    FORUM_URL = URL("https://forums.e-hentai.org/index.php")
    PATTS = {
        "price_buyer": re.compile(
            # 1803k (sickentide #66.5)
            r"(\d+[mkc]) \((.*) #[\d.]+\)"
        ),
        "quant_name": re.compile(
            # 30 Binding of Slaughter
            r"(\d+) (.*)"
        ),
        "level_stats": re.compile(
            # 455, MDB 36%, Holy EDB 73%
            r"(\d+|Unassigned|n/a)(?:, (.*))?"
        ),
    }
    HTML_CACHE = JsonCache(paths.CACHE_DIR / "super_html.json", default=dict)

    @classmethod
    @super_limit
    async def fetch_list(cls) -> list[dict]:
        """Fetch list of Super's auctions and update DB

        This only handles the list on the homepage (https://reasoningtheory.net),
        not the equip / item data
        """

        HOME_URL = URL("https://reasoningtheory.net")

        async def main():
            page: str = await fetch_page(HOME_URL)
            # from test.stubs.super import homepage; page = homepage  # fmt: skip
            soup = BeautifulSoup(page, "html.parser")

            row_els = soup.select("tbody > tr")
            row_data = []
            for el in row_els:
                data = parse_row(el)
                insert_db_row(data)
                row_data.append(data)

            return row_data

        def parse_row(row: bs4.Tag) -> dict:
            [idxEl, dateEl, _, _, _, threadEl] = row.select("td")

            title = idxEl.text
            end_time = datetime.strptime(
                dateEl.text + "+0000", r"%m-%d-%Y%z"
            ).timestamp()
            id = re.search(r"showtopic=(\d+)", str(threadEl.select_one("a")["href"])).group(1)  # type: ignore

            data = dict(
                id=id,
                title=title,
                end_time=end_time,
            )
            return data

        def insert_db_row(data: dict) -> None:
            with DB:
                DB.execute(
                    """
                    INSERT OR IGNORE INTO super_auctions
                    (id, title, end_time) VALUES (:id, :title, :end_time)
                """,
                    data,
                )

        return await main()

    @classmethod
    def forum_thread(cls, id: int | str) -> URL:
        return cls.FORUM_URL % {"showtopic": id}


if __name__ == "__main__":
    # fmt: off
    from config import init_logging
    import asyncio

    async def main():
        create_tables()
        await SuperScraper.fetch_list()
    asyncio.run(main())
