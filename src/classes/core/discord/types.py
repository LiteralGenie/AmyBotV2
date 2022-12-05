from typing import Optional, TypedDict


class _Equip:
    class FetchParams(TypedDict, total=False):
        name: str
        min_date: float | None
        min_price: int | None
        max_price: int | None
        seller: str | None
        buyer: str | None

    class FormatOptions(TypedDict, total=False):
        show_link: bool
        show_buyer: bool
        show_seller: bool

    class CogAuction(TypedDict):
        time: float
        is_complete: bool
        title: str

    class CogEquip(TypedDict):
        name: str
        eid: int
        key: str
        is_isekai: bool
        level: int | None
        stats: list[str]
        price: int | None
        min_bid: int
        buyer: str | None
        seller: str
        auction: "_Equip.CogAuction"
