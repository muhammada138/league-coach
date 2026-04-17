import pytest
import numpy as np
from app.services import win_predictor

def test_win_predict_with_hidden_players():
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
    
    prediction = win_predictor.predict(participants, live_stats)
    
    # Verify confidence score is present
    assert "confidence" in prediction
    # 8 out of 10 players are known, so confidence should be 0.8
    assert prediction["confidence"] == pytest.approx(0.8)
    
    assert "bluePct" in prediction
    assert "redPct" in prediction
    assert prediction["bluePct"] + prediction["redPct"] == 100

def test_win_predict_all_hidden():
    participants = [
        {"puuid": f"p{i}", "teamId": 100 if i < 5 else 200, "championId": i}
        for i in range(10)
    ]
    live_stats = {} # All hidden
    
    prediction = win_predictor.predict(participants, live_stats)
    
    assert "confidence" in prediction
    assert prediction["confidence"] == 0.0
    assert prediction["bluePct"] == 50
    assert prediction["redPct"] == 50
