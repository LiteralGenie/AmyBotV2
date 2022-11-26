import discord
from yarl import URL
from classes.core.discord.equip_cog import EquipCog
from classes.core.discord.meta_cog import MetaCog
from classes.core.discord.services.permissions_service import PermissionsService
from config import paths
from discord.ext import commands

from config import logger
from utils.misc import load_toml

logger = logger.bind(tags=["discord_bot"])


class AmyBot(commands.Bot):
    secrets: dict
    config: dict
    api_url: URL
    permsService: PermissionsService

    def run(self):
        assert self.secrets
        super().run(self.secrets["DISCORD_KEY"])

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__("fake_prefix", *args, intents=intents, **kwargs)

        self.reload_secrets()
        self.reload_config()

    async def on_ready(self):
        logger.info(f"Logged in as {bot.user}")

        self.reload_services()

        await self.add_cog(EquipCog(self))
        await self.add_cog(MetaCog(self))  # should be last cog added

    def reload_services(self):
        self.permsService = PermissionsService()

    def reload_secrets(self):
        self.secrets = load_toml(paths.CONFIG_DIR / "secrets.toml").value  # type: ignore

    def reload_config(self):
        self.config = load_toml(paths.CONFIG_DIR / "discord_bot.toml").value  # type: ignore

        self.command_prefix = self.config["prefix"]
        self.api_url = URL(self.config["api_url"])

    ###


bot = AmyBot()


if __name__ == "__main__":
    bot.run()
