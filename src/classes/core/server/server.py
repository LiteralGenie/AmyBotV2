import json
from datetime import datetime, timezone
from sqlite3 import Connection
from typing import Optional

from classes.core.server import logger
from classes.core.server.middleware import ErrorLog, RequestLog, PerformanceLog
from classes.db import get_db
from fastapi import Depends, FastAPI, HTTPException
from utils.sql import WhereBuilder

server = FastAPI()

# Order matters, topmost are called first
server.add_middleware(ErrorLog)
server.add_middleware(PerformanceLog)
server.add_middleware(RequestLog)


@server.get("/super/search_equips")
def get_super_equips(
    name: Optional[str] = None,
    min_date: Optional[float] = None,
    max_date: Optional[float] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    seller: Optional[str] = None,
    seller_partial: Optional[str] = None,
    buyer: Optional[str] = None,
    buyer_partial: Optional[str] = None,
    complete: Optional[bool] = None,
    DB: Connection = Depends(get_db),
):
    where_builder = WhereBuilder("AND")

    # Create name filters
    #   eg "name=peer,waki" should match "Peerless * Wakizashi of the *"
    if name is not None:
        fragments = [x.strip() for x in name.split(",")]
        for fragment in fragments:
            where_builder.add("name LIKE ?", f"%{fragment}%")

    # Create date filters (utc)
    #   eg "min_date=1546300800" should match items sold on / after Jan 1, 2019
    if min_date is not None and max_date is not None and max_date < min_date:
        raise HTTPException(
            400, detail=f"min_date > max_date ({min_date} > {max_date})"
        )
    if min_date is not None:
        where_builder.add("sa.end_time >= ?", min_date)
    if max_date is not None:
        where_builder.add("sa.end_time <= ?", max_date)

    # Create price filters
    #   eg "max_price=1000" should match items sold for <=1000c
    if min_price is not None and max_price is not None and max_price < min_price:
        raise HTTPException(
            400, detail=f"min_price > max_price ({min_price} > {max_price})"
        )
    if min_price is not None:
        where_builder.add("se.price >= ?", min_price)
    if max_price is not None:
        wb = WhereBuilder("OR")
        wb.add("se.price <= ?", max_price)
        wb.add("se.price IS NULL", None)
        where_builder.add_builder(wb)

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

    # Create completion filter
    if complete is not None:
        where_builder.add("sa_is_complete = ?", int(complete))

    # Query DB
    with DB:
        where, data = where_builder.print()
        query = f"""
            SELECT se.*, sa.end_time as sa_end_time, sa.is_complete as sa_is_complete, sa.title as sa_title, sa.id as sa_id
            FROM super_equips as se INNER JOIN super_auctions as sa
            ON sa.id = se.id_auction
            {where}
            COLLATE NOCASE
            """
        logger.trace(f"Search super equips {query} {data}")
        rows = DB.execute(query, data).fetchall()

    # Massage data structure
    result = [dict(row) for row in rows]
    for r in result:
        # Move joined cols into dict
        r["auction"] = dict(
            id=r["sa_id"],
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


@server.get("/kedama/search_equips")
def get_kedama_equips(
    name: Optional[str] = None,
    min_date: Optional[float] = None,
    max_date: Optional[float] = None,
    min_price: Optional[int] = None,
    max_price: Optional[int] = None,
    seller: Optional[str] = None,
    seller_partial: Optional[str] = None,
    buyer: Optional[str] = None,
    buyer_partial: Optional[str] = None,
    DB: Connection = Depends(get_db),
):
    where_builder = WhereBuilder("AND")

    # Create name filters
    #   eg "name=peer,waki" should match "Peerless * Wakizashi of the *"
    if name is not None:
        fragments = [x.strip() for x in name.split(",")]
        for fragment in fragments:
            where_builder.add("name LIKE ?", f"%{fragment}%")

    # Create date filters (utc)
    #   eg "min_date=1546300800" should match items sold on / after Jan 1, 2019
    if min_date is not None and max_date is not None and max_date < min_date:
        raise HTTPException(
            400, detail=f"min_date > max_date ({min_date} > {max_date})"
        )
    if min_date is not None:
        where_builder.add("list.start_time >= ?", min_date)
    if max_date is not None:
        where_builder.add("list.start_time <= ?", max_date)

    # Create price filters
    #   eg "max_price=1000" should match items sold for <=1000c
    if min_price is not None and max_price is not None and max_price < min_price:
        raise HTTPException(
            400, detail=f"min_price > max_price ({min_price} > {max_price})"
        )
    if min_price is not None:
        where_builder.add("equip.price >= ?", min_price)
    if max_price is not None:
        wb = WhereBuilder("OR")
        wb.add("equip.price <= ?", max_price)
        wb.add("equip.price IS NULL", None)
        where_builder.add_builder(wb)

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
            SELECT 
                equip.*,
                list.start_time as list_start_time,
                list.title as list_title,
                list.title_short as list_title_short,
                list.id as list_id
            FROM kedama_equips as equip INNER JOIN kedama_auctions as list
            ON list.id = equip.id_auction
            {where}
            COLLATE NOCASE
            """
        logger.trace(f"Search kedama equips {query} {data}")
        rows = DB.execute(query, data).fetchall()

    # Massage data structure
    result = [dict(row) for row in rows]
    for r in result:
        # Move joined cols into dict
        r["auction"] = dict()
        for k in list(r.keys()):
            if k.startswith("list_"):
                r["auction"][k.replace("list_", "")] = r[k]
                del r[k]

        # Stats col contains json
        r["stats"] = json.loads(r["stats"])

    # Return
    return result


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "classes.core.server.server:server", host="0.0.0.0", port=4545, reload=True
    )
