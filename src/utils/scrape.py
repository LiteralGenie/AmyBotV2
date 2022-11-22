from typing import Any, Literal

from aiohttp import ClientSession
from yarl import URL

from loguru import logger


async def fetch_page(
    url: str | URL,
    session: ClientSession | None = None,
    content_type: Literal["text", "json"] = "text",
) -> Any:
    """Perform a GET

    Args:
        url:
        session: For accumulating cookies
        content_type: Whether to return a str ('text') or a dict / list ('json')

    Raises:
        Exception:
        ValueError:
    """
    session = session or create_session()

    async with session:
        logger.info(f"Fetching {url}")
        resp = await session.get(url)
        if resp.status != 200:
            raise Exception

        match content_type:
            case "text":
                result = await resp.text(encoding="utf-8")
            case "json":
                result = await resp.json(encoding="utf-8")
            case default:
                raise ValueError

        return result


def create_session():
    session = ClientSession(
        headers={
            # https://github.com/aio-libs/aiohttp/issues/3904#issuecomment-632661245
            "Connection": "keep-alive"
        }
    )
    return session
