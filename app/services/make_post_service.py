from types import SimpleNamespace
from typing import Union

from fastapi import HTTPException, UploadFile, status

from app.config.setting import settings
from app.prompts.make_post import MAKE_POST_SYSTEM_PROMPT, get_generate_post_prompt
from app.services.agent_service import AgentService
from app.utils.document_parser import DocumentParser
from app.utils.fast_document_parser import FastDocumentParser
from app.utils.file_to_text import convert_upload_to_text


class MakePostService:
    def __init__(
        self,
        agent_service: AgentService,
        parser: Union[DocumentParser, FastDocumentParser],
    ):
        self.agent_service = agent_service
        self.parser = parser

    async def make_post(self, document: UploadFile, current_post: str) -> str:
        try:
            new_text = await convert_upload_to_text(document, self.parser)
            prompt = get_generate_post_prompt(
                current_post=current_post or "",
                new_text=new_text,
            )
            persona = SimpleNamespace(
                prompt_text=MAKE_POST_SYSTEM_PROMPT,
                model_name=settings.MAKE_POST_MODEL,
            )
            html = await self.agent_service.generate_async(
                prompt=prompt,
                persona=persona,
            )
            return self._strip_html_fences(html)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error: {exc}",
            ) from exc

    @staticmethod
    def _strip_html_fences(html: str) -> str:
        cleaned = html.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned
