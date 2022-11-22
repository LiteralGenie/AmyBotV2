import functools
from pathlib import Path
from typing import Union

from .json_cache import JsonCache


def memoize(fp: Union[Path, str]):
    """
    File cache for the results of method calls.
    (Meant for use with instance / class methods, NOT static or standalone functions)

    Results are keyed by the stringified arguments
    """

    cache_file = JsonCache(fp, default=dict())

    def decorator(f):
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            hash = list(args[1:]) + sorted(kwargs.items(), key=lambda kv: kv[0])
            hash = str(hash)

            if not fp.parent.exists():
                fp.parent.mkdir(parents=True, exist_ok=True)

            data = cache_file.load()

            if hash not in data:
                result = f(*args, **kwargs)
                data[hash] = result
                cache_file.dump(data)

            return data[hash]

        return wrapper

    return decorator
