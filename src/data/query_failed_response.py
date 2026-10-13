from typing import Literal

from pydantic import BaseModel

class QueryFailedResponse(BaseModel):
    query: str
    error: str
    error_code: int
    status: Literal["failed"] = "failed"
