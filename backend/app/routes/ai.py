from fastapi import APIRouter
from ..services.groq import ask_coach_question
from ..services import win_predictor
from ..models.requests import AskRequest, WinPredictRequest

router = APIRouter(tags=["AI & Coaching"])

@router.post("/ask")
async def ask_coach(body: AskRequest):
    system_prompt = (
        f"You are a League of Legends coach. Be casual, direct, human. Bold stats. 2-3 sentences max.\n"
        f"Always reference champion abilities by key (Q, W, E, R, Passive) — never use the ability's actual name. "
        f"Make tips specific to the champion's actual kit and how it enables their win conditions.\n\n"
        f"Player context:\n{body.context}"
    )
    history = [{"role": m.role, "content": m.content} for m in body.history]
    answer = await ask_coach_question(system_prompt, history, body.question)
    return {"answer": answer}

@router.post("/win-predict")
async def win_predict(body: WinPredictRequest):
    participants = [p.model_dump() for p in body.participants]
    return await win_predictor.predict(participants, body.live_stats)
