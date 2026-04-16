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

import json
import logging
from pathlib import Path

import numpy as np

try:
    import joblib
    import xgboost as xgb
    from sklearn.model_selection import train_test_split

    ML_AVAILABLE = True
except ImportError:
    joblib = None  # type: ignore
    xgb = None  # type: ignore
    train_test_split = None  # type: ignore
    ML_AVAILABLE = False

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

MODEL_PATH = Path(__file__).parent.parent.parent / "model" / "win_predictor_v4.pkl"

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
    if not ML_AVAILABLE:
        logger.warning("joblib/xgboost not installed – using linear fallback")
        return

    try:
        if MODEL_PATH.exists():
            _model = joblib.load(MODEL_PATH)
            logger.info("Loaded win predictor model from %s", MODEL_PATH)
        else:
            logger.info("No saved model – training on synthetic data (one-time, ~5 s)")
            _train_and_save()
    except Exception as exc:
        logger.warning("Model load failed (%s) – using linear fallback", exc)


def _generate_synthetic(n: int, seed: int = 42) -> tuple:
    """
    Generate n synthetic match rows. Returns (X, y) numpy arrays.
    All 7 features vary — teaches the model to weight form/streak/champ_wr
    in addition to rank and season WR.
    """
    rng = np.random.RandomState(seed)
    WEIGHTS = np.array([0.30, 0.10, 0.25, 0.20, 0.08, 0.04, 0.03])
    mastery_choices = [0.0, 0.02, 0.04, 0.06]
    mastery_probs   = [0.55, 0.15, 0.15, 0.15]

    X_list, y_list = [], []
    for _ in range(n):
        b_feats, r_feats = [], []
        for _p in range(5):
            b_feats.append([
                rng.beta(4, 4),
                rng.beta(5, 5),
                rng.beta(4, 4),
                rng.beta(4, 4),
                rng.beta(4, 4),
                rng.choice(mastery_choices, p=mastery_probs),
                rng.uniform(-1.0, 1.0),
            ])
            r_feats.append([
                rng.beta(4, 4),
                rng.beta(5, 5),
                rng.beta(4, 4),
                rng.beta(4, 4),
                rng.beta(4, 4),
                rng.choice(mastery_choices, p=mastery_probs),
                rng.uniform(-1.0, 1.0),
            ])
        blue = np.mean(b_feats, axis=0)
        red  = np.mean(r_feats, axis=0)
        diff = blue - red
        prob = 1.0 / (1.0 + np.exp(-np.dot(diff, WEIGHTS) * 25.0))
        prob = 0.10 + prob * 0.80
        y_list.append(int(rng.random() < prob))
        X_list.append(np.concatenate([blue, red, diff]))
    return np.array(X_list), np.array(y_list)


def _train_and_save() -> None:
    """Train on synthetic data and save. Used when no real data exists yet."""
    try:
        X, y = _generate_synthetic(20_000)
        X_train, _, y_train, _ = train_test_split(X, y, test_size=0.1, random_state=42)

        model = xgb.XGBClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            eval_metric="logloss", random_state=42,
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


def _player_features(stats: dict, champion_id: int):
    """Return a 7-dim feature vector for a single player, or None if hidden."""
    tier = stats.get("tier", "UNRANKED")
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)

    # Completely unknown / hidden profile (streamer mode — no data at all)
    if not stats or (tier == "UNRANKED" and wins == 0 and losses == 0 and not stats.get("last5")):
        return None

    # 1. Rank score  (0 → 1)
    if tier == "UNRANKED":
        # Has recent game data but no rank — treat as low Iron; form/recent_wr will carry them
        rank_score = 1.5 / MAX_RANK
    else:
        tier_val = TIER_SCORE.get(tier, 3.5)
        is_apex  = tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]
        div_val  = 0.0 if is_apex else DIV_BONUS.get(stats.get("division", ""), 0.0)
        
        # In apex tiers, LP is the primary differentiator. We give it more weight.
        lp_val = stats.get("lp", 0)
        if is_apex:
            # 100 LP in Master ≈ 0.4 rank points (vs 0.25 normally)
            lp_bonus = (lp_val / 100.0) * 0.4
        else:
            lp_bonus = (lp_val / 100.0) * 0.25
            
        rank_score = min((tier_val + div_val + lp_bonus) / MAX_RANK, 1.2) / 1.2 # Allow some headroom

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

    # Extract features, leaving None for hidden players
    blue_feats = [_player_features(live_stats.get(p.get("puuid", ""), {}), p.get("championId", 0)) for p in blue_raw]
    red_feats  = [_player_features(live_stats.get(p.get("puuid", ""), {}), p.get("championId", 0)) for p in red_raw]

    # A team's vector is simply the mean of its known players.
    # This prevents hidden players from dragging the team average toward the opponent's stats.
    blue_known = [f for f in blue_feats if f is not None]
    red_known  = [f for f in red_feats if f is not None]
    all_known  = blue_known + red_known
    global_mean = np.mean(all_known, axis=0) if all_known else _NEUTRAL.copy()

    blue_vec = np.mean(blue_known, axis=0) if blue_known else global_mean.copy()
    red_vec  = np.mean(red_known, axis=0) if red_known else global_mean.copy()
    diff_vec = blue_vec - red_vec

    X = np.concatenate([blue_vec, red_vec, diff_vec]).reshape(1, -1)

    if _model is not None:
        prob = float(_model.predict_proba(X)[0][1])
    else:
        w = np.array([0.30, 0.10, 0.25, 0.20, 0.08, 0.04, 0.03])
        diff_val = float(np.dot(blue_vec - red_vec, w))
        prob = 1.0 / (1.0 + np.exp(-diff_val * 25.0))

    blue_pct = max(1, min(99, round(prob * 100)))
    return {"bluePct": blue_pct, "redPct": 100 - blue_pct}


# ---------------------------------------------------------------------------
# Retrain on real ingested data
# ---------------------------------------------------------------------------
def retrain_on_real_data() -> dict:
    """
    Hybrid retrain strategy:
    - If clean training_matches has >= 5k rows: train on clean data + 5k synthetic
    - Otherwise: fall back to v1 legacy data (form zeroed) + 20k synthetic

    Synthetic data teaches the model to weight form/streak/champ_wr correctly
    for live game prediction, while real data anchors rank and season_WR signal.
    Hot-swaps the in-memory model on success.
    """
    global _model
    try:
        from ..services.db import get_all_training_matches_sync, get_v1_training_matches_sync

        clean_rows = get_all_training_matches_sync()
        v1_rows    = get_v1_training_matches_sync()

        if len(clean_rows) >= 5000:
            real_rows  = clean_rows
            zero_form  = False        # clean data has non-leaking form
            synth_n    = 5000
            source     = "clean"
        elif len(v1_rows) >= 100:
            real_rows  = v1_rows
            zero_form  = True         # v1 form leaks outcome, zero it
            synth_n    = 20000
            source     = "v1+synthetic"
        else:
            real_rows  = []
            zero_form  = False
            synth_n    = 20000
            source     = "synthetic-only"

        # Build feature matrix from real rows
        X_real, y_real = [], []
        for row in real_rows:
            blue = np.array(json.loads(row["blue_feats"]), dtype=float)
            red  = np.array(json.loads(row["red_feats"]),  dtype=float)
            if zero_form:
                blue[2] = 0.5
                red[2]  = 0.5
            diff = blue - red
            X_real.append(np.concatenate([blue, red, diff]))
            y_real.append(int(row["blue_won"]))

        # Combine with synthetic
        X_syn, y_syn = _generate_synthetic(synth_n, seed=99)
        if X_real:
            X = np.vstack([np.array(X_real), X_syn])
            y = np.concatenate([np.array(y_real), y_syn])
        else:
            X, y = X_syn, y_syn

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.1, random_state=42
        )

        model = xgb.XGBClassifier(
            n_estimators=200, max_depth=4, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            eval_metric="logloss", random_state=42,
        )
        model.fit(X_train, y_train)

        acc = float((model.predict(X_test) == y_test).mean())

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        _model = model

        logger.info(
            "Retrained (%s) on %d real + %d synthetic — test acc %.3f",
            source, len(real_rows), synth_n, acc,
        )
        return {
            "ok": True,
            "source": source,
            "real_rows": len(real_rows),
            "synthetic_rows": synth_n,
            "test_accuracy": round(acc, 4),
        }

    except Exception as exc:
        logger.error("Retrain failed: %s", exc)
        return {"ok": False, "error": str(exc)}
