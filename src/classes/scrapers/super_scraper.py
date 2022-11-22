import json
import re
from datetime import datetime
import time

import bs4
from bs4 import BeautifulSoup, ResultSet, Tag
from loguru import logger
from classes.db import DB, create_tables
from config import paths
from utils.json_cache import JsonCache
from utils.parse import parse_equip_link, price_to_int
from utils.scrape import fetch_page
from yarl import URL
from utils.rate_limit import rate_limit

super_limit = rate_limit(calls=1, period=5, scope="super")


class SuperScraper:
    HOME_URL = URL("https://reasoningtheory.net")

    HTML_CACHE_FILE = JsonCache(paths.CACHE_DIR / "super_html.json", default=dict)
    html_cache: dict = HTML_CACHE_FILE.load()  # type: ignore

    @classmethod
    async def fetch_updates(cls):
        """Fetch auctions that haven't been parsed yet"""
        with DB:
            rows = DB.execute(
                """
                SELECT id FROM super_auctions
                WHERE last_fetch_time is NULL
                """
            ).fetchall()

        for r in rows:
            await cls.fetch_auction(r["id"])

    @classmethod
    @super_limit
    async def refresh_list(cls) -> list[dict]:
        """Fetch list of Super's auctions and update DB

        This only handles the list on the homepage (https://reasoningtheory.net),
        not the equip / item data
        """

        async def main():
            page: str = await fetch_page(cls.HOME_URL, content_type="text")
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

            data = dict(id=id, title=title, end_time=end_time)
            return data

        def insert_db_row(data: dict) -> None:
            with DB:
                DB.execute(
                    """
                    INSERT OR IGNORE INTO super_auctions
                    (id, title, end_time, is_complete, last_fetch_time) VALUES (:id, :title, :end_time, 0, 0)
                """,
                    data,
                )

        return await main()

    @classmethod
    async def fetch_auction(cls, auction_id: str) -> list[dict]:
        PATTS = {
            "price_buyer": re.compile(
                # 1803k (sickentide #66.5)
                r"^(\d+[mkc]) \((.*) #[\d.]+\)$"
            ),
            "quant_name": re.compile(
                # 30 Binding of Slaughter
                r"^(\d+) (.*)$"
            ),
            "level_stats": re.compile(
                # 455, MDB 36%, Holy EDB 73%
                r"^(\d+|Unassigned|n/a)(?:, (.*))?$"
            ),
        }

        async def main():
            page = await fetch(auction_id)
            rows = [r.select("td") for r in page.select("tbody > tr")]

            # Parse auction data
            item_data = []
            for row in rows:
                data = parse_quirky_row(auction_id, row) or parse_row(row)

                data["id_auction"] = auction_id
                item_data.append(data)

            # Update db
            with DB:
                for item in item_data:
                    if item["_type"] == "equip":
                        DB.execute(
                            """
                            INSERT OR REPLACE INTO super_equips 
                            (id, id_auction, name, eid, key, is_isekai, level, stats, price, bid_link, buyer, seller)
                            VALUES (:id, :id_auction, :name, :eid, :key, :is_isekai, :level, :stats, :price, :bid_link, :buyer, :seller)
                            """,
                            item,
                        )
                    else:
                        DB.execute(
                            """
                            INSERT OR REPLACE INTO super_mats 
                            (id, id_auction, name, quantity, unit_price, price, bid_link, buyer, seller)
                            VALUES (:id, :id_auction, :name, :quantity, :unit_price, :price, :bid_link, :buyer, :seller)
                            """,
                            item,
                        )

            return item_data

        async def fetch(id: str, live=False) -> BeautifulSoup:
            path = f"itemlist{id}"

            if live or path not in cls.html_cache:
                # Fetch but rate-limited
                @super_limit
                async def _fetch() -> BeautifulSoup:
                    html: str = await fetch_page(
                        cls.HOME_URL / path, content_type="text"
                    )
                    page = BeautifulSoup(html, "html.parser")
                    cls.html_cache[path] = html
                    cls.HTML_CACHE_FILE.dump(cls.html_cache)
                    return page

                page = await _fetch()

                # Update db
                is_complete = "Auction ended" in page.select_one("#timing").text  # type: ignore
                with DB:
                    DB.execute(
                        """
                        UPDATE super_auctions SET
                            is_complete = ?,
                            last_fetch_time = ?
                        """,
                        (is_complete, time.time()),
                    )
            else:
                page = BeautifulSoup(cls.html_cache[path], "html.parser")

            return page

        def parse_quirky_row(auction_id: str, rowEls: ResultSet[Tag]) -> dict | None:
            [codeEl, nameEl, infoEl, currentBidEl, nextBidEl, sellerEl] = rowEls

            if auction_id == "194262" and codeEl.text == "Mat00":
                # Pony figurine set -> 1 Pony figurine set
                nameEl.string = "1 " + nameEl.text
                return parse_mat_row(rowEls)
            if infoEl.text.startswith("seller: "):
                logger.info(f'Discarding info for [{nameEl.text}] - "{infoEl.text}"')
                infoEl.string = ""
                return parse_row(rowEls)

            return None

        def parse_row(rowEls: ResultSet[Tag]) -> dict:
            [codeEl, *_] = rowEls
            if codeEl.text.startswith("Mat"):
                return parse_mat_row(rowEls)
            else:
                return parse_equip_row(rowEls)

        def parse_mat_row(rowEls: ResultSet[Tag]) -> dict:
            [codeEl, nameEl, infoEl, currentBidEl, nextBidEl, sellerEl] = rowEls

            id = codeEl.text
            seller = sellerEl.text

            [quantity, name] = PATTS["quant_name"].search(nameEl.text).groups()  # type: ignore
            quantity = int(quantity)

            [buyer, bid_link, price] = parse_price_buyer(currentBidEl)
            unit_price = price / quantity if price else None

            data = dict(
                _type="mat",
                id=id,
                name=name,
                quantity=quantity,
                unit_price=unit_price,
                price=price,
                bid_link=bid_link,
                buyer=buyer,
                seller=seller,
            )
            return data

        def parse_equip_row(rowEls: ResultSet[Tag]) -> dict:
            [codeEl, nameEl, infoEl, currentBidEl, nextBidEl, sellerEl] = rowEls

            id = codeEl.text
            name = nameEl.text
            [eid, key, is_isekai] = parse_equip_link(nameEl.select_one("a")["href"])  # type: ignore
            [buyer, bid_link, price] = parse_price_buyer(currentBidEl)
            seller = sellerEl.text

            if infoEl.text == "":
                # Super didn't provide any info
                level = None
                stats = "{}"
            else:
                info_text = re.search(PATTS["level_stats"], infoEl.text).group(1)  # type: ignore

                [level_text, *stat_list] = info_text.split(",")
                if level_text == "Unassigned":
                    level = 0
                elif level_text == "n/a":
                    level = None
                else:
                    level = int(level_text)
                    if int(level) != float(level):
                        raise Exception

                stat_list = [txt.split(" ") for txt in stat_list]
                stat_list = [
                    [" ".join(parts[:-1]).strip(), parts[-1].strip()]
                    for parts in stat_list
                ]
                stats = {k: v for k, v in stat_list}
                stats = json.dumps(stats)

            data = dict(
                _type="equip",
                id=id,
                name=name,
                eid=eid,
                key=key,
                is_isekai=is_isekai,
                level=level,
                stats=stats,
                price=price,
                bid_link=bid_link,
                buyer=buyer,
                seller=seller,
            )
            return data

        def parse_price_buyer(
            currentBidEl: Tag,
        ) -> tuple[str, str | None, int] | tuple[None, None, None]:
            m = PATTS["price_buyer"].search(currentBidEl.text)
            if m:
                # Item was sold
                [price, buyer] = m.groups()
                price = price_to_int(price)
                link_el = currentBidEl.select_one("a")
                bid_link = str(link_el["href"]) if link_el else None
                return (buyer, bid_link, price)
            else:
                # Item was unsold
                if currentBidEl.text != "0":
                    raise Exception
                return (None, None, None)

        return await main()


if __name__ == "__main__":
    # fmt: off
    from config import init_logging
    import asyncio

    async def main():
        await SuperScraper.refresh_list()
        await SuperScraper.fetch_updates()
    asyncio.run(main())
