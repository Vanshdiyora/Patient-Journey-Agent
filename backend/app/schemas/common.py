from typing import Any
from pydantic import BaseModel, Field
class MessageResponse(BaseModel): message: str
class PaginationResponse(BaseModel): items: list[Any]; total: int; limit: int; offset: int
