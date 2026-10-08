import asyncio
import mimetypes
import re
import time
from pathlib import Path
from typing import Any, Optional

import httpx
import pandas as pd

from app.utils.parser_constants import LlamaParseConstants
from app.utils.table_parser import TableParser


class DocumentParser:
    """Document parser backed by the LlamaParse v2 API.

    Supported LlamaParse profiles:
    - ``agentic``: high-quality tier with cost optimizer enabled.
    - ``cost_efficient``: cost-effective tier with the same structure-preserving
      output options, without cost optimizer.

    The parser requests markdown, items, and spatial text, then returns markdown
    reconstructed from ``items`` so page transitions preserve active heading
    context for downstream chunking/RAG.
    """

    UPLOAD_URL = "https://api.cloud.llamaindex.ai/api/v1/files"
    PARSE_URL = "https://api.cloud.llamaindex.ai/api/v2/parse"
    POLL_INTERVAL_SECONDS = 2.0
    POLL_TIMEOUT_SECONDS = 900.0

    def __init__(
        self,
        llama_parse_api_key: Optional[str],
        result_type: str = LlamaParseConstants.RESULT_TYPE,
        language: str = "en",
        config_profile: str = "agentic",
        version: Optional[str] = "latest",
    ):
        self.llama_parse_api_key = llama_parse_api_key
        self.result_type = result_type
        self.language = (language or "en").strip() or "en"
        self.config_profile = self._normalize_config_profile(config_profile)
        self.tier = self._tier_for_profile(self.config_profile)
        self.version = version or "latest"

    def parse_file(self, file_path: str, file_type: str) -> str:
        normalized_type = (file_type or "").lower()
        if normalized_type in {"txt", "plain"}:
            return self._parse_plain_text(file_path)
        if normalized_type in {
            "png",
            "jpg",
            "jpeg",
            "tiff",
            "webp",
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "ppt",
            "pptx",
        }:
            return self._normalize_markdown(self._parse_with_llama(file_path))
        if normalized_type == "csv":
            return self._parse_csv(file_path)
        if normalized_type in {"md", "markdown"}:
            return self._normalize_markdown(self._read_text_file(file_path))
        raise ValueError(f"Unsupported file type: {file_type}")

    async def parse_file_async(self, file_path: str, file_type: str) -> str:
        normalized_type = (file_type or "").lower()
        if normalized_type in {"txt", "plain"}:
            return self._parse_plain_text(file_path)
        if normalized_type in {
            "png",
            "jpg",
            "jpeg",
            "tiff",
            "webp",
            "pdf",
            "doc",
            "docx",
            "xls",
            "xlsx",
            "ppt",
            "pptx",
        }:
            return self._normalize_markdown(await self._parse_with_llama_async(file_path))
        if normalized_type == "csv":
            return await asyncio.to_thread(self._parse_csv, file_path)
        if normalized_type in {"md", "markdown"}:
            return self._normalize_markdown(await asyncio.to_thread(self._read_text_file, file_path))
        raise ValueError(f"Unsupported file type: {file_type}")

    def _normalize_config_profile(self, config_profile: str | None) -> str:
        cleaned = (config_profile or "agentic").strip().lower().replace("-", "_")
        if cleaned == "cost_effective":
            cleaned = "cost_efficient"
        if cleaned not in {"agentic", "cost_efficient"}:
            raise ValueError("config_profile must be 'agentic' or 'cost_efficient'")
        return cleaned

    def _tier_for_profile(self, profile: str) -> str:
        if profile == "agentic":
            return "agentic"
        if profile == "cost_efficient":
            return "cost_effective"
        raise ValueError(f"Unsupported LlamaParse profile: {profile}")

    def _normalize_markdown(self, text: str) -> str:
        if "<table" in text.lower() and not LlamaParseConstants.OUTPUT_TABLES_AS_HTML:
            text = TableParser.convert_html_tables_in_text(text)
        return text.strip()

    def _parse_plain_text(self, file_path: str) -> str:
        text = self._read_text_file(file_path).replace("\r\n", "\n").replace("\r", "\n")
        paragraphs = []
        current: list[str] = []
        for line in text.split("\n"):
            stripped = line.strip()
            if self._is_structural(stripped):
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
                paragraphs.append(stripped)
            elif not stripped:
                if current:
                    paragraphs.append(" ".join(current))
                    current = []
            else:
                current.append(stripped)
        if current:
            paragraphs.append(" ".join(current))
        return "\n\n".join(paragraphs)

    def _is_structural(self, line: str) -> bool:
        if not line:
            return False
        if re.match(r"^[-*+]\s", line) or re.match(r"^\d+\.\s", line):
            return True
        if line.startswith("#") or line.startswith(">"):
            return True
        if line.startswith("```") or line.startswith("~~~"):
            return True
        return False

    def _parse_csv(self, file_path: str) -> str:
        dataframe = pd.read_csv(file_path, dtype=str, keep_default_na=False)
        return dataframe.to_markdown(index=False)

    def _parse_with_llama(self, file_path: str) -> str:
        if not self.llama_parse_api_key:
            raise ValueError("LLAMA_PARSE_API_KEY is not configured")

        with httpx.Client(timeout=300.0) as client:
            file_id = self._upload_file(client, file_path)
            job_id = self._start_parse_job(client, file_id)
            payload = self._poll_parse_job(client, job_id)

        return self._final_markdown_from_payload(payload)

    async def _parse_with_llama_async(self, file_path: str) -> str:
        if not self.llama_parse_api_key:
            raise ValueError("LLAMA_PARSE_API_KEY is not configured")

        async with httpx.AsyncClient(timeout=300.0) as client:
            file_id = await self._upload_file_async(client, file_path)
            job_id = await self._start_parse_job_async(client, file_id)
            payload = await self._poll_parse_job_async(client, job_id)

        return self._final_markdown_from_payload(payload)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.llama_parse_api_key}",
            "Accept": "application/json",
        }

    def _mime_type_for(self, path: Path) -> str:
        return mimetypes.guess_type(path.name)[0] or "application/octet-stream"

    def _upload_file(self, client: httpx.Client, file_path: str) -> str:
        path = Path(file_path)
        with path.open("rb") as handle:
            response = client.post(
                self.UPLOAD_URL,
                headers=self._headers(),
                files={"upload_file": (path.name, handle, self._mime_type_for(path))},
                timeout=httpx.Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0),
            )
        response.raise_for_status()
        return self._extract_file_id(response.json())

    async def _upload_file_async(self, client: httpx.AsyncClient, file_path: str) -> str:
        path = Path(file_path)
        file_bytes = await asyncio.to_thread(path.read_bytes)
        response = await client.post(
            self.UPLOAD_URL,
            headers=self._headers(),
            files={"upload_file": (path.name, file_bytes, self._mime_type_for(path))},
            timeout=httpx.Timeout(connect=30.0, read=600.0, write=600.0, pool=30.0),
        )
        response.raise_for_status()
        return self._extract_file_id(response.json())

    def _extract_file_id(self, payload: dict[str, Any]) -> str:
        file_id = payload.get("id")
        if not file_id:
            raise RuntimeError(f"Upload response missing file id: {payload}")
        return str(file_id)

    def _start_parse_job(self, client: httpx.Client, file_id: str) -> str:
        response = client.post(
            self.PARSE_URL,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=self._build_parse_request(file_id),
        )
        response.raise_for_status()
        return self._extract_job_id(response.json())

    async def _start_parse_job_async(self, client: httpx.AsyncClient, file_id: str) -> str:
        response = await client.post(
            self.PARSE_URL,
            headers={**self._headers(), "Content-Type": "application/json"},
            json=self._build_parse_request(file_id),
        )
        response.raise_for_status()
        return self._extract_job_id(response.json())

    def _extract_job_id(self, payload: dict[str, Any]) -> str:
        job_id = payload.get("id")
        if not job_id:
            raise RuntimeError(f"Parse create response missing job id: {payload}")
        return str(job_id)

    def _poll_parse_job(self, client: httpx.Client, job_id: str) -> dict[str, Any]:
        started = time.perf_counter()
        while True:
            try:
                response = client.get(
                    f"{self.PARSE_URL}/{job_id}",
                    headers=self._headers(),
                    params={"expand": LlamaParseConstants.EXPAND},
                )
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    pass  # Transient 5xx error from LlamaParse, let it retry
                else:
                    raise  # 4xx error (e.g. Unauthorized), fail immediately
            except httpx.RequestError:
                pass  # Network timeout or disconnect, let it retry
            else:
                status = self._job_status(payload)
                if status == "COMPLETED":
                    return payload
                if status in {"FAILED", "CANCELLED"}:
                    raise RuntimeError(
                        f"LlamaParse job {job_id} ended with status={status}: {payload}"
                    )
            
            if time.perf_counter() - started > self.POLL_TIMEOUT_SECONDS:
                raise TimeoutError(f"Timed out waiting for LlamaParse job {job_id}")
            time.sleep(self.POLL_INTERVAL_SECONDS)

    async def _poll_parse_job_async(
        self, client: httpx.AsyncClient, job_id: str
    ) -> dict[str, Any]:
        started = time.perf_counter()
        while True:
            try:
                response = await client.get(
                    f"{self.PARSE_URL}/{job_id}",
                    headers=self._headers(),
                    params={"expand": LlamaParseConstants.EXPAND},
                )
                response.raise_for_status()
                payload = response.json()
            except httpx.HTTPStatusError as e:
                if e.response.status_code >= 500:
                    pass  # Transient 5xx error from LlamaParse, let it retry
                else:
                    raise  # 4xx error (e.g. Unauthorized), fail immediately
            except httpx.RequestError:
                pass  # Network timeout or disconnect, let it retry
            else:
                status = self._job_status(payload)
                if status == "COMPLETED":
                    return payload
                if status in {"FAILED", "CANCELLED"}:
                    raise RuntimeError(
                        f"LlamaParse job {job_id} ended with status={status}: {payload}"
                    )
            
            if time.perf_counter() - started > self.POLL_TIMEOUT_SECONDS:
                raise TimeoutError(f"Timed out waiting for LlamaParse job {job_id}")
            await asyncio.sleep(self.POLL_INTERVAL_SECONDS)

    def _job_status(self, payload: dict[str, Any]) -> str:
        return str(
            payload.get("job", {}).get("status") or payload.get("status") or ""
        ).upper()

    def _build_parse_request(self, file_id: str) -> dict[str, Any]:
        return {
            "file_id": file_id,
            "tier": self.tier,
            "version": self.version,
            "processing_options": LlamaParseConstants.get_parse_processing_options(
                self.language,
                cost_optimizer=self.config_profile == "agentic",
            ),
            "output_options": LlamaParseConstants.get_parse_output_options(),
        }

    def _final_markdown_from_payload(self, payload: dict[str, Any]) -> str:
        reconstructed = self._reconstruct_markdown_from_items(payload)
        if reconstructed:
            return reconstructed
        return self._join_markdown_pages(payload)

    def _pages_from(self, payload: dict[str, Any], key: str) -> list[dict[str, Any]]:
        value = payload.get(key) or {}
        pages = value.get("pages") if isinstance(value, dict) else None
        return pages if isinstance(pages, list) else []

    def _join_markdown_pages(self, payload: dict[str, Any]) -> str:
        parts: list[str] = []
        for index, page in enumerate(self._pages_from(payload, "markdown"), start=1):
            page_number = int(page.get("page_number") or index)
            markdown = str(page.get("markdown") or page.get("md") or "").strip()
            if markdown:
                parts.append(f"<!-- PAGE:{page_number} -->\n\n{markdown}")
        return "\n\n".join(parts).strip()

    def _reconstruct_markdown_from_items(self, payload: dict[str, Any]) -> str:
        pages = self._pages_from(payload, "items")
        heading_stack: dict[int, str] = {}
        page_parts: list[str] = []

        for page_index, page in enumerate(pages):
            page_number = int(page.get("page_number") or page_index + 1)
            items = page.get("items")
            if not isinstance(items, list):
                items = []

            blocks = [f"<!-- PAGE:{page_number} -->"]
            context = self._context_comment(heading_stack)
            if page_index > 0 and context:
                blocks.append(context)

            for item in items:
                if not isinstance(item, dict):
                    continue
                markdown = self._item_markdown(item)
                if not markdown:
                    continue

                item_type = str(item.get("type") or "").lower()
                if item_type == "heading":
                    level, markdown = self._normalize_heading(item, markdown)
                    if level:
                        text = self._single_line(re.sub(r"^#{1,6}\s+", "", markdown))
                        heading_stack = {
                            key: value for key, value in heading_stack.items() if key < level
                        }
                        heading_stack[level] = text
                elif item_type == "header" and page_index == 0 and not heading_stack:
                    heading_stack[1] = self._single_line(
                        re.sub(r"^#{1,6}\s+", "", markdown)
                    )

                blocks.append(markdown)

            page_parts.append("\n\n".join(blocks).strip())

        return "\n\n".join(part for part in page_parts if part).strip()

    def _item_markdown(self, item: dict[str, Any]) -> str:
        for key in ("md", "markdown", "html", "value", "text"):
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        child_items = item.get("items")
        if isinstance(child_items, list):
            child_text = "\n\n".join(
                self._item_markdown(child)
                for child in child_items
                if isinstance(child, dict)
            )
            if child_text.strip():
                return child_text.strip()
        return ""

    def _normalize_heading(
        self, item: dict[str, Any], markdown: str
    ) -> tuple[int | None, str]:
        level = item.get("level")
        if isinstance(level, int) and 1 <= level <= 6:
            text = self._single_line(re.sub(r"^#{1,6}\s+", "", markdown.strip()))
            return level, f"{'#' * level} {text}" if text else markdown

        markdown_level = self._heading_level_from_markdown(markdown)
        if markdown_level:
            text = self._single_line(re.sub(r"^#{1,6}\s+", "", markdown.strip()))
            return markdown_level, f"{'#' * markdown_level} {text}" if text else markdown
        return None, markdown

    def _heading_level_from_markdown(self, markdown: str) -> int | None:
        match = re.match(r"^(#{1,6})\s+", markdown.strip())
        return len(match.group(1)) if match else None

    def _context_comment(self, heading_stack: dict[int, str]) -> str:
        if not heading_stack:
            return ""
        parts = [self._single_line(heading_stack[level]) for level in sorted(heading_stack)]
        return "<!-- CONTINUED_CONTEXT: " + " > ".join(parts) + " -->"

    def _single_line(self, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    def _read_text_file(self, file_path: str) -> str:
        path = Path(file_path)
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="latin-1")
