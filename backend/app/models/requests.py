from pydantic import BaseModel
from typing import List

class LiveEnrichRequest(BaseModel):
    puuids: List[str]

class ChatMessage(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    context: str
    history: List[ChatMessage] = []
