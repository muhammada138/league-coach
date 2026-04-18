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
import asyncio
from pathlib import Path
from collections import Counter

import numpy as np

try:
    import joblib
    import xgboost as xgb
    from sklearn.model_selection import train_test_split
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    joblib = None
    xgb = None
    train_test_split = None

from ..services.db import get_all_training_matches_sync, get_v1_training_matches_sync
from .meta_scraper import get_meta_data
from .role_identifier import assign_team_roles

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

# Riot tiers → meta data key. Iron/unranked use bronze; Grandmaster/Challenger use master.
_RANK_TO_META = {
    "iron": "bronze", "bronze": "bronze", "silver": "silver",
    "gold": "gold", "platinum": "platinum", "emerald": "emerald",
    "diamond": "diamond", "master": "master",
    "grandmaster": "master", "challenger": "master",
    "unranked": "bronze",
}

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
    All 9 features vary — teaches the model to weight form/streak/champ_wr
    in addition to rank and meta stats.
    """
    rng = np.random.RandomState(seed)
    # Weights for rank, season, form, recent, champ, mastery, streak, meta_wr, matchup
    WEIGHTS = np.array([0.30, 0.10, 0.25, 0.20, 0.08, 0.04, 0.03, 0.15, 0.10])
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
                rng.beta(5, 5), # meta_wr
                rng.beta(5, 5), # matchup
            ])
            r_feats.append([
                rng.beta(4, 4),
                rng.beta(5, 5),
                rng.beta(4, 4),
                rng.beta(4, 4),
                rng.beta(4, 4),
                rng.choice(mastery_choices, p=mastery_probs),
                rng.uniform(-1.0, 1.0),
                rng.beta(5, 5), # meta_wr
                rng.beta(5, 5), # matchup
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
        logger.info("Trained and saved win predictor model (9-dim) to %s", MODEL_PATH)
    except Exception as exc:
        logger.warning("Model training failed (%s) – using linear fallback", exc)


# ---------------------------------------------------------------------------
# Feature extraction
# ---------------------------------------------------------------------------
_NEUTRAL = np.array([0.5, 0.5, 0.5, 0.5, 0.5, 0.0, 0.0, 0.5, 0.5], dtype=float)


def _player_features(stats: dict, champion_id: int, champ_dict: dict, opponent_champion_id: int = 0, role: str = "all"):
    """Return a 9-dim feature vector for a single player, or None if hidden."""
    tier = stats.get("tier", "UNRANKED")
    wins = stats.get("wins", 0)
    losses = stats.get("losses", 0)

    # Completely unknown / hidden profile (streamer mode — no data at all)
    if not stats or (tier == "UNRANKED" and wins == 0 and losses == 0 and not stats.get("last5")):
        return None

    # 1. Rank score  (0 → 1)
    division = stats.get("division", "")
    lp_val = stats.get("lp", 0)
    if tier == "UNRANKED":
        # Has recent game data but no rank — treat as low Iron; form/recent_wr will carry them
        rank_score = 1.5 / MAX_RANK
    else:
        tier_val = TIER_SCORE.get(tier, 3.5)
        is_apex  = tier in ["MASTER", "GRANDMASTER", "CHALLENGER"]
        div_val  = 0.0 if is_apex else DIV_BONUS.get(division, 0.0)
        
        # In apex tiers, LP is the primary differentiator. We give it more weight.
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
    avg_score = stats.get("avg_score", 50)
    form_score = avg_score / 100.0

    # 4. Recent WR — actual win fraction of last 10 games (outcome trend)
    recent_wr_val = float(stats.get("recent_wr", 0.5))
    last5 = stats.get("last5", [])

    # 5. Champion-specific WR from last 10 games — confidence-weighted (full trust at 3+ games)
    champ_id_str = str(champion_id)
    champ_wr_map = stats.get("champ_wr_map", {})
    champ_data   = champ_wr_map.get(champ_id_str, [0, 0])
    champ_wins   = champ_data[0]
    champ_total  = champ_data[1]
    raw_champ_wr = champ_wins / champ_total if champ_total > 0 else 0.5
    champ_conf   = min(champ_total / 3.0, 1.0)
    champ_wr     = raw_champ_wr * champ_conf + 0.5 * (1.0 - champ_conf)

    # 6. Mastery score — is current champion in their top-3 most played recently?
    main_champs   = stats.get("main_champs", [])
    mastery_score = 0.0
    is_main = False
    if champ_id_str in main_champs:
        is_main = True
        idx = main_champs.index(champ_id_str)
        for threshold, val in [(0, 0.06), (1, 0.04), (2, 0.02)]:
            if idx == threshold:
                mastery_score = val
                break

    # 7. Streak momentum  (−1 → 1)
    streak_val  = stats.get("streak", 0)
    streak      = max(-5, min(5, streak_val))
    streak_norm = streak / 5.0

    # 8. Meta WR (Lolalytics) — how good is the champ in this rank?
    # Try lane-specific lookup first, then fall back to 'all'
    role_key = role.lower()
    if role_key == "utility": role_key = "support"

    champ_meta = champ_dict.get(f"{champ_id_str}:{role_key}")
    if not champ_meta:
        champ_meta = champ_dict.get(f"{champ_id_str}:all", champ_dict.get(champ_id_str, {}))

    # Lolalytics WR is usually around 50.0. Scale to 0-1.
    meta_wr_val = champ_meta.get("wr", 50.0)
    meta_wr = meta_wr_val / 100.0
    
    # 9. Matchup Advantage — Specific counter winrate from Lolalytics
    matchup_adv = 0.5
    vs_wr = 50.0
    matchup_games = 0
    matchup_conf = 0.0
    if opponent_champion_id:
        opp_id_str = str(opponent_champion_id)
        matchups = champ_meta.get("matchups", {})
        if opp_id_str in matchups:
            raw = matchups[opp_id_str]
            vs_wr = raw["wr"] if isinstance(raw, dict) else raw
            # Confidence-weight toward neutral when games count is low (<100 games)
            matchup_games = raw.get("games", 100) if isinstance(raw, dict) else 100
            matchup_conf = min(matchup_games / 100.0, 1.0)
            matchup_adv = (vs_wr / 100.0) * matchup_conf + 0.5 * (1.0 - matchup_conf)
        elif champ_meta:
            # Fallback: use relative meta WR difference as a proxy for matchup strength
            opp_meta = champ_dict.get(f"{opp_id_str}:{role_key}", champ_dict.get(f"{opp_id_str}:all", {}))
            opp_wr = opp_meta.get("wr", 50.0)
            vs_wr = 50.0 + (meta_wr_val - opp_wr)
            matchup_adv = max(0.0, min(1.0, 0.5 + (meta_wr - (opp_wr / 100.0))))
        # else: no champ meta at all (Naafiri bronze top) → stays 0.5 neutral

    details = {
        "rank": {"tier": tier, "division": division, "lp": lp_val, "score": round(float(rank_score), 3)},
        "season_wr": {"wins": wins, "losses": losses, "wr": round(float(raw_wr), 3), "conf": round(float(conf), 2)},
        "form": {"avg_score": avg_score, "label": "Hot" if avg_score > 65 else "Cold" if avg_score < 40 else "Steady"},
        "recent_wr": {"wr": round(float(recent_wr_val), 3), "last5": last5},
        "champ_wr": {"wins": champ_wins, "total": champ_total, "wr": round(float(raw_champ_wr), 3), "conf": round(float(champ_conf), 2)},
        "mastery": {"is_main": is_main, "score": round(float(mastery_score), 3)},
        "streak": {"value": streak_val, "norm": round(float(streak_norm), 2)},
        "meta_wr": {"wr": round(float(meta_wr), 3)},
        "matchup": {
            "opp_cid": opponent_champion_id, 
            "vs_wr": round(float(vs_wr), 1), 
            "games": matchup_games, 
            "conf": round(float(matchup_conf), 2), 
            "score": round(float(matchup_adv), 3)
        }
    }

    return np.array([
        rank_score, season_wr, form_score, recent_wr_val, champ_wr, 
        mastery_score, streak_norm, meta_wr, matchup_adv
    ], dtype=float), details


def _team_vector(player_feat_list: list) -> np.ndarray:
    arr = np.array(player_feat_list, dtype=float)
    return arr.mean(axis=0)


# ---------------------------------------------------------------------------
# Public inference function
# ---------------------------------------------------------------------------
async def predict(participants: list[dict], live_stats: dict) -> dict:
    """
    Estimate win probability for both teams.
    """
    if not participants:
        return {"error": "No participants provided."}

    # Identify roles for lane-specific features (matchup advantage)
    blue_raw = [p for p in participants if p.get("teamId") == 100]
    red_raw  = [p for p in participants if p.get("teamId") == 200]
    
    blue_roles, red_roles = await asyncio.gather(
        assign_team_roles([{"championId": p.get("championId", 0), "spells": [p.get("spell1Id"), p.get("spell2Id")] if "spell1Id" in p else []} for p in blue_raw]),
        assign_team_roles([{"championId": p.get("championId", 0), "spells": [p.get("spell1Id"), p.get("spell2Id")] if "spell1Id" in p else []} for p in red_raw])
    )
    
    # Map role -> championId for matchup lookup
    blue_role_map = {role: cid for cid, role in blue_roles.items()}
    red_role_map  = {role: cid for cid, role in red_roles.items()}

    # Determine lobby average rank
    known_tiers = [live_stats.get(p.get("puuid"), {}).get("tier") for p in participants if live_stats.get(p.get("puuid"), {}).get("tier")]
    lobby_rank = "EMERALD"
    if known_tiers:
        # Pick the most common tier as the anchor for meta stats
        lobby_rank = Counter(known_tiers).most_common(1)[0][0]

    # Load meta data once per prediction
    meta = get_meta_data()
    rank_key = _RANK_TO_META.get(lobby_rank.lower(), "emerald")
    champ_dict = meta.get("data", {}).get(rank_key, {}).get("champions", {})

    def get_feats(team_players, roles, opp_role_map):
        feats = []
        details_list = []
        for p in team_players:
            cid = p.get("championId", 0)
            role = roles.get(cid, "UNKNOWN")
            opp_cid = opp_role_map.get(role, 0)
            res = _player_features(live_stats.get(p.get("puuid", ""), {}), cid, champ_dict, opp_cid, role)
            if res:
                f, d = res
                feats.append(f)
                details_list.append(d)
            else:
                feats.append(None)
                details_list.append(None)
        return feats, details_list

    blue_feats, blue_details = get_feats(blue_raw, blue_roles, red_role_map)
    red_feats, red_details  = get_feats(red_raw, red_roles, blue_role_map)

    blue_known = [f for f in blue_feats if f is not None]
    red_known  = [f for f in red_feats if f is not None]
    all_known  = blue_known + red_known
    
    confidence = len(all_known) / len(participants) if participants else 0.0
    global_mean = np.mean(all_known, axis=0) if all_known else _NEUTRAL.copy()

    blue_team_mean = np.mean(blue_known, axis=0) if blue_known else global_mean.copy()
    red_team_mean  = np.mean(red_known, axis=0) if red_known else global_mean.copy()

    blue_vec = blue_team_mean
    red_vec  = red_team_mean
    diff_vec = blue_vec - red_vec

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

    _FEAT = ["rank", "season_wr", "form", "recent_wr", "champ_wr", "mastery", "streak", "meta_wr", "matchup"]
    features = {
        "blue": {k: round(float(blue_team_mean[i]), 3) for i, k in enumerate(_FEAT)},
        "red":  {k: round(float(red_team_mean[i]),  3) for i, k in enumerate(_FEAT)},
    }

    blue_pct = max(1, min(99, round(prob * 100)))
    return {
        "bluePct": blue_pct,
        "redPct": 100 - blue_pct,
        "confidence": round(float(confidence), 2),
        "features": features,
        "details": {
            "blue": blue_details,
            "red": red_details
        }
    }


# ---------------------------------------------------------------------------
# Retrain on real ingested data
# ---------------------------------------------------------------------------
def retrain_on_real_data() -> dict:
    """
    Train on real ingested match data. Synthetic data is only used when there
    are fewer than 500 real rows — at scale it biases the model toward manually-
    guessed feature weights instead of learning the true ones from outcomes.
    Hot-swaps the in-memory model on success.
    """
    global _model
    if not ML_AVAILABLE:
        return {"ok": False, "error": "ML dependencies not installed"}

    try:
        clean_rows = get_all_training_matches_sync()
        v1_rows    = get_v1_training_matches_sync()

        if len(clean_rows) >= 500:
            real_rows = clean_rows
            zero_form = False
            source    = "clean"
        elif len(v1_rows) >= 100:
            real_rows = v1_rows
            zero_form = True   # v1 form leaks outcome, zero it
            source    = "v1"
        else:
            # Not enough real data yet — fall back to synthetic only
            X, y = _generate_synthetic(20_000, seed=99)
            X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.15, random_state=42)
            model = xgb.XGBClassifier(
                n_estimators=300, max_depth=4, learning_rate=0.05,
                subsample=0.8, colsample_bytree=0.8,
                eval_metric="logloss", random_state=42,
            )
            model.fit(X_train, y_train)
            acc = float((model.predict(X_test) == y_test).mean())
            MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
            joblib.dump(model, MODEL_PATH)
            _model = model
            return {"ok": True, "source": "synthetic-only", "real_rows": 0, "synthetic_rows": 20_000, "test_accuracy": round(acc, 4)}

        # Build feature matrix — no synthetic mixing at this scale
        X_all, y_all = [], []
        for row in real_rows:
            blue = np.array(json.loads(row["blue_feats"]), dtype=float)
            red  = np.array(json.loads(row["red_feats"]),  dtype=float)
            if zero_form:
                blue[2] = 0.5
                red[2]  = 0.5
            diff = blue - red
            X_all.append(np.concatenate([blue, red, diff]))
            y_all.append(int(row["blue_won"]))

        X = np.array(X_all)
        y = np.array(y_all)

        # 85/15 stratified split preserves class balance in both sets
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.15, random_state=42, stratify=y
        )

        # Validation set for early stopping (carved from train)
        X_tr, X_val, y_tr, y_val = train_test_split(
            X_train, y_train, test_size=0.15, random_state=42, stratify=y_train
        )

        model = xgb.XGBClassifier(
            n_estimators=1000,      # high ceiling; early stopping finds the right number
            max_depth=4,
            learning_rate=0.02,     # lower lr → more trees → better generalisation
            subsample=0.8,
            colsample_bytree=0.7,
            min_child_weight=5,     # prevents splits on tiny leaf populations
            gamma=0.1,              # minimum gain to make a split
            reg_alpha=0.05,         # L1 regularisation
            reg_lambda=1.0,         # L2 regularisation
            eval_metric="logloss",
            early_stopping_rounds=50,
            random_state=42,
        )
        model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

        acc = float((model.predict(X_test) == y_test).mean())

        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(model, MODEL_PATH)
        _model = model

        best_n = model.best_iteration + 1
        logger.info("Retrained (%s) on %d rows, best_iteration=%d, test_acc=%.4f", source, len(real_rows), best_n, acc)
        return {
            "ok": True,
            "source": source,
            "real_rows": len(real_rows),
            "synthetic_rows": 0,
            "best_iteration": best_n,
            "test_accuracy": round(acc, 4),
        }

    except Exception as exc:
        logger.error("Retrain failed: %s", exc)
        return {"ok": False, "error": str(exc)}
