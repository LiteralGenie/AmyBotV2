from dataclasses import dataclass
from functools import partial
from typing import Optional

from classes.core.discord_bot.keywords import (
    BuyerKey,
    Keyword,
    LinkKey,
    MaxPriceKey,
    MinPriceKey,
    NameKey,
    SellerKey,
    YearKey,
)
from classes.core.discord_bot.table import Col, Table, clip
from classes.core.server import types as Api
from discord import Interaction, app_commands
from discord.ext.commands import Context
from discord.ext import commands
from utils.discord import alias_by_prefix, extract_quoted
from utils.http import fetch_page
from utils.parse import int_to_price

from classes.core import discord_bot


@dataclass
class EquipCog(commands.Cog):
    bot: "discord_bot.DiscordBot"

    @app_commands.command(name="equip")
    @app_commands.describe(
        equip_name='Equip name (eg "leg oak heimd")',
        year="Ignore old auctions (eg 22)",
        link="Show equip link",
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
        link: Optional[str],
        min: Optional[str],
        max: Optional[str],
        seller: Optional[str],
        buyer: Optional[str],
    ):
        """Search auction data for equips"""
        data = dict(
            name=NameKey.convert(equip_name),
            min_date=YearKey.convert(str(year)) if year else None,
            link=LinkKey.convert(link),
            min_price=MaxPriceKey.convert(min),
            max_price=MaxPriceKey.convert(max),
            seller=SellerKey.convert(seller),
            buyer=BuyerKey.convert(buyer),
        )
        resp = await self._equip(data)

    @commands.command(name="equip", aliases=alias_by_prefix("equip", starting_at=2))
    async def text_equip(self, ctx: Context, *, msg: str):
        async def main():
            data = parse(msg)
            resp = await self._equip(data)

        def parse(text: str) -> dict:
            # Maps parser to alias
            keys: list[tuple[Keyword, str]] = [
                (YearKey, "min_date"),
                (LinkKey, "link"),
                (MinPriceKey, "min_price"),
                (MaxPriceKey, "max_price"),
                (SellerKey, "seller"),
                (BuyerKey, "buyer"),
            ]
            rem = text

            # Isolate any quoted sections
            # eg "the quick'brown dog'" becomes ("the ", [("brown dog", "quick")])
            (rem, quoted) = extract_quoted(rem)

            # Extract keywords from remaining
            data = dict()
            for kw, alias in keys:
                result = kw.parse(rem)
                if result[1] is not None:
                    rem = result[0]
                    data[alias] = result[1]

            # Extract keywords from quoted sections
            for q_key, q_val in quoted:
                if q_key is not None:
                    kw, alias = next(
                        (kw, alias) for kw, alias in keys if kw.key == q_key
                    )
                    data[alias] = kw.convert(q_val)

            # rem should be kw-free now
            # Bring back and quoted sections that did not represent keywords
            for q_key, q_val in quoted:
                if q_key is None:
                    rem += " " + q_val
            data["name"] = NameKey.convert(rem)

            # Return
            return data

        await main()

    async def _equip(self, params: dict) -> str:
        async def main():
            data = await fetch()
            msg = fmt(data, show_link=params.get("link", False))
            print(msg)
            return msg

        async def fetch() -> list[Api.SuperEquip]:
            ep = self.bot.api_url / "super" / "search_equips"

            keys: list[str] = [
                "name",
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

        def fmt(data: list[Api.SuperEquip], show_link=False) -> str:
            def main():
                return fmt_item(data, show_link)

            def fmt_item(data: list[Api.SuperEquip], show_link: bool) -> str:
                data = sorted(data, key=lambda d: d["price"] or 0, reverse=True)
                tbl = Table()

                prices = [d["price"] or 0 for d in data]
                price_col = Col(
                    title="Price",
                    stringify=lambda x: int_to_price(x, precision=(0, 0, 1)),
                    align="right",
                )
                tbl.add_col(price_col, prices)

                levels = [d["level"] or 0 for d in data]
                level_col = Col(title="Level")
                tbl.add_col(level_col, levels)

                stats = [d["stats"] or 0 for d in data]
                stat_col = Col(title="Stats", stringify=lambda x: clip(x, 15, "..."))
                tbl.add_col(stat_col, stats)

                return tbl.print()

            return main()

        return await main()
