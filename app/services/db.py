import os
import re
from typing import Dict

import pymysql


def parse_mysql_url(mysql_url: str) -> Dict[str, object]:
    pattern = re.compile(
        r"^mysql:\/\/(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:\/]+):(?P<port>\d+)\/(?P<database>[^?]+)"
    )
    match = pattern.match(mysql_url)
    if not match:
        raise ValueError(
            "MYSQL_URL format is invalid. Expected mysql://user:password@host:port/database"
        )

    values = match.groupdict()
    return {
        "host": values["host"],
        "user": values["user"],
        "password": values["password"],
        "database": values["database"],
        "port": int(values["port"]),
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
        "autocommit": False,
    }


def get_mysql_connection():
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        raise RuntimeError("MYSQL_URL is required.")

    return pymysql.connect(**parse_mysql_url(mysql_url))
