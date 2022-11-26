import asyncio
import copy
from pathlib import Path
from typing import Optional, TypedDict

from config import logger, paths
from hachiko.hachiko import AIOEventHandler, AIOWatchdog
from tomlkit.toml_document import TOMLDocument
from utils.misc import dump_toml, load_toml


class _PermissionException(TypedDict):
    action: "Required[bool]"

    # If all conditions below are met, the value of action is returned
    user: int
    channel: int
    role: list[int]


class _CommandPermission(TypedDict, total=True):
    default: "Required[bool]"  # Default if no relevant _PermissionException
    exceptions: list[_PermissionException]


class _GuildPermissions(TypedDict):
    default: "Required[bool]"  # Default if no relevant _CommandPermission
    commands: dict[str, _CommandPermission]


class PermissionsService:
    perms: dict[int, TOMLDocument]
    default_perms: TOMLDocument

    def __init__(self):
        # Load default perms
        try:
            self.default_perms = self._read_file(
                paths.CONFIG_DIR / "default_perms.toml"
            )
        except:
            logger.exception("Unable to load default perms file")
            raise

        # Load guild perms
        self.perms = dict()
        for fp in paths.PERMS_DIR.glob("*.toml"):
            self.load_file(fp, invalidate=True)

        # Watch for changes
        _PermDirWatcher(self).start()

    def check(
        self,
        command: str,
        guild: int,
        user: int = -1,
        channel: int = -1,
        roles: Optional[list[int]] = None,
    ) -> bool:
        """Check if command is allowed based on permisisons file

        Args:
            command:
            guild: 0 for DMs
            user:
            channel:
            roles:
        """
        roles = roles or []

        # Get guild permissions
        if guild not in self.perms:
            self.register_guild(guild)
        guild_perms: _GuildPermissions = self.perms[guild]  # type: ignore

        # Get command permissions
        command_dct = guild_perms.get("commands")
        if command_dct is None:
            return guild_perms["default"]
        command_perms = command_dct.get(command)
        if command_perms is None:
            return guild_perms["default"]

        # Check for exceptions
        exceptions = command_perms.get("exceptions")
        if exceptions is None:
            return guild_perms["default"]

        for ex in exceptions:
            isUser = ex.get("user") == user
            isChannel = ex.get("channel") == channel
            isRole = "role" in ex and all(r in roles for r in ex["role"])

            if isUser and isChannel and isRole:
                return ex["action"]

        # Return server default
        return guild_perms["default"]

    def load_file(self, fp: Path, invalidate=True):
        def rename():
            new_fp = fp.parent / (fp.name + ".invalid")
            logger.exception(f"Invalid perms file. Renaming {fp} to {new_fp.name}")
            fp.replace(new_fp)

        try:
            guild_id = int(fp.stem)
        except:
            rename()
            return

        try:
            perms = self._read_file(fp)
            self.perms[guild_id] = perms
        except:
            if invalidate:
                rename()
                if guild_id in self.perms:
                    logger.exception(f"Reverting {fp} to previous state")
                    dump_toml(self.perms[guild_id], fp)

    def register_guild(self, id: int) -> None:
        if id not in self.perms:
            guild_perms = copy.deepcopy(self.default_perms)
            self.perms[id] = guild_perms

            fp = paths.PERMS_DIR / f"{id}.toml"
            dump_toml(guild_perms, fp)

    @classmethod
    def _read_file(cls, fp: Path) -> TOMLDocument:
        """Read and validate permissions file"""

        def main():
            data = load_toml(fp)
            validate_guild(data)
            return data

        def validate_guild(data: dict):
            if "default" not in data:
                raise Exception

            if "commands" in data:
                if not isinstance(data, dict):
                    raise Exception

                for cmd in data["commands"].values():
                    validate_command(cmd)

        def validate_command(data: dict):
            if "default" not in data:
                raise Exception

            if "exceptions" in data:
                if not isinstance(data, list):
                    raise Exception

                for ex in data["exceptions"]:
                    validate_exception(ex)

        def validate_exception(data: dict):
            if "action" not in data:
                raise Exception

        return main()


class _PermDirWatcher(AIOEventHandler):
    def __init__(self, service: PermissionsService):
        super().__init__(loop=asyncio.get_running_loop())
        self.service = service

    def start(self):
        AIOWatchdog(str(paths.PERMS_DIR), event_handler=self).start()

    async def on_created(self, event):
        if not self._is_toml_file(event.src_path):
            return

        logger.debug(f"Perm file created: {event.src_path}")
        self.service.load_file(Path(event.src_path))

    async def on_modified(self, event):
        if not self._is_toml_file(event.src_path):
            return

        logger.debug(f"Perm file updated: {event.src_path}")
        self.service.load_file(Path(event.src_path))

    @staticmethod
    def _is_toml_file(fp: str):
        return fp.lower().endswith(".toml")
