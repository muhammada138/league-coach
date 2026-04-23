import re

with open("backend/app/services/win_predictor.py", "r") as f:
    content = f.read()

helper = """
def _calculate_lobby_rank_scores(participants: list[dict], live_stats: dict) -> tuple[str, float]:
    \"\"\"Calculate the most common tier and the mean rank score of known players.\"\"\"
    known_tiers = [
        live_stats.get(p.get("puuid"), {}).get("tier")
        for p in participants
        if live_stats.get(p.get("puuid"), {}).get("tier") and live_stats.get(p.get("puuid"), {}).get("tier") != "UNRANKED"
    ]

    lobby_rank = "EMERALD"
    if known_tiers:
        # Pick the most common tier as the anchor for meta stats
        lobby_rank = Counter(known_tiers).most_common(1)[0][0]

    known_rank_scores = []

    # Calculate exactly what the rank feature is (0.0 to 1.0)
    for p in participants:
         tier = live_stats.get(p.get("puuid"), {}).get("tier", "UNRANKED")
         if tier != "UNRANKED":
             div = live_stats.get(p.get("puuid"), {}).get("division", "")
             lp = live_stats.get(p.get("puuid"), {}).get("lp", 0)
             if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
                effective_lp = max(0, lp + {"MASTER": 0, "GRANDMASTER": 800, "CHALLENGER": 1600}.get(tier, 0))
                known_rank_scores.append(min(0.70 + (effective_lp / 5600.0) * 0.30, 1.0))
             else:
                t_val = TIER_SCORE.get(tier, 3.5)
                d_val = DIV_BONUS.get(div, 0.0)
                lp_b = (lp / 100.0) * 0.25
                known_rank_scores.append(min((t_val + d_val + lp_b) / MAX_RANK, 0.70))

    lobby_mean_rank_score = float(np.mean(known_rank_scores)) if known_rank_scores else 0.5
    return lobby_rank, lobby_mean_rank_score
"""

predict_old = """    # Map role -> championId for matchup lookup
    blue_role_map = {role: cid for cid, role in blue_roles.items()}
    red_role_map  = {role: cid for cid, role in red_roles.items()}

    # Determine lobby average rank
    known_tiers = [live_stats.get(p.get("puuid"), {}).get("tier") for p in participants if live_stats.get(p.get("puuid"), {}).get("tier") and live_stats.get(p.get("puuid"), {}).get("tier") != "UNRANKED"]
    lobby_rank = "EMERALD"
    if known_tiers:
        # Pick the most common tier as the anchor for meta stats
        lobby_rank = Counter(known_tiers).most_common(1)[0][0]

    known_rank_scores = []

    # Calculate exactly what the rank feature is (0.0 to 1.0)
    for p in participants:
         tier = live_stats.get(p.get("puuid"), {}).get("tier", "UNRANKED")
         if tier != "UNRANKED":
             div = live_stats.get(p.get("puuid"), {}).get("division", "")
             lp = live_stats.get(p.get("puuid"), {}).get("lp", 0)
             if tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]:
                effective_lp = max(0, lp + {"MASTER": 0, "GRANDMASTER": 800, "CHALLENGER": 1600}.get(tier, 0))
                known_rank_scores.append(min(0.70 + (effective_lp / 5600.0) * 0.30, 1.0))
             else:
                t_val = TIER_SCORE.get(tier, 3.5)
                d_val = DIV_BONUS.get(div, 0.0)
                lp_b = (lp / 100.0) * 0.25
                known_rank_scores.append(min((t_val + d_val + lp_b) / MAX_RANK, 0.70))

    lobby_mean_rank_score = float(np.mean(known_rank_scores)) if known_rank_scores else 0.5

    # Load meta data once per prediction"""

predict_new = """    # Map role -> championId for matchup lookup
    blue_role_map = {role: cid for cid, role in blue_roles.items()}
    red_role_map  = {role: cid for cid, role in red_roles.items()}

    lobby_rank, lobby_mean_rank_score = _calculate_lobby_rank_scores(participants, live_stats)

    # Load meta data once per prediction"""

# Insert the helper before predict
content = content.replace("async def predict", helper + "\n\nasync def predict")
content = content.replace(predict_old, predict_new)

with open("backend/app/services/win_predictor.py", "w") as f:
    f.write(content)
