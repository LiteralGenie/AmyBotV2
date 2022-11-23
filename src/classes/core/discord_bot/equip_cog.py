from discord.ext import commands


class EquipCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def hello(self, ctx):
        """Says hello"""
        print("here")
