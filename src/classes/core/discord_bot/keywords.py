import re
from datetime import datetime, timezone
from functools import partial
from typing import Any, Callable, Optional

from utils.parse import price_to_int


class Keyword:
    """Helper class for parsing commands

    Given a command like "!equip legendary staff min500k"
    A Keyword subclass might be used to convert "min500k" to ("min", 500_000)
    """

    def __init__(self, key: str, converter: Optional[Callable[[str], Any]] = None):
        super().__init__()
        self.key = key
        self._converter = converter or self._default_converter

    def parse(self, text: str) -> tuple[str, Any | None]:
        """Extract keyword + value from string

        Args:
            text:

        Returns:
            (cleaned_string, keyword_value)
        """
        raw = self.extract(text)
        if raw is None:
            return (text, None)
        else:
            val = self.convert(raw)
            rem = self.purge(text)
            return (rem, val)

    def extract(self, text: str) -> str | None:
        m = re.search(rf"\b{self.key}([^\s]*)", text, flags=re.IGNORECASE)
        return m.group(1) if m else None

    def convert(self, text: str | None):
        return self._converter(text) if text else None

    def purge(self, text: str) -> str:
        result = re.sub(rf"\b{self.key}[^\s]* ?", "", text, flags=re.IGNORECASE)
        return result

    def _default_converter(self, text: str) -> Any:
        return text


_StringKey = partial(Keyword, converter=lambda x: str(x).strip())
_IntKey = partial(Keyword, converter=int)
_FloatKey = partial(Keyword, converter=float)


class _YearKey(Keyword):
    def __init__(self):
        super().__init__("year")

    def _default_converter(self, text: str) -> float:
        yr = int(text)
        if yr < 100:
            yr += 2000

        ts = datetime(yr, 1, 1, tzinfo=timezone.utc).timestamp()
        return ts


class _PriceKey(Keyword):
    """Converts 50k to 50_000"""

    def __init__(self, key: str):
        super().__init__(key)

    def _default_converter(self, text: str) -> int:
        val = price_to_int(text)
        return val


### vvv Concretes vvv

NameKey = Keyword("name", converter=lambda x: re.sub(r"\s+", ",", x.strip()))
YearKey = _YearKey()
LinkKey = Keyword("link", converter=lambda _: True)
MinPriceKey = _PriceKey("min")
MaxPriceKey = _PriceKey("max")
SellerKey = _StringKey("seller")
BuyerKey = _StringKey("buyer")
