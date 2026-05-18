from urllib.parse import urlparse

import pymysql
from pymysql.cursors import DictCursor

from app.core.config import get_settings


def parse_mysql_url(mysql_url: str) -> dict:
    parsed = urlparse(mysql_url)
    if parsed.scheme != "mysql":
        raise ValueError("MYSQL_URL must start with mysql://")

    return {
        "host": parsed.hostname,
        "port": parsed.port or 3306,
        "user": parsed.username,
        "password": parsed.password,
        "database": parsed.path.lstrip("/"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": False,
    }


def get_mysql_connection():
    settings = get_settings()
    if not settings.mysql_url:
        raise RuntimeError("MYSQL_URL is required.")

    return pymysql.connect(**parse_mysql_url(settings.mysql_url))
