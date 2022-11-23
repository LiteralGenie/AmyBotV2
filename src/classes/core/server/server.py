import json
from datetime import datetime, timezone
from sqlite3 import Connection
from typing import Optional

import uvicorn
from classes.core.server import logger
from classes.core.server.middleware import LogWare, PerformanceWare
from classes.db import init_db
from fastapi import Depends, FastAPI, HTTPException
from utils.sql import WhereBuilder

server = FastAPI()
server.add_middleware(PerformanceWare)
server.add_middleware(LogWare)


@server.get("/super/search_equips")
def get_search_equips(
    name: Optional[str] = None,
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    seller: Optional[str] = None,
    seller_partial: Optional[str] = None,
    buyer: Optional[str] = None,
    buyer_partial: Optional[str] = None,
    DB: Connection = Depends(init_db),
):
    where_builder = WhereBuilder("AND")

    # Create name filters
    #   eg "name=peer,waki" should match "Peerless * Wakizashi of the *"
    if name is not None:
        fragments = [x.strip() for x in name.split(",")]
        for fragment in fragments:
            where_builder.add("name LIKE ?", f"%{fragment}%")

    # Create year filters
    #   eg "min_year=2019" should match items sold >=2019
    if min_year is not None and max_year is not None and max_year < min_year:
        raise HTTPException(
            400, detail=f"min_year > max_year ({min_year} > {max_year})"
        )
    if min_year is not None:
        ts = datetime(min_year, 1, 1, tzinfo=timezone.utc).timestamp()
        where_builder.add("sa.end_time >= ?", ts)
    if max_year is not None:
        ts = datetime(max_year, 1, 1, tzinfo=timezone.utc).timestamp()
        where_builder.add("sa.end_time <= ?", ts)

    # Create price filters
    #   eg "max_price=1000" should match items sold for <=1000c
    if min_price is not None and max_price is not None and max_price < min_price:
        raise HTTPException(
            400, detail=f"min_price > max_price ({min_price} > {max_price})"
        )
    if min_price is not None:
        where_builder.add("se.price >= ?", min_price)
    if max_price is not None:
        where_builder.add("se.price <= ?", max_price)

    # Create buyer filters
    if buyer is not None:
        # Exact match
        where_builder.add("buyer = ?", buyer)
    elif buyer_partial is not None:
        # Partial match
        fragments = [x.strip() for x in buyer_partial.split(",")]
        for fragment in fragments:
            where_builder.add("buyer LIKE ?", f"%{fragment}%")

    # Create seller filters
    if seller is not None:
        # Exact match
        where_builder.add("seller = ?", seller)
    elif seller_partial is not None:
        # Partial match
        fragments = [x.strip() for x in seller_partial.split(",")]
        for fragment in fragments:
            where_builder.add("seller LIKE ?", f"%{fragment}%")

    # Query DB
    with DB:
        where, data = where_builder.print()
        query = f"""
            SELECT se.*, sa.end_time as sa_end_time, sa.is_complete as sa_is_complete, sa.title as sa_title
            FROM super_equips as se INNER JOIN super_auctions as sa
            ON sa.id = se.id_auction
            {where}
            COLLATE NOCASE
            """
        logger.trace(f"Search equips {query} {data}")
        rows = DB.execute(query, data).fetchall()

    # Massage data structure
    result = [dict(row) for row in rows]
    for r in result:
        # Move joined cols into dict
        r["auction"] = dict(
            end_time=r["sa_end_time"],
            is_complete=r["sa_is_complete"],
            title=r["sa_title"],
        )
        for k in list(r.keys()):
            if k.startswith("sa_"):
                del r[k]

        # Stats col contains json
        r["stats"] = json.loads(r["stats"])

    # Return
    return result


if __name__ == "__main__":
    uvicorn.run(
        "classes.core.server.server:server", host="0.0.0.0", port=4545, reload=True
    )
