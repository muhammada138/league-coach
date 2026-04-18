from pydantic import BaseModel, field_validator
from typing import List, Dict, Any, Optional

class LiveEnrichRequest(BaseModel):
    puuids: List[str]
    queue_id: int = 420  # live game queueId — determines which match history queue to pull
    region: str = "na1"

class WinPredictParticipant(BaseModel):
    puuid: Optional[str] = ""
    championId: int
    teamId: int  # 100 = blue, 200 = red
    summonerName: str = "Unknown"
    championName: str = "Unknown"
    spell1Id: Optional[int] = 0
    spell2Id: Optional[int] = 0

    @field_validator('puuid', mode='before')
    @classmethod
    def coerce_none_puuid(cls, v):
        return v if v is not None else ""

    @field_validator('spell1Id', 'spell2Id', mode='before')
    @classmethod
    def coerce_none_to_zero(cls, v):
        return v if v is not None else 0

class WinPredictRequest(BaseModel):
    participants: List[WinPredictParticipant]
    live_stats: Dict[str, Any]

class ChatMessage(BaseModel):
    role: str
    content: str

class AskRequest(BaseModel):
    question: str
    context: str
    history: List[ChatMessage] = []
