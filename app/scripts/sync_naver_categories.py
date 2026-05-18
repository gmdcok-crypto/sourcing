import os
import re
from pathlib import Path
from typing import Dict, List, Tuple

import pymysql


CATEGORY_ROW_RE = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|$")
THEME_HEADER_RE = re.compile(r"^##\s+(.+?)\s+\((\d+)개\)$")


def slugify_theme_name(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^\w가-힣\s-]", "", value)
    value = re.sub(r"[\s-]+", "_", value)
    return value


def parse_category_map(markdown_text: str) -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    categories: Dict[str, Dict[str, object]] = {}
    themes: List[Dict[str, object]] = []
    mappings: List[Dict[str, object]] = []
    current_theme = None

    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()

        theme_match = THEME_HEADER_RE.match(line)
        if theme_match:
            theme_name, _ = theme_match.groups()
            current_theme = {
                "theme_name": theme_name.strip(),
                "theme_code": slugify_theme_name(theme_name),
                "display_order": len(themes) + 1,
                "is_active": 1,
            }
            themes.append(current_theme)
            continue

        match = CATEGORY_ROW_RE.match(line)
        if not match:
            continue

        cid, full_path = match.groups()
        parts = [part.strip() for part in full_path.split(">")]
        category_name = parts[-1]
        depth = len(parts)
        parent_cid = None

        if cid not in categories:
            categories[cid] = {
                "cid": cid,
                "category_name": category_name,
                "full_path": " > ".join(parts),
                "depth": depth,
                "parent_cid": parent_cid,
                "is_active": 1,
            }

        if current_theme:
            mappings.append(
                {
                    "theme_code": current_theme["theme_code"],
                    "cid": cid,
                    "display_order": len([m for m in mappings if m["theme_code"] == current_theme["theme_code"]]) + 1,
                    "is_active": 1,
                }
            )

    return themes, list(categories.values()), mappings


def parse_mysql_url(mysql_url: str) -> Dict[str, object]:
    pattern = re.compile(
        r"^mysql:\/\/(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:\/]+):(?P<port>\d+)\/(?P<database>[^?]+)"
    )
    match = pattern.match(mysql_url)
    if not match:
        raise ValueError("MYSQL_URL format is invalid. Expected mysql://user:password@host:port/database")

    values = match.groupdict()
    return {
        "host": values["host"],
        "user": values["user"],
        "password": values["password"],
        "database": values["database"],
        "port": int(values["port"]),
        "charset": "utf8mb4",
        "autocommit": False,
    }


def ensure_table_exists(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS `naver_categories` (
                `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                `cid` VARCHAR(20) NOT NULL,
                `category_name` VARCHAR(255) NOT NULL,
                `full_path` VARCHAR(1000) NOT NULL,
                `depth` TINYINT UNSIGNED NOT NULL,
                `parent_cid` VARCHAR(20) DEFAULT NULL,
                `is_active` TINYINT(1) NOT NULL DEFAULT 1,
                `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_naver_categories_cid` (`cid`),
                KEY `idx_naver_categories_parent_cid` (`parent_cid`),
                KEY `idx_naver_categories_is_active` (`is_active`)
            ) ENGINE=InnoDB
              DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS `themes` (
                `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                `theme_code` VARCHAR(100) NOT NULL,
                `theme_name` VARCHAR(255) NOT NULL,
                `display_order` INT UNSIGNED NOT NULL DEFAULT 0,
                `is_active` TINYINT(1) NOT NULL DEFAULT 1,
                `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_themes_theme_code` (`theme_code`),
                UNIQUE KEY `uk_themes_theme_name` (`theme_name`),
                KEY `idx_themes_is_active` (`is_active`)
            ) ENGINE=InnoDB
              DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci;
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS `theme_category_maps` (
                `id` BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                `theme_id` BIGINT UNSIGNED NOT NULL,
                `category_id` BIGINT UNSIGNED NOT NULL,
                `display_order` INT UNSIGNED NOT NULL DEFAULT 0,
                `is_active` TINYINT(1) NOT NULL DEFAULT 1,
                `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                `updated_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (`id`),
                UNIQUE KEY `uk_theme_category_maps_theme_category` (`theme_id`, `category_id`),
                KEY `idx_theme_category_maps_theme_id` (`theme_id`),
                KEY `idx_theme_category_maps_category_id` (`category_id`),
                CONSTRAINT `fk_theme_category_maps_theme`
                    FOREIGN KEY (`theme_id`) REFERENCES `themes` (`id`),
                CONSTRAINT `fk_theme_category_maps_category`
                    FOREIGN KEY (`category_id`) REFERENCES `naver_categories` (`id`)
            ) ENGINE=InnoDB
              DEFAULT CHARSET=utf8mb4
              COLLATE=utf8mb4_unicode_ci;
            """
        )


def upsert_categories(connection, categories: List[Dict[str, object]]) -> Tuple[int, int]:
    inserted_or_updated = 0

    sql = """
    INSERT INTO `naver_categories` (
        `cid`,
        `category_name`,
        `full_path`,
        `depth`,
        `parent_cid`,
        `is_active`
    ) VALUES (%s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        `category_name` = VALUES(`category_name`),
        `full_path` = VALUES(`full_path`),
        `depth` = VALUES(`depth`),
        `parent_cid` = VALUES(`parent_cid`),
        `is_active` = VALUES(`is_active`),
        `updated_at` = CURRENT_TIMESTAMP
    """

    with connection.cursor() as cursor:
        for category in categories:
            cursor.execute(
                sql,
                (
                    category["cid"],
                    category["category_name"],
                    category["full_path"],
                    category["depth"],
                    category["parent_cid"],
                    category["is_active"],
                ),
            )
            inserted_or_updated += 1

    return inserted_or_updated, len(categories)


def upsert_themes(connection, themes: List[Dict[str, object]]) -> Tuple[int, int]:
    affected = 0
    sql = """
    INSERT INTO `themes` (
        `theme_code`,
        `theme_name`,
        `display_order`,
        `is_active`
    ) VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        `theme_name` = VALUES(`theme_name`),
        `display_order` = VALUES(`display_order`),
        `is_active` = VALUES(`is_active`),
        `updated_at` = CURRENT_TIMESTAMP
    """

    with connection.cursor() as cursor:
        for theme in themes:
            cursor.execute(
                sql,
                (
                    theme["theme_code"],
                    theme["theme_name"],
                    theme["display_order"],
                    theme["is_active"],
                ),
            )
            affected += 1

    return affected, len(themes)


def fetch_theme_ids(connection) -> Dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT `id`, `theme_code` FROM `themes`")
        rows = cursor.fetchall()
    return {row[1]: row[0] for row in rows}


def fetch_category_ids(connection) -> Dict[str, int]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT `id`, `cid` FROM `naver_categories`")
        rows = cursor.fetchall()
    return {row[1]: row[0] for row in rows}


def upsert_theme_category_maps(connection, mappings: List[Dict[str, object]]) -> Tuple[int, int]:
    theme_ids = fetch_theme_ids(connection)
    category_ids = fetch_category_ids(connection)
    affected = 0

    sql = """
    INSERT INTO `theme_category_maps` (
        `theme_id`,
        `category_id`,
        `display_order`,
        `is_active`
    ) VALUES (%s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
        `display_order` = VALUES(`display_order`),
        `is_active` = VALUES(`is_active`),
        `updated_at` = CURRENT_TIMESTAMP
    """

    with connection.cursor() as cursor:
        for mapping in mappings:
            theme_id = theme_ids.get(mapping["theme_code"])
            category_id = category_ids.get(mapping["cid"])
            if not theme_id or not category_id:
                continue

            cursor.execute(
                sql,
                (
                    theme_id,
                    category_id,
                    mapping["display_order"],
                    mapping["is_active"],
                ),
            )
            affected += 1

    return affected, len(mappings)


def main() -> None:
    mysql_url = os.getenv("MYSQL_URL")
    if not mysql_url:
        raise RuntimeError("MYSQL_URL is required.")

    project_root = Path(__file__).resolve().parents[2]
    category_map_path = project_root / "CATEGORY_MAP.md"
    if not category_map_path.exists():
        raise FileNotFoundError(f"Missing category map file: {category_map_path}")

    markdown_text = category_map_path.read_text(encoding="utf-8")
    themes, categories, mappings = parse_category_map(markdown_text)
    if not themes or not categories or not mappings:
        raise RuntimeError("No category rows were parsed from CATEGORY_MAP.md")

    connection = pymysql.connect(**parse_mysql_url(mysql_url))
    try:
        ensure_table_exists(connection)
        theme_rows, total_themes = upsert_themes(connection, themes)
        category_rows, total_categories = upsert_categories(connection, categories)
        mapping_rows, total_mappings = upsert_theme_category_maps(connection, mappings)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(
        f"Synced themes={theme_rows}/{total_themes}, "
        f"categories={category_rows}/{total_categories}, "
        f"mappings={mapping_rows}/{total_mappings}"
    )


if __name__ == "__main__":
    main()
