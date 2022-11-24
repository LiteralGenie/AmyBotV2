from typing import TypedDict

# @todo pydantic models


class SuperAuctionJoined(TypedDict):
    end_time: float
    is_complete: bool
    title: str


class SuperEquip(TypedDict):
    name: str
    eid: int
    key: int
    is_isekai: bool
    level: int | None
    stats: dict[str, str]
    price: int | None
    buyer: str | None
    seller: str
    auction: SuperAuctionJoined
