from loguru import logger
import loguru
from config import paths


def init_logger():
    def main():
        logger.add(
            paths.LOG_DIR / "amy.log",
            rotation="10 MB",
            compression="gz",
            filter=default_filter,
        )

    def default_filter(record: "loguru.Record") -> bool:
        tags: list = record["extra"].get("tags", [])
        return "default" in tags or len(tags) == 0

    main()
