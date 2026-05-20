from pydantic import BaseModel
from typing import List

class HistoryItem(BaseModel):
    prompt: str
    response_time_ms: int

class DashboardResponse(BaseModel):
    total_generations: int
    history: List[HistoryItem]
