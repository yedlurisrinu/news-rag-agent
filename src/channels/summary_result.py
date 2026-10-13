from typing import TypedDict, Required

class SummaryResult(TypedDict):
    summary: Required[str]
    duration_seconds: Required[dict[str, int]]  # Time this agent took
