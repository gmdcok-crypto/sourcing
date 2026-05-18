from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.db import get_mysql_connection

router = APIRouter(prefix="/api/admin", tags=["admin-theme"])


class ThemeCreateRequest(BaseModel):
    theme_code: str = Field(..., min_length=1, max_length=100)
    theme_name: str = Field(..., min_length=1, max_length=255)
    display_order: int = Field(default=0, ge=0)
    status_label: str = Field(default="핵심", min_length=1, max_length=50)


class ThemeUpdateRequest(ThemeCreateRequest):
    pass


class CategoryCreateRequest(BaseModel):
    cid: str = Field(..., min_length=1, max_length=20)
    category_name: str = Field(..., min_length=1, max_length=255)
    full_path: str = Field(..., min_length=1, max_length=1000)
    theme_id: Optional[int] = None
    status_label: str = Field(default="활성", min_length=1, max_length=50)


class CategoryUpdateRequest(CategoryCreateRequest):
    pass


def ensure_tables(connection) -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS themes (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                theme_code VARCHAR(100) NOT NULL,
                theme_name VARCHAR(255) NOT NULL,
                display_order INT UNSIGNED NOT NULL DEFAULT 0,
                status_label VARCHAR(50) NOT NULL DEFAULT '핵심',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uk_themes_theme_code (theme_code)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS naver_categories (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                cid VARCHAR(20) NOT NULL,
                category_name VARCHAR(255) NOT NULL,
                full_path VARCHAR(1000) NOT NULL,
                status_label VARCHAR(50) NOT NULL DEFAULT '활성',
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uk_naver_categories_cid (cid)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS theme_category_maps (
                id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
                theme_id BIGINT UNSIGNED NOT NULL,
                category_id BIGINT UNSIGNED NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                PRIMARY KEY (id),
                UNIQUE KEY uk_theme_category_maps_theme_category (theme_id, category_id),
                KEY idx_theme_category_maps_theme_id (theme_id),
                KEY idx_theme_category_maps_category_id (category_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
    connection.commit()


@router.get("/themes")
async def list_themes() -> Dict[str, List[Dict[str, Any]]]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    t.id,
                    t.theme_code,
                    t.theme_name,
                    t.display_order,
                    t.status_label,
                    COUNT(tcm.id) AS cid_count
                FROM themes t
                LEFT JOIN theme_category_maps tcm
                    ON t.id = tcm.theme_id
                GROUP BY t.id, t.theme_code, t.theme_name, t.display_order, t.status_label
                ORDER BY t.display_order ASC, t.id ASC
                """
            )
            rows = cursor.fetchall()
        return {"items": rows}
    finally:
        connection.close()


@router.post("/themes", status_code=status.HTTP_201_CREATED)
async def create_theme(payload: ThemeCreateRequest) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO themes (theme_code, theme_name, display_order, status_label)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    payload.theme_code,
                    payload.theme_name,
                    payload.display_order,
                    payload.status_label,
                ),
            )
        connection.commit()
        return {"message": "Theme created."}
    finally:
        connection.close()


@router.put("/themes/{theme_id}")
async def update_theme(theme_id: int, payload: ThemeUpdateRequest) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE themes
                SET theme_code = %s,
                    theme_name = %s,
                    display_order = %s,
                    status_label = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    payload.theme_code,
                    payload.theme_name,
                    payload.display_order,
                    payload.status_label,
                    theme_id,
                ),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Theme not found.")
        connection.commit()
        return {"message": "Theme updated."}
    finally:
        connection.close()


@router.delete("/themes/{theme_id}")
async def delete_theme(theme_id: int) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM theme_category_maps WHERE theme_id = %s", (theme_id,))
            cursor.execute("DELETE FROM themes WHERE id = %s", (theme_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Theme not found.")
        connection.commit()
        return {"message": "Theme deleted."}
    finally:
        connection.close()


@router.get("/categories")
async def list_categories() -> Dict[str, List[Dict[str, Any]]]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    nc.id,
                    nc.cid,
                    nc.category_name,
                    nc.full_path,
                    nc.status_label,
                    t.id AS theme_id,
                    t.theme_name
                FROM naver_categories nc
                LEFT JOIN theme_category_maps tcm
                    ON nc.id = tcm.category_id
                LEFT JOIN themes t
                    ON tcm.theme_id = t.id
                ORDER BY nc.id ASC
                """
            )
            rows = cursor.fetchall()
        return {"items": rows}
    finally:
        connection.close()


@router.post("/categories", status_code=status.HTTP_201_CREATED)
async def create_category(payload: CategoryCreateRequest) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO naver_categories (cid, category_name, full_path, status_label)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    payload.cid,
                    payload.category_name,
                    payload.full_path,
                    payload.status_label,
                ),
            )
            category_id = cursor.lastrowid

            if payload.theme_id:
                cursor.execute(
                    """
                    INSERT INTO theme_category_maps (theme_id, category_id)
                    VALUES (%s, %s)
                    """,
                    (payload.theme_id, category_id),
                )
        connection.commit()
        return {"message": "Category created."}
    finally:
        connection.close()


@router.put("/categories/{category_id}")
async def update_category(category_id: int, payload: CategoryUpdateRequest) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE naver_categories
                SET cid = %s,
                    category_name = %s,
                    full_path = %s,
                    status_label = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
                """,
                (
                    payload.cid,
                    payload.category_name,
                    payload.full_path,
                    payload.status_label,
                    category_id,
                ),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Category not found.")

            cursor.execute("DELETE FROM theme_category_maps WHERE category_id = %s", (category_id,))
            if payload.theme_id:
                cursor.execute(
                    """
                    INSERT INTO theme_category_maps (theme_id, category_id)
                    VALUES (%s, %s)
                    """,
                    (payload.theme_id, category_id),
                )
        connection.commit()
        return {"message": "Category updated."}
    finally:
        connection.close()


@router.delete("/categories/{category_id}")
async def delete_category(category_id: int) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        ensure_tables(connection)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM theme_category_maps WHERE category_id = %s", (category_id,))
            cursor.execute("DELETE FROM naver_categories WHERE id = %s", (category_id,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Category not found.")
        connection.commit()
        return {"message": "Category deleted."}
    finally:
        connection.close()
