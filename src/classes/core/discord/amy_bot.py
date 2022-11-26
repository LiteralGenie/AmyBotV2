import discord
from tomlkit.toml_document import TOMLDocument
from yarl import URL
from classes.core.discord.equip_cog import EquipCog
from classes.core.discord.meta_cog import MetaCog
from classes.core.discord.services.permissions_service import PermissionsService
from classes.core.discord.watchers import DirectoryWatcher, FileWatcher
from config import paths
from discord.ext import commands

from config import logger
from utils.misc import dump_toml, load_toml

logger = logger.bind(tags=["discord_bot"])


class AmyBot(commands.Bot):
    secrets: TOMLDocument = None  # type: ignore
    config: TOMLDocument = None  # type: ignore
    api_url: URL
    permsService: PermissionsService

    def run(self):
        secrets = load_toml(paths.SECRETS_FILE)
        super().run(secrets["DISCORD_KEY"])  # type: ignore

    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__("fake_prefix", *args, intents=intents, **kwargs)

    async def on_ready(self):
        self.permsService = PermissionsService()

        self.init_secrets()
        self.init_config()

        await self.add_cog(EquipCog(self))
        await self.add_cog(MetaCog(self))  # should be last cog added

        logger.info(f"Logged in as {bot.user}")

    def init_secrets(self):
        """Read and validate secrets file. Also watch for changes."""
        fp = paths.SECRETS_FILE

        def load(*args) -> bool:
            # Read file
            doc = load_toml(fp)
            data = doc.value

            # Quit if invalid
            if not is_valid(data):
                new_fp = fp.with_suffix(fp.suffix + ".invalid")
                logger.exception(
                    f"Invalid secrets file. Renaming {fp} to {new_fp.name}"
                )
                fp.replace(new_fp)

                if self.secrets:
                    logger.info(f"Reverting secrets to previous state: {fp}")
                    dump_toml(self.secrets, fp)

                return False

            # Apply values
            self.secrets = doc
            return True

        def is_valid(data: dict) -> bool:
            try:
                assert isinstance(data.get("DISCORD_KEY"), str)
            except AssertionError:
                return False

            return True

        result = load()
        if result == False:
            raise Exception(f"Invalid secrets file: {fp}")

        FileWatcher(fp, load).start()

    def init_config(self):
        """Read and validate config file. Also watch for changes."""
        fp = paths.DISCORD_CONFIG

        def load(*args) -> bool:
            # Read file
            doc = load_toml(fp)
            data = doc.value

            # Check validity
            if not is_valid(data):
                new_fp = fp.with_suffix(fp.suffix + ".invalid")
                logger.exception(f"Invalid config file. Renaming {fp} to {new_fp.name}")
                fp.replace(new_fp)

                if self.config:
                    logger.info(f"Reverting config to previous state: {fp}")
                    dump_toml(self.config, fp)

                return False

            # Apply values
            self.config = doc
            self.command_prefix = data["prefix"]
            self.api_url = URL(data["api_url"])
            return True

        def is_valid(data: dict) -> bool:
            try:
                assert isinstance(data.get("prefix"), str)
                assert isinstance(data.get("api_url"), str)
            except AssertionError:
                return False

            return True

        result = load()
        if result == False:
            raise Exception(f"Invalid config file: {fp}")

        FileWatcher(fp, load).start()

    ###


bot = AmyBot()


if __name__ == "__main__":
    bot.run()
