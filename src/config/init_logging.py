from loguru import logger
from config import paths

logger.add(paths.LOG_DIR / "amy.log", rotation="10 MB", compression="gz")
