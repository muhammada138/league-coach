import pytest
import numpy as np
from app.services.win_predictor import predict

@pytest.mark.asyncio
async def test_win_predict_with_hidden_players():
    # 10 participants, 5 per team
    participants = [
        {"puuid": f"p{i}", "teamId": 100 if i < 5 else 200, "championId": i}
        for i in range(10)
    ]

    # Only 8 players are known (4 per team)
    # p4 and p9 are hidden
    live_stats = {
        f"p{i}": {
            "tier": "GOLD", "division": "I", "lp": 50,
            "wins": 20, "losses": 18, "avg_score": 55,
            "recent_wr": 0.5, "streak": 0
        }
        for i in range(10) if i not in [4, 9]
    }

    prediction = await predict(participants, live_stats)

    # Verify confidence score is present
    assert "confidence" in prediction
    assert prediction["confidence"] == 0.8 # 8/10 players known
    assert "bluePct" in prediction
    assert "redPct" in prediction

@pytest.mark.asyncio
async def test_win_predict_all_hidden():
    participants = [
        {"puuid": f"p{i}", "teamId": 100 if i < 5 else 200, "championId": i}
        for i in range(10)
    ]
    live_stats = {} # All hidden

    prediction = await predict(participants, live_stats)

    assert "confidence" in prediction
    assert prediction["confidence"] == 0.0
    assert prediction["bluePct"] == 50 # Symmetrical neutral should be 50%
