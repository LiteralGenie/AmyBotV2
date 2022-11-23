from fastapi import FastAPI
import uvicorn

from classes.core.server.middleware import LogWare
from classes.core.server import logger
from classes.db import DB

server = FastAPI()
server.add_middleware(LogWare)


@server.get("/super/search")
def get_super_search():
    return "pong"


if __name__ == "__main__":
    uvicorn.run(
        "classes.core.server.server:server", host="0.0.0.0", port=4545, reload=True
    )
