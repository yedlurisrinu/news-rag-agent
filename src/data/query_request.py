from pydantic import BaseModel

class QueryRequest(BaseModel):
    query: str  # Field(..., min_length=1, description="Natural language news query")
