from dataclasses import dataclass
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
from discord import Interaction, app_commands
from discord.ext import commands
from utils.discord import alias_by_prefix, extract_quoted
from utils.http import fetch_page
from utils.parse import price_to_int

from . import discord_bot


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
            seller_partial=SellerKey.convert(seller),
            buyer_partial=BuyerKey.convert(buyer),
        )
        print(data)
        resp = await self._equip(data)

    @commands.command(name="equip", aliases=alias_by_prefix("equip", starting_at=2))
    async def text_equip(self, ctx, *, msg: str):
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
                (SellerKey, "seller_partial"),
                (BuyerKey, "buyer_partial"),
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
            print(len(data), str(data)[:100])
            return str(data)

        async def fetch() -> list:
            ep = self.bot.api_url / "super" / "search_equips"

            keys: list[str] = [
                "name",
                "min_date",
                "min_price",
                "max_price",
                "seller_partial",
                "buyer_partial",
            ]

            for k in keys:
                if (v := params.get(k)) is not None:
                    ep %= {k: str(v).strip()}

            resp = await fetch_page(ep, content_type="json")
            return resp

        async def fmt():
            pass

        return await main()
