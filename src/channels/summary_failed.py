from typing import TypedDict, Required

class SummaryFailed(TypedDict):
    query: Required[str]
    error: Exception
    error_code: str
