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
