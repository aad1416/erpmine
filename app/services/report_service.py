from datetime import datetime
from types import SimpleNamespace
from typing import Any

from fastapi import HTTPException, status

from app.config.setting import settings
from app.db.models.Users import User
from app.prompts.report import REPORT_SYSTEM_PROMPT, get_generate_report_prompt
from app.services.agent_service import AgentService


class ReportService:
    def __init__(self, agent_service: AgentService):
        self.agent_service = agent_service

    async def generate_report(
        self,
        narrative: str,
        info: dict[str, Any] | None,
        user: User,
    ) -> str:
        try:
            merged_info = {
                **(info or {}),
                "prepared_by": user.username,
                "date": datetime.now().strftime("%Y/%m/%d, %H:%M"),
            }
            prompt = get_generate_report_prompt(info=merged_info, narrative=narrative)
            persona = SimpleNamespace(
                prompt_text=REPORT_SYSTEM_PROMPT,
                model_name=settings.REPORT_MODEL,
            )
            return await self.agent_service.generate_async(
                prompt=prompt,
                persona=persona,
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error: {exc}",
            ) from exc
