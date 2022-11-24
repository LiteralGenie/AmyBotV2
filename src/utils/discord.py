import re
from typing import Optional


def alias_by_prefix(
    text: str,
    starting_at: int = 2,
    include_full=False,
    exclude: Optional[list[str]] = None,
) -> list[str]:
    """eg "equip" -> ["eq", "equ", "equi"]

    Args:
        text:
        starting_at: Defaults to 2.
        include_full: Defaults to False.
        except_: Defaults to None.
    """
    aliases = []
    end = starting_at
    while end < len(text):
        aliases.append(text[:end])
        end += 1

    if include_full:
        aliases.append(text)

    if exclude:
        for x in exclude or []:
            aliases.remove(x)

    return aliases


def extract_quoted(
    text: str, tokens: Optional[list[str]] = None
) -> tuple[str, list[tuple[str | None, str]]]:
    """Extracts quoted substrings

    For example...
        the 'lazy dog' jumped over the"brown bear"
    becomes...
        [
            "the  jumped over",
            [
                ("lazy dog", ""),
                ("brown bear", the)
            ]
        ]
    """

    tokens = tokens or ['"', "'"]

    def main():
        rem = text
        substrings: list[tuple[str | None, str]] = []

        while True:
            start = find_next_token(rem)
            end = find_next_token(rem, start + 1)

            if end == -1:
                rem = purge_tokens(rem)
                break
            else:
                sub = rem[start + 1 : end]  # does not include quote-tokens
                prefix = get_prefix(rem, start)
                substrings.append((prefix, sub))
                rem = rem[0 : start - len(prefix or "")] + rem[end + 1 :]

        return (rem, substrings)

    def find_next_token(text: str, start=0) -> int:
        for t in tokens:
            idx = text.find(t, start)
            if idx != -1:
                return idx
        else:
            return -1

    def purge_tokens(text: str) -> str:
        for t in tokens:
            text = text.replace(t, "")
        return text

    def get_prefix(text: str, prefix_end: int) -> str | None:
        idx = prefix_end
        prefix = ""
        while idx > 0:
            idx -= 1
            char = text[idx]

            if char.strip():
                prefix = char + prefix
            else:
                break
        return prefix if prefix else None

    return main()
