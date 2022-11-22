from operator import is_
import re


def price_to_int(x: str) -> int:
    # Strip commas and spaces
    text = str(x).replace(",", "").strip()

    # Check format (digits followed by optional suffix)
    m = re.search(r"^\d+[mkc]?$", text)
    if m is None:
        raise Exception

    # Parse suffix
    mult = 1
    if text[-1] == "c":
        text = text[:-1]
    elif text[-1] == "k":
        mult = 10**3
        text = text[:-1]
    elif text[-1] == "m":
        mult = 10**6
        text = text[:-1]

    # Parse base
    val = int(text)
    if int(text) != float(text):
        raise Exception

    # Apply mult
    val = mult * val

    # Return
    return val


def parse_equip_link(text: str) -> tuple[int, str, bool] | None:
    # http://hentaiverse.org/equip/123487856/579b582136
    patt = r".*hentaiverse\.org/(isekai/)?equip/(\d+)/([A-Za-z\d]{10})"
    if m := re.search(patt, text, flags=re.IGNORECASE):
        [is_isekai, eid, key] = m.groups()
        return (int(eid), key, bool(is_isekai))

    # legacy format -- http://hentaiverse.org/pages/showequip.php?eid=123487856&key=579b582136
    eid = re.search(r"eid=(\d+)", text)
    key = re.search(r"key=([A-Za-z\d]{10})", text)
    is_isekai = "/isekai/" in text
    if eid and key:
        return (int(eid.group(1)), key.group(1), is_isekai)

    return None
