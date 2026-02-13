from pydantic import BaseModel
from typing import Optional, Any


class ExecutionStatus(BaseModel):
    status: str
    execution_id: int
    cached: bool = False
    data: Optional[Any] = None
    error: Optional[str] = None
