import json
import re
import time
from dataclasses import dataclass
from datetime import datetime

import bs4
from bs4 import BeautifulSoup, Tag
from classes.db import DB, create_tables
from config import paths
from config import logger
from utils.json_cache import JsonCache
from utils.parse import parse_equip_link, price_to_int
from utils.rate_limit import rate_limit
from utils.scrape import fetch_page
from yarl import URL

super_limit = rate_limit(calls=1, period=5, scope="super")


@dataclass
class Cell:
    text: str
    href: str | None


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
                SELECT id, is_complete FROM super_auctions
                WHERE last_fetch_time is NULL
                OR is_complete = 0
                OR is_complete is NULL
                """
            ).fetchall()

        for r in rows:
            await cls.fetch_auction(r["id"], allow_cached=bool(r["is_complete"]))

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
            row_data: list[dict] = []
            for el in row_els:
                data = parse_row(el)
                insert_db_row(data)
                row_data.append(data)

            return row_data

        def parse_row(tr: bs4.Tag) -> dict:
            # Check pre-conditions
            cells = [cls._el_to_dict(td) for td in tr.select("td")]
            [idxCell, dateCell, _, _, _, threadCell] = cells
            assert threadCell.href

            # Parse
            title = idxCell.text
            end_time = datetime.strptime(
                dateCell.text + "+0000", r"%m-%d-%Y%z"
            ).timestamp()
            id = re.search(r"showtopic=(\d+)", threadCell.href).group(1)  # type: ignore

            # Return
            data = dict(id=id, title=title, end_time=end_time)
            return data

        def insert_db_row(data: dict) -> None:
            with DB:
                DB.execute(
                    """
                    INSERT OR IGNORE INTO super_auctions
                    (id, title, end_time, is_complete, last_fetch_time) VALUES (:id, :title, :end_time, NULL, 0)
                    """,
                    data,
                )

        return await main()

    @classmethod
    async def fetch_auction(cls, auction_id: str, allow_cached=True) -> list[dict]:
        """Fetch itemlist for auction

        Args:
            auction_id:

        Raises:
            Exception:
        """

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
            page = await fetch(auction_id, allow_cached=allow_cached)
            trs = page.select("tbody > tr")
            rows: list[list[Cell]] = []
            for tr in trs:
                cells = [cls._el_to_dict(td) for td in tr.select("td")]
                assert len(cells) == 6
                rows.append(cells)

            # Parse auction data
            item_data = []
            for cells in rows:
                try:
                    data = parse_quirky_row(auction_id, cells) or parse_row(cells)
                    data["id_auction"] = auction_id
                    item_data.append(data)
                except:
                    logger.exception(f"Failed to parse {cells}")
                    with DB:
                        item_code = cells[0].text
                        item_name = cells[1].text
                        tr = trs[rows.index(cells)]
                        DB.execute(
                            """
                            INSERT OR REPLACE INTO super_fails
                            (id, id_auction, summary, html) VALUES (?, ?, ?, ?)
                            """,
                            (item_code, auction_id, item_name, str(tr)),
                        )

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

        async def fetch(id: str, allow_cached=False) -> BeautifulSoup:
            path = f"itemlist{id}"

            if not allow_cached or path not in cls.html_cache:
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

        def parse_quirky_row(auction_id: str, cells: list[Cell]) -> dict | None:
            [codeCell, nameCell, infoCell, *_] = cells

            if auction_id == "194262" and codeCell.text == "Mat00":
                # Pony figurine set -> 1 Pony figurine set
                nameCell.text = "1 " + nameCell.text
                return parse_mat_row(cells)
            if infoCell.text.startswith("seller: "):
                logger.info(
                    f'Discarding info "{infoCell.text}" for "{nameCell.text}" in auction {auction_id}'
                )
                infoCell.text = ""
                return parse_row(cells)

            return None

        def parse_row(cells: list[Cell]) -> dict:
            [codeCell, *_] = cells
            if codeCell.text.startswith("Mat"):
                return parse_mat_row(cells)
            else:
                return parse_equip_row(cells)

        def parse_mat_row(rowEls: list[Cell]) -> dict:
            [codeCell, nameCell, _, currentBidCell, _, sellerCell] = rowEls

            id = codeCell.text
            seller = sellerCell.text

            [quantity, name] = PATTS["quant_name"].search(nameCell.text).groups()  # type: ignore
            quantity = int(quantity)

            [buyer, bid_link, price] = parse_price_buyer(currentBidCell)
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

        def parse_equip_row(cells: list[Cell]) -> dict:
            [codeCell, nameCell, infoCell, currentBidCell, _, sellerCell] = cells

            id = codeCell.text
            name = nameCell.text
            seller = sellerCell.text
            [eid, key, is_isekai] = parse_equip_link(nameCell.href)  # type: ignore
            [buyer, bid_link, price] = parse_price_buyer(currentBidCell)

            if infoCell.text == "":
                # Super didn't provide any info
                level = None
                stats = "{}"
            else:
                # Verify we're parsing smth like "500, ADB 94%, EDB 55%, ..."
                assert re.search(PATTS["level_stats"], infoCell.text)

                [level_text, *stat_list] = infoCell.text.split(",")
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
            cell: Cell,
        ) -> tuple[str, str | None, int] | tuple[None, None, None]:
            m = PATTS["price_buyer"].search(cell.text)
            if m:
                # Item was sold
                [price, buyer] = m.groups()
                price = price_to_int(price)
                return (buyer, cell.href, price)
            else:
                # Item was unsold
                if cell.text != "0":
                    raise Exception
                return (None, None, None)

        return await main()

    @staticmethod
    def _el_to_dict(el: Tag) -> Cell:
        a = el.select_one("a")
        result = Cell(text=el.text, href=str(a["href"]) if a else None)
        return result


if __name__ == "__main__":
    # fmt: off
    import asyncio
    async def main():
        await SuperScraper.refresh_list()
        await SuperScraper.fetch_updates()
    asyncio.run(main())
