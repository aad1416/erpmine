from pydantic import BaseModel


class MakePostResponse(BaseModel):
    detail: str
