import discord
import toml
from classes.core.discord_bot.equip_cog import EquipCog
from config import paths
from discord.ext import commands

from config import logger

logger = logger.bind(tags=["discord_bot"])


class DiscordBot(commands.Bot):
    secrets: dict
    config: dict

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(*args, intents=intents, **kwargs)

        self.reload_secrets()
        self.reload_config()

    async def on_ready(self):
        logger.info(f"Logged in as {bot.user}")
        await self.add_cog(EquipCog(self))

    def reload_secrets(self):
        self.secrets = toml.load(paths.CONFIG_DIR / "secrets.toml")

    def reload_config(self):
        self.config = toml.load(paths.CONFIG_DIR / "discord_bot.toml")
        self.command_prefix = self.config["prefix"]

    def run(self):
        assert self.secrets
        super().run(self.secrets["DISCORD_KEY"])


bot = DiscordBot(command_prefix="?")


if __name__ == "__main__":
    bot.run()
