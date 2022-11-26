from typing import TypedDict

# @todo pydantic models


class SuperAuctionJoined(TypedDict):
    end_time: float
    is_complete: bool
    title: str


class SuperEquip(TypedDict):
    name: str
    eid: int
    key: str
    is_isekai: bool
    level: int | None
    stats: list[str]
    price: int | None
    next_bid: int
    buyer: str | None
    seller: str
    auction: SuperAuctionJoined
