from dataclasses import dataclass
from datetime import datetime
import re
from typing import Any, Callable, Optional
from classes.core.discord.checks import app_check_perms, check_perms

from classes.core.discord.keywords import (
    BuyerKey,
    LinkKey,
    MaxPriceKey,
    MinPriceKey,
    SellerKey,
    YearKey,
)
from classes.core.discord.table import Col, Table, clip
from classes.core.server import types as Api
from discord import Interaction, app_commands
from discord.ext.commands import Context
from discord.ext import commands
from utils.discord import alias_by_prefix, extract_quoted, paginate
from utils.http import fetch_page
from utils.misc import compose_1arg_fns
from utils.parse import create_equip_link, int_to_price
from classes.core.discord import types as types

from classes.core import discord


@dataclass
class EquipCog(commands.Cog):
    bot: "discord.AmyBot"

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
    @app_commands.check(app_check_perms("equip"))
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

        params = types._Equip.FetchParams()

        params["name"] = equip_name or ""
        params["min_date"] = noop(str, YearKey.convert)(year)
        params["min_price"] = noop(MinPriceKey.convert)(min)
        params["max_price"] = noop(MinPriceKey.convert)(max)
        params["seller"] = seller
        params["buyer"] = buyer

        opts = types._Equip.FormatOptions()
        opts["show_link"] = bool(show_link)
        if show_seller or seller:
            opts["show_seller"] = True
        if show_buyer or buyer:
            opts["show_buyer"] = True

        # for pg in await self._equip(params, opts):
        pages = await self._equip(params, opts)
        if len(pages) == 1:
            await itn.response.send_message(pages[0])
        elif len(pages) > 1:
            # Create pages-omitted-warning
            if (rem := len(pages) - 1) == 1:
                trailer = "1 page omitted. Try !equip to see more."
            else:
                trailer = f"{rem} pages omitted. Try !equip to see more."
            if pages[0][-3:] != "```":
                trailer = "\n" + trailer

            # Append
            resp = paginate(pages[0], page_size=2000 - len(trailer))
            resp = resp[0] + trailer

            # Send
            await itn.response.send_message(resp)

    @commands.command(
        name="equip",
        aliases=alias_by_prefix("equip", starting_at=2),
        extras=dict(id="equip"),
    )
    @commands.check(check_perms("equip"))
    async def text_equip(self, ctx: Context, *, msg: str):
        async def main():
            params, opts = parse(msg)

            for pg in await self._equip(params, opts):
                await ctx.send(pg)

        def parse(
            text: str,
        ) -> tuple[types._Equip.FetchParams, types._Equip.FormatOptions]:
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

            # Split into params and options
            params = data.copy()
            opts = types._Equip.FormatOptions()

            if params.get("link"):
                opts["show_link"] = True
                del params["link"]
            if params.get("seller") is True:
                opts["show_seller"] = True
                del params["seller"]
            if params.get("buyer") is True:
                opts["show_buyer"] = True
                del params["buyer"]

            # Return
            return params, opts  # type: ignore

        await main()

    async def _equip(
        self, params: types._Equip.FetchParams, opts: types._Equip.FormatOptions
    ) -> list[str]:
        async def main():
            # Fetch
            items = sorted(
                await fetch(params), key=lambda d: d["price"] or 0, reverse=True
            )
            groups = group_by_name(items)
            tables = {
                name: create_table(
                    lst,
                    show_buyer=opts.get("show_buyer", False),
                    show_seller=opts.get("show_seller", False),
                )
                for name, lst in groups.items()
            }

            # Create printout
            msg = ""
            if opts.get("show_link"):

                def fmt_row(row_text: str, row_type: str, idx: int | None):
                    if row_type == "BODY":
                        item = items[idx]  # type: ignore
                        url = create_equip_link(
                            item["eid"], item["key"], item["is_isekai"]
                        )
                        result = f"`{row_text} | `{url}"
                    else:
                        result = f"`{row_text} | `"
                    return result

                table_texts = {
                    name: tbl.print(cb=fmt_row) for name, tbl in tables.items()
                }
                pieces = [f"**{name}**\n{text}" for name, text in table_texts.items()]
                msg = "\n\n".join(pieces)
            else:
                pieces = [f"@ {name}\n{tbl.print()}" for name, tbl in tables.items()]
                msg = "\n\n".join(pieces)
                msg = f"```py\n{msg}```"

            # Paginate
            pages = paginate(msg)
            return pages

        async def fetch(params: types._Equip.FetchParams) -> list[Api.SuperEquip]:
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

        def group_by_name(
            items: list[Api.SuperEquip],
        ) -> dict[str, list[Api.SuperEquip]]:
            map = {}
            for item in items:
                map.setdefault(item["name"], []).append(item)
            return map

        def create_table(
            items: list[Api.SuperEquip],
            show_buyer=False,
            show_seller=True,
        ) -> Table:
            def main() -> Table:
                tbl = Table()

                # Price col
                prices = items
                price_col = Col(title="Price", stringify=fmt_price, align="right")
                tbl.add_col(price_col, prices)

                # User cols
                if show_buyer:
                    buyers = [d["buyer"] or "" for d in items]
                    buyer_col = Col(title="Buyer")
                    tbl.add_col(buyer_col, buyers)
                if show_seller:
                    sellers = [d["seller"] or "" for d in items]
                    seller_col = Col(title="Seller")
                    tbl.add_col(seller_col, sellers)

                # Stats col
                stats = [d["stats"] for d in items]
                stat_col = Col(title="Stats", stringify=fmt_stat_dct)
                tbl.add_col(stat_col, stats)

                # Level col
                levels = [d["level"] or 0 for d in items]
                level_col = Col(title="Level", align="right")
                tbl.add_col(level_col, levels)

                # Date col
                dates = [
                    (d["auction"]["end_time"], d["auction"]["title"]) for d in items
                ]
                date_col = Col(
                    title="# Auction / Date", stringify=lambda x: fmt_date(*x)
                )
                tbl.add_col(date_col, dates)

                # Remove padding at edges
                tbl.cols[0].padding_left = 0
                tbl.cols[-1].padding_right = 0

                return tbl

            def fmt_price(item: Api.SuperEquip) -> str:
                price = item["price"]
                next_bid = item["next_bid"]

                if price is None or price <= 0:
                    next_bid_str = int_to_price(next_bid, precision=(0, 0, 1))
                    next_bid_str = f"({next_bid_str})"
                    return next_bid_str
                elif price > 0:
                    return int_to_price(price, precision=(0, 0, 1))
                else:
                    raise Exception("Pylance please...")

            def fmt_stat_dct(x: dict) -> str:
                def value(k, v) -> int:
                    k = k.lower()
                    if any(x in k for x in ["forged"]):
                        return 30
                    elif any(x in k for x in ["edb", "adb", "mdb"]):
                        return 20
                    elif any(x in k for x in ["prof", "blk", "iw"]):
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

            def fmt_date(ts, title):
                title_str = "#S" + title[:3].zfill(3)
                ts_str = datetime.fromtimestamp(ts).strftime("%m-%Y")
                return f"{title_str} / {ts_str}"

            return main()

        return await main()
