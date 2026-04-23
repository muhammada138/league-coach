import re

with open("backend/app/services/win_predictor.py", "r") as f:
    content = f.read()

# Fix the recursion error: the model was trying to call predict recursively due to string replacement hitting a commented version
content = content.replace("prob = _predict_probability(blue_vec, red_vec, diff_vec)", "prob = float(_model.predict_proba(X)[0][1])", 1)

with open("backend/app/services/win_predictor.py", "w") as f:
    f.write(content)
