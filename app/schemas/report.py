from typing import Any

from pydantic import BaseModel


class ReportRequest(BaseModel):
    narrative: str
    info: dict[str, Any] | None = None


class ReportResponse(BaseModel):
    detail: str
