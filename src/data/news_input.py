from pydantic import BaseModel

class NewsInput(BaseModel):
    query: str
