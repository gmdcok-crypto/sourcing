from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.db import get_mysql_connection

router = APIRouter(prefix="/api/admin", tags=["admin-theme"])


class ThemeCategoryCreateRequest(BaseModel):
    cid: str = Field(..., min_length=1, max_length=20)
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True


class ThemeCategoryUpdateRequest(BaseModel):
    display_order: int = Field(default=0, ge=0)
    is_active: bool = True


@router.get("/themes")
async def list_themes() -> Dict[str, List[Dict[str, Any]]]:
    connection = get_mysql_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    t.id,
                    t.theme_code,
                    t.theme_name,
                    t.display_order,
                    t.is_active,
                    COUNT(tcm.id) AS category_count
                FROM themes t
                LEFT JOIN theme_category_maps tcm
                    ON t.id = tcm.theme_id
                GROUP BY
                    t.id,
                    t.theme_code,
                    t.theme_name,
                    t.display_order,
                    t.is_active
                ORDER BY t.display_order ASC, t.id ASC
                """
            )
            rows = cursor.fetchall()
        return {"items": rows}
    finally:
        connection.close()


@router.get("/themes/{theme_id}/categories")
async def list_theme_categories(theme_id: int) -> Dict[str, List[Dict[str, Any]]]:
    connection = get_mysql_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id, theme_name FROM themes WHERE id = %s", (theme_id,))
            theme = cursor.fetchone()
            if not theme:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Theme not found.",
                )

            cursor.execute(
                """
                SELECT
                    tcm.id,
                    nc.cid,
                    nc.category_name,
                    nc.full_path,
                    nc.depth,
                    nc.parent_cid,
                    tcm.display_order,
                    tcm.is_active
                FROM theme_category_maps tcm
                INNER JOIN naver_categories nc
                    ON tcm.category_id = nc.id
                WHERE tcm.theme_id = %s
                ORDER BY tcm.display_order ASC, tcm.id ASC
                """,
                (theme_id,),
            )
            rows = cursor.fetchall()

        return {"theme": theme, "items": rows}
    finally:
        connection.close()


@router.post("/themes/{theme_id}/categories")
async def create_theme_category(
    theme_id: int, payload: ThemeCategoryCreateRequest
) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT id FROM themes WHERE id = %s", (theme_id,))
            theme = cursor.fetchone()
            if not theme:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Theme not found.",
                )

            cursor.execute(
                "SELECT id FROM naver_categories WHERE cid = %s",
                (payload.cid,),
            )
            category = cursor.fetchone()
            if not category:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Category CID not found.",
                )

            cursor.execute(
                """
                INSERT INTO theme_category_maps (
                    theme_id,
                    category_id,
                    display_order,
                    is_active
                ) VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    display_order = VALUES(display_order),
                    is_active = VALUES(is_active),
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    theme_id,
                    category["id"],
                    payload.display_order,
                    int(payload.is_active),
                ),
            )
        connection.commit()
        return {"message": "Theme category mapping saved."}
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.put("/themes/{theme_id}/categories/{mapping_id}")
async def update_theme_category(
    theme_id: int, mapping_id: int, payload: ThemeCategoryUpdateRequest
) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE theme_category_maps
                SET display_order = %s,
                    is_active = %s,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND theme_id = %s
                """,
                (
                    payload.display_order,
                    int(payload.is_active),
                    mapping_id,
                    theme_id,
                ),
            )
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Theme category mapping not found.",
                )
        connection.commit()
        return {"message": "Theme category mapping updated."}
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


@router.delete("/themes/{theme_id}/categories/{mapping_id}")
async def delete_theme_category(theme_id: int, mapping_id: int) -> Dict[str, Any]:
    connection = get_mysql_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM theme_category_maps WHERE id = %s AND theme_id = %s",
                (mapping_id, theme_id),
            )
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Theme category mapping not found.",
                )
        connection.commit()
        return {"message": "Theme category mapping deleted."}
    except HTTPException:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
