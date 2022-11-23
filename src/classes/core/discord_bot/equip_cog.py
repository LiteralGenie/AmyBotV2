from dataclasses import dataclass
from discord.ext import commands
from . import discord_bot


@dataclass
class EquipCog(commands.Cog):
    bot: "discord_bot.DiscordBot"

    @commands.hybrid_command()
    async def hello(self, ctx):
        """Says hello"""
        print("here")
