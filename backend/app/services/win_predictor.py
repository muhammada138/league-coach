"""
Win Predictor – XGBoost-based match outcome estimator.

Features per player (5-dim):
  [rank_score, season_wr, form_score, mastery_score, streak_norm]

  - rank_score:    tier + division + LP bonus, normalised 0→1
  - season_wr:     wins/(wins+losses) with games-played confidence weighting
  - form_score:    avg perf score of last 5 games (0→1)
  - mastery_score: champion mastery proxy — 0.06/0.04/0.02/0.0 based on whether
                   the player's current champion appears in their top-1/2/3 most
                   played champions from recent match history
  - streak_norm:   current win/loss streak clamped ±3, normalised to [-1, 1]

Model input (15-dim):  [blue_mean(5), red_mean(5), diff(5)]

The XGBoost model is trained once on synthetic data that mirrors real LoL
win-probability dynamics, then persisted to disk.  Replace
model/win_predictor.pkl with a model trained on real Riot API match history
for better accuracy.
"""

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
TIER_SCORE = {
    "IRON": 1, "BRONZE": 2, "SILVER": 3, "GOLD": 4, "PLATINUM": 5,
    "EMERALD": 6, "DIAMOND": 7, "MASTER": 8, "GRANDMASTER": 9, "CHALLENGER": 10,
}
DIV_BONUS = {"I": 0.75, "II": 0.5, "III": 0.25, "IV": 0.0}
MAX_RANK  = 11.0  # Challenger I + max LP bonus

# Mastery tiers: how much edge does playing your main give you?
# Approximates a ~53–56% win rate on your main vs 50% on an off-pick.
_MASTERY_SCORES = [0.06, 0.04, 0.02]  # index 0 = most-played champ

MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "win_predictor.pkl"

# ---------------------------------------------------------------------------
# Global model handle
# ---------------------------------------------------------------------------
_model = None  # fitted XGBClassifier or None


# ---------------------------------------------------------------------------
# Model loader / trainer  (called once at startup)
# ---------------------------------------------------------------------------
def load_or_train_model() -> None:
    """Load persisted model from disk; if absent, train on synthetic data."""
    global _model
    try:
        import joblib  # noqa: PLC0415
        if MODEL_PATH.exists():
            _model = joblib.load(MODEL_PATH)
            logger.info("Loaded win predictor model from %s", MODEL_PATH)
        else:
            logger.info("No saved model – training on synthetic data (one-time, ~5 s)")
            _train_and_save()
    except ImportError:
        logger.warning("joblib/xgboost not installed – using linear fallback")
    except Exception as exc:
        logger.warning("Model load failed (%s) – using linear fallback", exc)


def _train_and_save() -> None:
    """
    Generate 20 000 synthetic matches and fit an XGBClassifier.

    The synthetic distribution matches the real-data feature distributions
    used at inference time so the model learns useful non-linear interactions
    (e.g. rank advantage matters more when form difference is also large).
    """
    try:
        import joblib          # noqa: PLC0415
        import xgboost as xgb  # noqa: PLC0415
        from sklearn.model_selection import train_test_split  # noqa: PLC0415

        rng = np.random.RandomState(42)
        WEIGHTS = np.array([0.40, 0.20, 0.30, 0.05, 0.05])

        X_list, y_list = [], []
        mastery_choices = [0.0, 0.02, 0.04, 0.06]
        mastery_probs   = [0.55, 0.15, 0.15, 0.15]   # ~45% off-pick games

        for _ in range(20_000):
            blue = np.array([
                rng.beta(4, 4),                                          # rank_score
                rng.beta(5, 5),                                          # season_wr
                rng.beta(4, 4),                                          # form_score
                rng.choice(mastery_choices, p=mastery_probs),            # mastery_score
                rng.uniform(-1.0, 1.0),                                  # streak_norm
            ])
            red = np.array([
                rng.beta(4, 4),
                rng.beta(5, 5),
                rng.beta(4, 4),
                rng.choice(mastery_choices, p=mastery_probs),
                rng.uniform(-1.0, 1.0),
            ])

            diff = blue - red
            prob = 1.0 / (1.0 + np.exp(-np.dot(diff, WEIGHTS) * 10.0))
            prob = 0.10 + prob * 0.80   # compress to [0.10, 0.90] — upsets exist

            y_list.append(int(rng.random() < prob))
            X_list.append(np.concatenate([blue, red, diff]))

        X = np.array(X_list)
        y = np.array(y_list)
        X_train, _, y_train, _ = train_test_split(X, y, test_size=0.1, random_state=42)

        model = xgb.XGBClassifier(
            n_estimators=150,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            eval_metric="logloss",
            random_state=42,
        )
        model.fit(X_train, y_train)

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        global _model
        _model = model
        logger.info("Trained and saved win predictor model to %s", MODEL_PATH)
    except Exception as exc:
        logger.warning("Model training failed (%s) – using linear fallback", exc)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
_NEUTRAL = np.array([0.5, 0.5, 0.5, 0.0, 0.0], dtype=float)


def _player_features(stats: dict, champion_id: int) -> np.ndarray:
    """Return a 5-dim feature vector for a single player."""
    tier = stats.get("tier", "UNRANKED")
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)

    # Completely unknown / hidden profile (streamer mode — no data at all) → neutral baseline
    if not stats or (tier == "UNRANKED" and wins == 0 and losses == 0 and not stats.get("last5")):
        return _NEUTRAL.copy()

    # 1. Rank score with LP  (0 → 1)
    if tier == "UNRANKED":
        # Unranked but has recent game data — treat as low Iron for rank purposes
        # (don't penalise too hard; they may be a smurf, but form score will reflect that)
        rank_score = 1.5 / MAX_RANK
    else:
        tier_val   = TIER_SCORE.get(tier, 3.5)
        div_val    = DIV_BONUS.get(stats.get("division", ""), 0.0)
        lp_bonus   = (stats.get("lp", 0) / 100.0) * 0.25   # up to +0.25 within a tier
        rank_score = min((tier_val + div_val + lp_bonus) / MAX_RANK, 1.0)

    # 2. Season WR with games-played confidence weighting
    #    Smurf / new accounts are regressed toward 0.5 until 200 games
    total    = wins + losses
    raw_wr   = wins / total if total > 0 else 0.5
    conf     = min(total / 200.0, 1.0)
    season_wr = raw_wr * conf + 0.5 * (1.0 - conf)

    # 3. Recent form (avg perf score of last 5 games, 0–100 → 0–1)
    form_score = stats.get("avg_score", 50) / 100.0

    # 4. Champion mastery score
    #    main_champs is a list of champion ID strings ordered by play frequency.
    #    Being on your #1 pick gives a +0.08 edge; #2 +0.05; #3 +0.03; off-pick 0.
    champ_id_str = str(champion_id)
    main_champs  = stats.get("main_champs", [])
    mastery_score = 0.0
    if champ_id_str in main_champs:
        idx = main_champs.index(champ_id_str)
        _MASTERY_WEIGHTS = [0.08, 0.05, 0.03]
        if idx < len(_MASTERY_WEIGHTS):
            mastery_score = _MASTERY_WEIGHTS[idx]

    # 5. Streak momentum normalised to [−1, 1]
    #    Increased importance: streak can now be up to ±5
    streak      = max(-5, min(5, stats.get("streak", 0)))
    streak_norm = streak / 5.0

    return np.array([rank_score, season_wr, form_score, mastery_score, streak_norm], dtype=float)


def _team_vector(player_feat_list: list) -> np.ndarray:
    arr = np.array(player_feat_list, dtype=float)
    return arr.mean(axis=0)


# ---------------------------------------------------------------------------
# Public inference function
# ---------------------------------------------------------------------------
def predict(participants: list[dict], live_stats: dict) -> dict:
    """
    Estimate win probability for both teams.

    Parameters
    ----------
    participants : list of dicts
        Each entry must have keys: ``puuid``, ``championId`` (int), ``teamId``
        (100 = blue, 200 = red).
    live_stats : dict
        Mapping of puuid → enrichment dict (from /live-enrich).

    Returns
    -------
    dict with ``bluePct`` and ``redPct`` integers that sum to 100.
    """
    blue_raw = [p for p in participants if p.get("teamId") == 100]
    red_raw  = [p for p in participants if p.get("teamId") == 200]

    def feats(players):
        result = [
            _player_features(live_stats.get(p["puuid"], {}), p.get("championId", 0))
            for p in players
        ]
        while len(result) < 5:
            result.append(_NEUTRAL.copy())
        return result[:5]

    blue_feats = feats(blue_raw)
    red_feats  = feats(red_raw)

    blue_vec = _team_vector(blue_feats)
    red_vec  = _team_vector(red_feats)
    diff_vec = blue_vec - red_vec

    X = np.concatenate([blue_vec, red_vec, diff_vec]).reshape(1, -1)

    if _model is not None:
        prob = float(_model.predict_proba(X)[0][1])
    else:
        w = np.array([0.40, 0.20, 0.30, 0.05, 0.05])
        b = float(np.dot(blue_vec, w))
        r = float(np.dot(red_vec, w))
        prob = b / (b + r) if (b + r) > 0 else 0.5

    blue_pct = max(1, min(99, round(prob * 100)))
    return {"bluePct": blue_pct, "redPct": 100 - blue_pct}
