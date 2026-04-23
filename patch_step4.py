import re

with open("backend/app/services/win_predictor.py", "r") as f:
    content = f.read()

helpers = """
def _get_team_synergy(team_details: list[dict], live_stats: dict) -> float:
    # Synergistic duos give massive real-game advantages through coordination.
    groups = {}
    for d in team_details:
        if not d: continue
        puuid = d.get("puuid")
        stats = live_stats.get(puuid, {})
        gid = stats.get("duo_group", 0)
        if gid != 0:
            groups.setdefault(gid, []).append(d.get("role", "UNKNOWN"))

    score = 0.0
    for gid, roles in groups.items():
        if len(roles) >= 2:
            score += 1.0 # base duo bonus
            roles_set = set(roles)
            if {"BOTTOM", "UTILITY"}.issubset(roles_set):
                score += 0.7 # High synergy: Bot lane
            elif {"MIDDLE", "JUNGLE"}.issubset(roles_set):
                score += 0.5 # High synergy: Mid/Jg
            elif {"TOP", "JUNGLE"}.issubset(roles_set):
                score += 0.4 # High synergy: Top/Jg
    return min(score, 3.0)

def _get_team_smurf_bonus(team_details: list[dict], live_stats: dict) -> float:
    # Smurfs possess significantly higher individual skill than their current rank suggests.
    bonus = 0.0
    for d in team_details:
        if not d: continue
        puuid = d.get("puuid")
        stats = live_stats.get(puuid, {})
        if stats.get("is_smurf"):
            # A single smurf is a massive threat (+2.5% odds)
            bonus += 1.0
    return min(bonus, 2.5) # Cap at 2.5 smurfs worth of impact
"""

predict_old = """    # --- DUO SYNERGY ADJUSTMENT ---
    # Synergistic duos give massive real-game advantages through coordination.
    def get_synergy(team_details):
        groups = {}
        for d in team_details:
            if not d: continue
            puuid = d.get("puuid")
            stats = live_stats.get(puuid, {})
            gid = stats.get("duo_group", 0)
            if gid != 0:
                groups.setdefault(gid, []).append(d.get("role", "UNKNOWN"))

        score = 0.0
        for gid, roles in groups.items():
            if len(roles) >= 2:
                score += 1.0 # base duo bonus
                roles_set = set(roles)
                if {"BOTTOM", "UTILITY"}.issubset(roles_set):
                    score += 0.7 # High synergy: Bot lane
                elif {"MIDDLE", "JUNGLE"}.issubset(roles_set):
                    score += 0.5 # High synergy: Mid/Jg
                elif {"TOP", "JUNGLE"}.issubset(roles_set):
                    score += 0.4 # High synergy: Top/Jg
        return min(score, 3.0)

    blue_synergy = get_synergy(blue_details)
    red_synergy = get_synergy(red_details)

    # --- SMURF ADJUSTMENT ---
    # Smurfs possess significantly higher individual skill than their current rank suggests.
    def get_smurf_bonus(team_details):
        bonus = 0.0
        for d in team_details:
            if not d: continue
            puuid = d.get("puuid")
            stats = live_stats.get(puuid, {})
            if stats.get("is_smurf"):
                # A single smurf is a massive threat (+2.5% odds)
                bonus += 1.0
        return min(bonus, 2.5) # Cap at 2.5 smurfs worth of impact

    blue_smurf = get_smurf_bonus(blue_details)
    red_smurf = get_smurf_bonus(red_details)"""

predict_new = """    blue_synergy = _get_team_synergy(blue_details, live_stats)
    red_synergy = _get_team_synergy(red_details, live_stats)

    blue_smurf = _get_team_smurf_bonus(blue_details, live_stats)
    red_smurf = _get_team_smurf_bonus(red_details, live_stats)"""

# Insert the helpers before predict
content = content.replace("async def predict", helpers + "\n\nasync def predict")
content = content.replace(predict_old, predict_new)

with open("backend/app/services/win_predictor.py", "w") as f:
    f.write(content)
