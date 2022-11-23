from dataclasses import dataclass

from discord.ext import commands
from discord.ext.commands import Context

from . import discord_bot


@dataclass
class MetaCog(commands.Cog):
    bot: "discord_bot.DiscordBot"

    @commands.command(name="enable_slash_commands")
    async def enable_slash_commands(self, ctx: Context):
        if ctx.guild:
            self.bot.tree.copy_global_to(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.message.add_reaction("👍")

    @commands.command(name="disable_slash_commands")
    async def disable_slash_commands(self, ctx: Context):
        if ctx.guild:
            self.bot.tree.clear_commands(guild=ctx.guild)
            await self.bot.tree.sync(guild=ctx.guild)
            await ctx.message.add_reaction("👍")
