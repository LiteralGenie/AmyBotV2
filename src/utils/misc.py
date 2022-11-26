from pathlib import Path

import tomlkit


def compose_1arg_fns(*fns):
    def compose(f1, f2):
        return lambda x: f1(f2(x))

    wrapped = lambda x: x
    for fn in fns:
        wrapped = compose(fn, wrapped)
    return wrapped


def load_toml(fp: Path | str):
    if isinstance(fp, str):
        fp = Path(fp)
    return tomlkit.parse(fp.read_text(encoding="utf-8"))


def dump_toml(data: tomlkit.TOMLDocument, fp: Path | str) -> None:
    if isinstance(fp, str):
        fp = Path(fp)

    with open(fp, "w") as file:
        tomlkit.dump(data, file)
