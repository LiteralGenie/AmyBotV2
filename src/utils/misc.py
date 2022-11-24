def compose_1arg_fns(*fns):
    def compose(f1, f2):
        return lambda x: f1(f2(x))

    wrapped = lambda x: x
    for fn in fns:
        wrapped = compose(fn, wrapped)
    return wrapped
