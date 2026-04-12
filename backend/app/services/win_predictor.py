"""
Win Predictor – XGBoost-based match outcome estimator.

Features per player (7-dim):
  [rank_score, season_wr, form_score, recent_wr, champ_wr, mastery_score, streak_norm]

  - rank_score:    tier + division + LP bonus, normalised 0→1
  - season_wr:     ranked wins/(wins+losses) confidence-weighted (full trust at 100 games)
  - form_score:    avg perf score of last 10 games (0→1) — quality signal
  - recent_wr:     actual W/L fraction of last 10 games (0→1) — outcome trend signal
  - champ_wr:      win rate on the specific champion being played, from last 10 games,
                   confidence-weighted toward 0.5 until 3+ games on that champ
  - mastery_score: whether current champ appears in their top-3 most played (0→0.06)
  - streak_norm:   current win/loss streak clamped ±5, normalised to [-1, 1]

Model input (21-dim):  [blue_mean(7), red_mean(7), diff(7)]

Trained on synthetic data that mirrors real LoL win-probability dynamics.
Replace model/win_predictor.pkl with a model trained on real Riot API match
history (see MEMORY.md future plans) for better accuracy.
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

MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "win_predictor_v2.pkl"

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

    7 features per player: rank_score, season_wr, form_score, recent_wr,
    champ_wr, mastery_score, streak_norm.  Model input = 21-dim
    [blue_mean, red_mean, diff].
    """
    try:
        import joblib          # noqa: PLC0415
        import xgboost as xgb  # noqa: PLC0415
        from sklearn.model_selection import train_test_split  # noqa: PLC0415

        rng = np.random.RandomState(42)
        # Feature weights mirror _player_features ordering
        WEIGHTS = np.array([0.30, 0.10, 0.25, 0.20, 0.08, 0.04, 0.03])

        X_list, y_list = [], []
        mastery_choices = [0.0, 0.02, 0.04, 0.06]
        mastery_probs   = [0.55, 0.15, 0.15, 0.15]

        for _ in range(20_000):
            blue = np.array([
                rng.beta(4, 4),                                # rank_score
                rng.beta(5, 5),                                # season_wr
                rng.beta(4, 4),                                # form_score
                rng.beta(4, 4),                                # recent_wr
                rng.beta(4, 4),                                # champ_wr
                rng.choice(mastery_choices, p=mastery_probs),  # mastery_score
                rng.uniform(-1.0, 1.0),                        # streak_norm
            ])
            red = np.array([
                rng.beta(4, 4),
                rng.beta(5, 5),
                rng.beta(4, 4),
                rng.beta(4, 4),
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
_NEUTRAL = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.0, 0.0], dtype=float)


def _player_features(stats: dict, champion_id: int) -> np.ndarray:
    """Return a 7-dim feature vector for a single player."""
    tier = stats.get("tier", "UNRANKED")
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)

    # Completely unknown / hidden profile (streamer mode — no data at all) → neutral baseline
    if not stats or (tier == "UNRANKED" and wins == 0 and losses == 0 and not stats.get("last5")):
        return _NEUTRAL.copy()

    # 1. Rank score  (0 → 1)
    if tier == "UNRANKED":
        # Has recent game data but no rank — treat as low Iron; form/recent_wr will carry them
        rank_score = 1.5 / MAX_RANK
    else:
        tier_val   = TIER_SCORE.get(tier, 3.5)
        div_val    = DIV_BONUS.get(stats.get("division", ""), 0.0)
        lp_bonus   = (stats.get("lp", 0) / 100.0) * 0.25
        rank_score = min((tier_val + div_val + lp_bonus) / MAX_RANK, 1.0)

    # 2. Season WR — confidence-weighted toward 0.5 (full trust at 100 games)
    total     = wins + losses
    raw_wr    = wins / total if total > 0 else 0.5
    conf      = min(total / 100.0, 1.0)
    season_wr = raw_wr * conf + 0.5 * (1.0 - conf)

    # 3. Form score — avg performance score from last 10 games (quality, not just W/L)
    form_score = stats.get("avg_score", 50) / 100.0

    # 4. Recent WR — actual win fraction of last 10 games (outcome trend)
    recent_wr = float(stats.get("recent_wr", 0.5))

    # 5. Champion-specific WR from last 10 games — confidence-weighted (full trust at 3+ games)
    champ_id_str = str(champion_id)
    champ_wr_map = stats.get("champ_wr_map", {})
    champ_data   = champ_wr_map.get(champ_id_str, [0, 0])
    champ_total  = champ_data[1]
    raw_champ_wr = champ_data[0] / champ_total if champ_total > 0 else 0.5
    champ_conf   = min(champ_total / 3.0, 1.0)
    champ_wr     = raw_champ_wr * champ_conf + 0.5 * (1.0 - champ_conf)

    # 6. Mastery score — is current champion in their top-3 most played recently?
    main_champs   = stats.get("main_champs", [])
    mastery_score = 0.0
    if champ_id_str in main_champs:
        idx = main_champs.index(champ_id_str)
        for threshold, val in [(0, 0.06), (1, 0.04), (2, 0.02)]:
            if idx == threshold:
                mastery_score = val
                break

    # 7. Streak momentum  (−1 → 1)
    streak      = max(-5, min(5, stats.get("streak", 0)))
    streak_norm = streak / 5.0

    return np.array([rank_score, season_wr, form_score, recent_wr, champ_wr, mastery_score, streak_norm], dtype=float)


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
        w = np.array([0.30, 0.10, 0.25, 0.20, 0.08, 0.04, 0.03])
        b = float(np.dot(blue_vec, w))
        r = float(np.dot(red_vec, w))
        prob = b / (b + r) if (b + r) > 0 else 0.5

    blue_pct = max(1, min(99, round(prob * 100)))
    return {"bluePct": blue_pct, "redPct": 100 - blue_pct}
