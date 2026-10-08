from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
from typing import Annotated, Any, Dict, List, Literal, Optional, Union


# ---------------------------------------------------------------------------
# Chart spec (map decision D9). Copied verbatim from the chart-spec prototype
# (prototypes/chart_spec/chart_spec_proto.py); reviewed against all five
# chart-bearing client examples.
# ---------------------------------------------------------------------------

MAX_CATEGORIES = 60  # x values; wider results become a Table / Export
MAX_SERIES = 6

ChartType = Literal["bar", "line", "pie"]
ValueFormat = Literal["number", "integer", "currency", "percent"]
Axis = Literal["primary", "secondary"]


class ChartAxis(BaseModel):
    label: Optional[str] = None
    values: List[str] = Field(..., min_length=1, max_length=MAX_CATEGORIES)


class ChartSeries(BaseModel):
    name: str
    values: List[Optional[float]] = Field(..., min_length=1)
    format: ValueFormat = "number"
    unit: Optional[str] = None
    axis: Axis = "primary"


class ChartSpec(BaseModel):
    type: ChartType
    title: str = Field(..., min_length=1, max_length=120)
    x: ChartAxis
    series: List[ChartSeries] = Field(..., min_length=1, max_length=MAX_SERIES)
    y_label: Optional[str] = None
    y2_label: Optional[str] = None
    stacked: bool = False
    horizontal: bool = False
    note: Optional[str] = Field(None, max_length=300)

    @model_validator(mode="after")
    def _check_shape(self) -> "ChartSpec":
        n = len(self.x.values)
        for s in self.series:
            if len(s.values) != n:
                raise ValueError(
                    f"series '{s.name}' has {len(s.values)} values but x has {n} categories"
                )
        secondary = [s for s in self.series if s.axis == "secondary"]
        if self.type == "pie":
            if len(self.series) != 1:
                raise ValueError("pie charts take exactly one series")
            if any(v is not None and v < 0 for v in self.series[0].values):
                raise ValueError("pie slices cannot be negative")
            if secondary:
                raise ValueError("pie charts have no secondary axis")
            if self.stacked or self.horizontal:
                raise ValueError("stacked/horizontal apply to bar charts only")
        if self.type == "line" and (self.stacked or self.horizontal):
            raise ValueError("stacked/horizontal apply to bar charts only")
        if secondary and len(secondary) == len(self.series):
            raise ValueError("at least one series must be on the primary axis")
        if self.stacked and secondary:
            raise ValueError("stacked bars cannot mix axes")
        if self.y2_label and not secondary:
            raise ValueError("y2_label given but no series uses the secondary axis")
        return self


# ---------------------------------------------------------------------------
# Message attachments (map decision D5). Item envelope + provenance shape from
# ticket 03's resolution, with the `transforms: list[TransformStep]` erratum
# from ticket 04 (chained transforms don't fit a single transform/params pair).
# ---------------------------------------------------------------------------

class TransformStep(BaseModel):
    transform: str
    params: Dict[str, Any]


class OutputProvenance(BaseModel):
    sql: str  # root, post-guard SQL (store filter already injected)
    transforms: List[TransformStep] = Field(default_factory=list)  # [] for raw SQL
    row_count: int  # full result size before any inline cap
    generated_at: datetime


class ChartAttachment(BaseModel):
    kind: Literal["chart"]
    title: str = Field(..., max_length=120)
    spec: ChartSpec
    provenance: OutputProvenance


class TableColumn(BaseModel):
    key: str
    label: str
    type: Literal["string", "number", "currency", "date", "percent"]


class TableAttachment(BaseModel):
    kind: Literal["table"]
    title: str = Field(..., max_length=120)
    columns: List[TableColumn]
    rows: List[List[Any]] = Field(default_factory=list, max_length=30)
    row_count: int  # full result size
    truncated: bool  # row_count > len(rows)
    provenance: OutputProvenance


class FileAttachment(BaseModel):
    kind: Literal["file"]
    title: str = Field(..., max_length=120)
    file_id: str  # files.id (FK by convention, no DB constraint)
    filename: str  # denormalised from files.file_name
    mime_type: str
    size: int
    provenance: OutputProvenance


Attachment = Annotated[
    Union[ChartAttachment, TableAttachment, FileAttachment], Field(discriminator="kind")
]


# Message Schemas
class MessageBase(BaseModel):
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="Message content")


class MessageCreate(BaseModel):
    content: str = Field(..., min_length=1, description="Message content")


class MessageResponse(MessageBase):
    id: int
    chat_id: int
    created_at: datetime
    updated_at: datetime
    attachments: List[Attachment] = Field(
        default_factory=list, description="Outputs (chart/table/file); [] when none"
    )

    @field_validator("attachments", mode="before")
    @classmethod
    def _null_attachments_to_empty_list(cls, value: Any) -> Any:
        return value or []

    class Config:
        from_attributes = True


# Chat Schemas
class ChatBase(BaseModel):
    title: str = Field(..., min_length=1, max_length=200, description="Chat title")


class ChatCreate(ChatBase):
    pass


class ChatUpdate(BaseModel):
    title: Optional[str] = Field(
        None, min_length=1, max_length=200, description="New chat title"
    )


class ChatResponse(ChatBase):
    id: int
    user_id: str
    feature_id: int
    created_at: datetime
    updated_at: datetime
    message_count: Optional[int] = Field(None, description="Number of messages in chat")

    class Config:
        from_attributes = True


class ChatWithMessages(ChatResponse):
    messages: List[MessageResponse] = Field(
        default_factory=list, description="Chat messages"
    )


# Chat Message Sending/Response
class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="User message to send")
    use_rag: bool = Field(
        default=True,
        description="Whether the document retrieval tool is available (OpenAI Agents path) or eager RAG runs (legacy path)",
    )
    use_db: bool = Field(
        default=True,
        description="Whether the database query tool may run (OpenAI Agents path only; requires DB_RAG_ENABLED and Lyndom DB)",
    )
    rag_top_k: int = Field(
        default=5, ge=1, le=20, description="Number of documents to retrieve"
    )


class MessageSource(BaseModel):
    document_id: Optional[str] = None
    filename: Optional[str] = None
    file_type: Optional[str] = None
    chunk_type: Optional[str] = None
    chunk_index: Optional[int] = None
    table_id: Optional[str] = None
    row_start: Optional[int] = None
    row_end: Optional[int] = None
    section_path: Optional[str] = None
    page: Optional[int] = None
    page_label: Optional[str] = None


class SendMessageResponse(BaseModel):
    message: str = Field(..., description="Assistant's response")
    user_message_id: int = Field(..., description="ID of saved user message")
    assistant_message_id: int = Field(..., description="ID of saved assistant message")
    sources: List[MessageSource] = Field(
        default_factory=list, description="Sources used for response"
    )
    persona_model: str = Field(..., description="LLM model used for generation")
    chat_id: int = Field(..., description="Chat ID")
    db_query_result: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            "DB tool audit (OpenAI Agents path when use_db=true). Legacy ChatService "
            "path does not populate this field."
        ),
    )
    attachments: List[Attachment] = Field(
        default_factory=list, description="Outputs (chart/table/file); [] when none"
    )

    @field_validator("attachments", mode="before")
    @classmethod
    def _null_attachments_to_empty_list(cls, value: Any) -> Any:
        return value or []


# Admin Chat Schemas
class AdminMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Admin message to send")


class IntentDetectionResult(BaseModel):
    behavior_change: bool = Field(
        ..., description="Whether user wants to change persona behavior"
    )
    rag_data: bool = Field(..., description="Whether user wants to retrieve data")


class PersonaUpdateResult(BaseModel):
    updated: bool = Field(..., description="Whether persona was updated")
    old_prompt: Optional[str] = Field(None, description="Previous persona prompt")
    new_prompt: Optional[str] = Field(None, description="New persona prompt")


class AdminMessageResponse(BaseModel):
    response: str = Field(..., description="Synthesized response from admin chat")
    intent: IntentDetectionResult = Field(..., description="Detected user intent")
    persona_update: Optional[PersonaUpdateResult] = Field(
        None, description="Persona update details (if behavior change occurred)"
    )
    sources: List[MessageSource] = Field(
        default_factory=list, description="RAG sources (if data retrieved)"
    )
    user_message_id: int = Field(..., description="ID of saved user message")
    assistant_message_id: int = Field(..., description="ID of saved assistant message")
    chat_id: int = Field(..., description="Chat ID")
    db_query_result: Optional[List[Dict[str, Any]]] = Field(
        None,
        description=(
            "DB tool audit (OpenAI Agents path). Legacy AdminChatService "
            "path does not populate this field."
        ),
    )
    attachments: List[Attachment] = Field(
        default_factory=list, description="Outputs (chart/table/file); [] when none"
    )

    @field_validator("attachments", mode="before")
    @classmethod
    def _null_attachments_to_empty_list(cls, value: Any) -> Any:
        return value or []
