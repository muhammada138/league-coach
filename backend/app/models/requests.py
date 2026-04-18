from pydantic import BaseModel
from typing import List, Dict, Any

class LiveEnrichRequest(BaseModel):
    puuids: List[str]
    queue_id: int = 420  # live game queueId — determines which match history queue to pull
    region: str = "na1"

class WinPredictParticipant(BaseModel):
    puuid: str
    championId: int
    teamId: int  # 100 = blue, 200 = red
    summonerName: str = "Unknown"
    championName: str = "Unknown"

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
