from dataclasses import dataclass
from datetime import datetime
from functools import partial
import re
from typing import Any, Callable, Optional, Type

from classes.core.discord_bot.keywords import (
    BuyerKey,
    Keyword,
    LinkKey,
    MaxPriceKey,
    MinPriceKey,
    SellerKey,
    YearKey,
)
from classes.core.discord_bot.table import Col, Table, clip
from classes.core.server import types as Api
from discord import Interaction, app_commands
from discord.ext.commands import Context
from discord.ext import commands
from utils.discord import alias_by_prefix, extract_quoted, paginate
from utils.http import fetch_page
from utils.misc import compose_1arg_fns
from utils.parse import int_to_price

from classes.core import discord_bot


@dataclass
class EquipCog(commands.Cog):
    bot: "discord_bot.DiscordBot"

    @app_commands.command(name="equip")
    @app_commands.describe(
        equip_name='Equip name (eg "leg oak heimd")',
        year="Ignore old auctions (eg 22)",
        show_link="Show equip link",
        min="Minimum price (eg 500k)",
        max="Maximum price (eg 1m)",
        seller="Username of seller",
        buyer="Username of buyer",
    )
    async def app_equip(
        self,
        itn: Interaction,
        equip_name: str,
        year: Optional[int],
        show_link: Optional[bool],
        min: Optional[str],
        max: Optional[str],
        show_seller: Optional[bool],
        seller: Optional[str],
        show_buyer: Optional[bool],
        buyer: Optional[str],
    ):
        """Search auction data for equips"""

        # If input is None, return None. Else apply each function in fns, from left to right
        noop = lambda *fns: lambda x: compose_1arg_fns(*fns)(x) if x is not None else x

        data = dict()
        data["name"] = noop(str)(equip_name)
        data["min_date"] = noop(str, YearKey.convert)(year)
        data["link"] = bool(show_link)
        data["min_price"] = noop(MinPriceKey.convert)(min)
        data["max_price"] = noop(MinPriceKey.convert)(max)
        data["seller"] = noop(lambda name: name if name else True)(seller)
        data["buyer"] = noop(lambda name: name if name else True)(buyer)

        if seller is None and show_seller:
            data["seller"] = True
        if buyer is None and show_buyer:
            data["buyer"] = True

        resp = await self._equip(data)

    @commands.command(name="equip", aliases=alias_by_prefix("equip", starting_at=2))
    async def text_equip(self, ctx: Context, *, msg: str):
        async def main():
            data = parse(msg)
            for pg in await self._equip(data):
                await ctx.send(pg)

        def parse(text: str) -> dict:
            # Pair dict key with prefix / extractor / converter
            parsers: list[
                tuple[
                    str,
                    str,
                    Callable[[str], tuple[str, str | None]],
                    Callable[[str], Any],
                ]
            ] = [
                ("min_date", YearKey.prefix, YearKey.extract, YearKey.convert),
                ("link", LinkKey.prefix, LinkKey.extract, lambda x: x is not None),
                (
                    "min_price",
                    MinPriceKey.prefix,
                    MinPriceKey.extract,
                    MinPriceKey.convert,
                ),
                (
                    "max_price",
                    MaxPriceKey.prefix,
                    MaxPriceKey.extract,
                    MaxPriceKey.convert,
                ),
                (
                    "seller",
                    SellerKey.prefix,
                    SellerKey.extract,
                    lambda x: x if x else True,
                ),
                (
                    "buyer",
                    BuyerKey.prefix,
                    BuyerKey.extract,
                    lambda x: x if x else True,
                ),
            ]
            rem = text

            # Isolate any quoted sections
            # eg "the quick'brown dog'" becomes ("the ", [("brown dog", "quick")])
            (rem, quoted) = extract_quoted(rem)

            # Extract keywords from remaining
            data = dict()
            for key, _, extract, convert in parsers:
                rem, raw = extract(rem)
                if raw is not None:
                    val = convert(raw)
                    if val is not None:
                        data[key] = val

            # Extract keyword data from quoted sections with a prefix (eg quick"brown dog")
            for q_key, q_val in quoted:
                if q_key is not None:
                    key, convert = next(
                        (key, convert)
                        for (key, prefix, _, convert) in parsers
                        if prefix == q_key
                    )
                    try:
                        val = convert(q_val)
                        if val is not None:
                            data[key] = val
                    except:
                        continue

            # rem should be kw-free now
            # Bring back and quoted sections that did not represent keywords
            for q_key, q_val in quoted:
                if q_key is None:
                    rem += " " + q_val
            data["name"] = rem

            # Return
            return data

        await main()

    async def _equip(self, params: dict) -> list[str]:
        async def main():
            # Massage params
            show_link = bool(params.get("link"))
            show_buyer = bool(params.get("buyer"))
            show_seller = bool(params.get("seller"))
            if params.get("buyer") is True:
                del params["buyer"]
            if params.get("seller") is True:
                del params["seller"]

            # Fetch
            data = await fetch(params)

            # Get printout
            msg = fmt(
                "Test",
                data,
                show_link=show_link,
                show_buyer=show_buyer,
                show_seller=show_seller,
            )
            msg = f"```py\n{msg}```"
            pages = paginate(msg)
            return pages

        async def fetch(params: dict) -> list[Api.SuperEquip]:
            ep = self.bot.api_url / "super" / "search_equips"

            # Search for equip that contains all words
            # so order doesn't matter and partial words are okay
            # eg "lege oak heimd" should match "Legendary Oak Staff of Heimdall"
            name_fragments = re.sub(r"\s", ",", params.get("name", "").strip())
            ep %= dict(name=name_fragments)

            keys: list[str] = [
                "min_date",
                "min_price",
                "max_price",
                "seller",
                "buyer",
            ]
            for k in keys:
                if (v := params.get(k)) is not None:
                    ep %= {k: str(v).strip()}

            resp = await fetch_page(ep, content_type="json")
            return resp

        def fmt(
            name: str,
            data: list[Api.SuperEquip],
            show_link=False,
            show_buyer=False,
            show_seller=True,
        ) -> str:
            def main():
                tbl = get_table(data, show_link)
                msg = "\n".join([f"@ {name}", "", tbl.print()])
                return msg

            def get_table(items: list[Api.SuperEquip], show_link: bool) -> Table:
                items = sorted(items, key=lambda d: d["price"] or 0, reverse=True)
                tbl = Table()

                prices = [d["price"] or 0 for d in items]
                price_col = Col(
                    title="Price",
                    stringify=lambda x: int_to_price(x, precision=(0, 0, 1)),
                    align="right",
                )
                tbl.add_col(price_col, prices)

                levels = [d["level"] or 0 for d in items]
                level_col = Col(title="Level", align="right")
                tbl.add_col(level_col, levels)

                stats = [d["stats"] for d in items]
                stat_col = Col(title="Stats", stringify=fmt_stat_dct)
                tbl.add_col(stat_col, stats)

                if show_buyer:
                    buyers = [d["buyer"] or "" for d in items]
                    buyer_col = Col(title="Buyer")
                    tbl.add_col(buyer_col, buyers)

                if show_seller:
                    sellers = [d["seller"] or "" for d in items]
                    seller_col = Col(title="Seller")
                    tbl.add_col(seller_col, sellers)

                # fmt: off
                dates = [
                    (d["auction"]["end_time"], d["auction"]["title"]) for d in items
                ]
                def fmt_date(x):
                    ts, title = x
                    title_str = "#S" + title[:3].zfill(3)
                    ts_str = datetime.fromtimestamp(ts).strftime("%m-%Y")
                    return f"{title_str} / {ts_str}"
                date_col = Col(title="# Auction / Date", stringify=fmt_date)
                tbl.add_col(date_col, dates)
                # fmt: on

                tbl.cols[0].padding_left = 0
                tbl.cols[-1].padding_right = 0

                return tbl

            def fmt_stat_dct(x: dict) -> str:
                def value(k, v) -> int:
                    k = k.lower()
                    if any(x in k for x in ["edb", "adb", "mdb"]):
                        return 30
                    elif any(x in k for x in ["prof", "blk"]):
                        return 20
                    elif any(x in k for x in ["dex", "str", "agi", "int", "wis"]):
                        return 10
                    else:
                        return 1

                sorted_ = sorted(x.items(), key=lambda it: value(*it), reverse=True)
                items = [f"{k} {v}" for k, v in sorted_]

                simplified = [
                    re.sub(r".* ((?:EDB|Prof))", r"\1", x, flags=re.IGNORECASE)
                    for x in items
                ]
                text = ", ".join(simplified[:3])
                clipped = clip(text, 15, "...")
                return clipped

            return main()

        return await main()
