import sqlite3

from config import paths


DB = sqlite3.connect(paths.DATA_DIR / "db.sqlite")


def create_tables():
    with DB:
        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS super_auctions (
                id                          TEXT,

                title                       TEXT    NOT NULL,
                end_time                    REAL    NOT NULL,
                last_scan_time              REAL,
                last_complete_scan_time     REAL,

                PRIMARY KEY (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS super_equips (
                id                  TEXT,
                id_auction          TEXT,

                name                TEXT        NOT NULL,
                eid                 INTEGER     NOT NULL,
                key                 TEXT        NOT NULL,
                level               INTEGER,
                stats               TEXT        NOT NULL,       --json

                current_bid         INTEGER,
                current_bid_link    TEXT,
                buyer               TEXT,
                next_bid            INTEGER,
                seller              TEXT        NOT NULL,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES super_auctions (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS super_items (
                id                  TEXT,
                id_auction          TEXT,

                name                TEXT        NOT NULL,
                quantity            INTEGER     NOT NULL,
                price               INTEGER     NOT NULL,
                unit_price          INTEGER     NOT NULL,

                current_bid         INTEGER,
                current_bid_link    TEXT,
                buyer               TEXT,
                next_bid            INTEGER,
                seller              TEXT        NOT NULL,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES super_auctions (id)
            ) STRICT;
            """
        )

        DB.execute(
            """
            CREATE TABLE IF NOT EXISTS super_fails (
                id              TEXT,
                id_auction      TEXT,
                                
                info            TEXT,

                PRIMARY KEY (id, id_auction),
                FOREIGN KEY (id_auction) REFERENCES super_auctions (id)
            ) STRICT;
            """
        )
