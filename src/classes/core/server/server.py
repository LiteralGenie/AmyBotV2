from fastapi import FastAPI

server = FastAPI()


@server.get("super/search")
def get_super_search():
    pass
