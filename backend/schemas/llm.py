from typing import Any
from pydantic import BaseModel


class LLMResponse(BaseModel):
    text: str
    provider: str
    model: str | None = None
    raw: Any | None = None
