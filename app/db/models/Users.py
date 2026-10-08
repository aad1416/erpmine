from typing import List

from pydantic import BaseModel


class User(BaseModel):
    id: str
    name: str
    username: str
    password: str = ""
    user_type: str = "user"
    store_id: str = ""
    accesses: List[str] = []
