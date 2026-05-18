from typing import List, Optional, Union

from pydantic import BaseModel, Field, HttpUrl


class KeywordSearchParams(BaseModel):
    query: str = Field(..., min_length=1, description="Keyword to search on Naver Shopping")
    display: int = Field(default=10, ge=1, le=100, description="Number of items")
    start: int = Field(default=1, ge=1, le=1000, description="Pagination start index")
    sort: str = Field(
        default="sim",
        pattern="^(sim|date|asc|dsc)$",
        description="Naver sort mode",
    )


class ProductItem(BaseModel):
    title: str
    link: Union[HttpUrl, str]
    image: Optional[Union[HttpUrl, str]] = None
    lprice: Optional[str] = None
    mall_name: Optional[str] = None
    product_id: Optional[str] = None
    product_type: Optional[str] = None
    brand: Optional[str] = None
    maker: Optional[str] = None
    category1: Optional[str] = None
    category2: Optional[str] = None
    category3: Optional[str] = None
    category4: Optional[str] = None


class KeywordSearchResponse(BaseModel):
    query: str
    total: int
    start: int
    display: int
    items: List[ProductItem]
    saved_to_r2: bool = False
    r2_key: Optional[str] = None
