from typing import Any, Literal

from aiohttp import ClientSession
from bs4 import BeautifulSoup
from yarl import URL

from config import logger


async def fetch_page(
    url: str | URL,
    session: ClientSession | None = None,
    content_type: Literal["soup", "text", "json"] = "soup",
) -> Any:
    """Perform a GET

    Args:
        url:
        session: For accumulating cookies
        content_type: Whether to return a BeautifulSoup instance, str, or list / dict

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
            case "soup":
                result = await resp.text(encoding="utf-8")
                result = BeautifulSoup(result, "html.parser")
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
