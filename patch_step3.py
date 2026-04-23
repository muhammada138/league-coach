import re

with open("backend/app/services/win_predictor.py", "r") as f:
    content = f.read()

helper = """
def _predict_probability(blue_vec: np.ndarray, red_vec: np.ndarray, diff_vec: np.ndarray) -> float:
    X = np.concatenate([blue_vec, red_vec, diff_vec]).reshape(1, -1)

    if _model is not None:
        # Ensure X is the right shape for the model (might be 7 or 9 dim depending on training)
        # If model is 7-dim, truncate X to 7 features per team (total 21)
        expected_dim = _model.n_features_in_
        if expected_dim == 21 and X.shape[1] == 27:
            # Truncate each team's features (first 7 of 9)
            blue_7 = blue_vec[:7]
            red_7 = red_vec[:7]
            diff_7 = diff_vec[:7]
            X = np.concatenate([blue_7, red_7, diff_7]).reshape(1, -1)

        prob = float(_model.predict_proba(X)[0][1])
    else:
        # Linear fallback with 9-dim weights
        w = np.array([0.30, 0.10, 0.25, 0.20, 0.08, 0.04, 0.03, 0.15, 0.10])
        diff_val = float(np.dot(blue_vec - red_vec, w))
        prob = 1.0 / (1.0 + np.exp(-diff_val * 25.0))

    return prob
"""

predict_old = """    X = np.concatenate([blue_vec, red_vec, diff_vec]).reshape(1, -1)

    if _model is not None:
        # Ensure X is the right shape for the model (might be 7 or 9 dim depending on training)
        # If model is 7-dim, truncate X to 7 features per team (total 21)
        expected_dim = _model.n_features_in_
        if expected_dim == 21 and X.shape[1] == 27:
            # Truncate each team's features (first 7 of 9)
            blue_7 = blue_vec[:7]
            red_7 = red_vec[:7]
            diff_7 = diff_vec[:7]
            X = np.concatenate([blue_7, red_7, diff_7]).reshape(1, -1)

        prob = float(_model.predict_proba(X)[0][1])
    else:
        # Linear fallback with 9-dim weights
        w = np.array([0.30, 0.10, 0.25, 0.20, 0.08, 0.04, 0.03, 0.15, 0.10])
        diff_val = float(np.dot(blue_vec - red_vec, w))
        prob = 1.0 / (1.0 + np.exp(-diff_val * 25.0))"""

predict_new = """    prob = _predict_probability(blue_vec, red_vec, diff_vec)"""

# Insert the helper before predict
content = content.replace("async def predict", helper + "\n\nasync def predict")
content = content.replace(predict_old, predict_new)

with open("backend/app/services/win_predictor.py", "w") as f:
    f.write(content)
