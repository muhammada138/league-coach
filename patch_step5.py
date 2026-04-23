import re

with open("backend/app/services/win_predictor.py", "r") as f:
    content = f.read()

helper = """
def _apply_heuristics(prob: float, blue_synergy: float, red_synergy: float, blue_smurf: float, red_smurf: float) -> float:
    # Convert probability to logit, add precision adjustments, and convert back.
    # 0.08 logit translates to roughly +2% flat win odds at 50%.
    prob = max(1e-9, min(1.0 - 1e-9, prob))
    logit = np.log(prob / (1.0 - prob))

    # Apply Duo Synergy (coord) + Smurf Bonus (skill)
    logit += (blue_synergy - red_synergy) * 0.08
    logit += (blue_smurf - red_smurf) * 0.12 # Smurfs have higher individual agency than duos

    return 1.0 / (1.0 + np.exp(-logit))
"""

predict_old = """    # Convert probability to logit, add precision adjustments, and convert back.
    # 0.08 logit translates to roughly +2% flat win odds at 50%.
    prob = max(1e-9, min(1.0 - 1e-9, prob))
    logit = np.log(prob / (1.0 - prob))

    # Apply Duo Synergy (coord) + Smurf Bonus (skill)
    logit += (blue_synergy - red_synergy) * 0.08
    logit += (blue_smurf - red_smurf) * 0.12 # Smurfs have higher individual agency than duos

    prob = 1.0 / (1.0 + np.exp(-logit))"""

predict_new = """    prob = _apply_heuristics(prob, blue_synergy, red_synergy, blue_smurf, red_smurf)"""

# Insert the helper before predict
content = content.replace("async def predict", helper + "\n\nasync def predict")
content = content.replace(predict_old, predict_new)

with open("backend/app/services/win_predictor.py", "w") as f:
    f.write(content)
