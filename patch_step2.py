import re

with open("backend/app/services/win_predictor.py", "r") as f:
    content = f.read()

helpers = """
def _get_team_features(team_players: list[dict], roles: dict, opp_role_map: dict, live_stats: dict, champ_dict: dict, lobby_mean_rank_score: float) -> tuple[list, list]:
    feats_with_roles = []
    for p in team_players:
        cid = p.get("championId", 0)
        role = roles.get(cid, "UNKNOWN")
        opp_cid = opp_role_map.get(role, 0)
        res = _player_features(live_stats.get(p.get("puuid", ""), {}), cid, champ_dict, opp_cid, role)
        if res:
            f, d = res
            d["puuid"] = p.get("puuid")
            # OVERRIDE: Rank is now a Delta against the lobby mean. 0.5 means EXACTLY lobby average.
            # Lower rank (smurf) = HIGHER delta score.
            # Higher rank (hardstuck) = LOWER delta score.
            raw_rank = f[0]
            smurf_delta = 0.5 + ((lobby_mean_rank_score - raw_rank) * 2.0)
            f[0] = max(0.0, min(1.0, smurf_delta))

            d["summonerName"] = p.get("summonerName", "Unknown")
            d["championName"] = p.get("championName", "Unknown")
            d["role"] = role
            feats_with_roles.append((f, d))
        else:
            feats_with_roles.append((None, None))

    # Sort by role priority: TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY, UNKNOWN
    role_order = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4, "UNKNOWN": 5}
    feats_with_roles.sort(key=lambda x: role_order.get(x[1].get("role", "UNKNOWN") if x[1] else "UNKNOWN", 99))

    return [x[0] for x in feats_with_roles], [x[1] for x in feats_with_roles]


def _impute_team_hidden_players(feats: list, details: list) -> None:
    # Instead of hardcoded 0.5 neutral, hidden players inherit mean of known teammates.
    known_indices = [i for i, d in enumerate(details) if not d.get("is_hidden", False)]
    if not known_indices:
        return  # Entire team hidden; keep neutral 0.5 fallback

    # Calculate mean of all features from known players
    # Note: We exclude index 8 (matchup_adv) from imputation as it is champion-specific
    # and already resolved for hidden players via meta-data proxies.
    known_vecs = [feats[i] for i in known_indices]
    team_mean = np.mean(known_vecs, axis=0)

    for i, d in enumerate(details):
        if d.get("is_hidden", False):
            # Update feature vector (indices 0-7: Rank, WR, Form, Recent, Champ, Mastery, Streak, Meta)
            # We now explicitly include Index 6 (Streak) for fairness
            feats[i][:8] = team_mean[:8]

            # Update details for the "Math" UI to be transparent
            d["rank"]["score"] = round(float(feats[i][0]), 3)
            d["rank"]["tier"] = "Hidden (Estimated)"

            # Season WR
            d["season_wr"]["wr"] = round(float(feats[i][1]), 3)
            d["season_wr"]["label"] = f"{int(feats[i][1]*100)}% (Estimated)"

            d["form"]["avg_score"] = int(feats[i][2] * 100)
            d["form"]["label"] = "Estimated"

            # Recent WR & Last 5 Visualization
            recent_wr = round(float(feats[i][3]), 3)
            d["recent_wr"]["wr"] = recent_wr
            d["recent_wr"]["label"] = "(Estimated)"
            # Generate a representative [True, True, False, ...] list based on WR
            wins_to_show = int(recent_wr * 5)
            d["recent_wr"]["last5"] = [True] * wins_to_show + [False] * (5 - wins_to_show)

            # Champ WR
            d["champ_wr"]["wr"] = round(float(feats[i][4]), 3)
            d["champ_wr"]["label"] = "(Estimated)"

            # Streak
            d["streak"]["value"] = round(float(feats[i][6] * 5), 1)
            d["streak"]["label"] = "(Estimated)"

            d["meta_wr"]["wr"] = round(float(feats[i][7]), 3)
            d["meta_wr"]["label"] = "(Estimated)"
"""

predict_old = """    def get_feats(team_players, roles, opp_role_map):
        feats_with_roles = []
        for p in team_players:
            cid = p.get("championId", 0)
            role = roles.get(cid, "UNKNOWN")
            opp_cid = opp_role_map.get(role, 0)
            res = _player_features(live_stats.get(p.get("puuid", ""), {}), cid, champ_dict, opp_cid, role)
            if res:
                f, d = res
                d["puuid"] = p.get("puuid")
                # OVERRIDE: Rank is now a Delta against the lobby mean. 0.5 means EXACTLY lobby average.
                # Lower rank (smurf) = HIGHER delta score.
                # Higher rank (hardstuck) = LOWER delta score.
                raw_rank = f[0]
                smurf_delta = 0.5 + ((lobby_mean_rank_score - raw_rank) * 2.0)
                f[0] = max(0.0, min(1.0, smurf_delta))

                d["summonerName"] = p.get("summonerName", "Unknown")
                d["championName"] = p.get("championName", "Unknown")
                d["role"] = role
                feats_with_roles.append((f, d))
            else:
                feats_with_roles.append((None, None))

        # Sort by role priority: TOP, JUNGLE, MIDDLE, BOTTOM, UTILITY, UNKNOWN
        role_order = {"TOP": 0, "JUNGLE": 1, "MIDDLE": 2, "BOTTOM": 3, "UTILITY": 4, "UNKNOWN": 5}
        feats_with_roles.sort(key=lambda x: role_order.get(x[1].get("role", "UNKNOWN") if x[1] else "UNKNOWN", 99))

        return [x[0] for x in feats_with_roles], [x[1] for x in feats_with_roles]

    blue_feats, blue_details = get_feats(blue_raw, blue_roles, red_role_map)
    red_feats, red_details  = get_feats(red_raw, red_roles, blue_role_map)

    # --- HEURISTIC IMPUTATION ---
    # Instead of hardcoded 0.5 neutral, hidden players inherit mean of known teammates.
    def impute_team(feats, details):
        known_indices = [i for i, d in enumerate(details) if not d.get("is_hidden", False)]
        if not known_indices:
            return  # Entire team hidden; keep neutral 0.5 fallback

        # Calculate mean of all features from known players
        # Note: We exclude index 8 (matchup_adv) from imputation as it is champion-specific
        # and already resolved for hidden players via meta-data proxies.
        known_vecs = [feats[i] for i in known_indices]
        team_mean = np.mean(known_vecs, axis=0)

        for i, d in enumerate(details):
            if d.get("is_hidden", False):
                # Update feature vector (indices 0-7: Rank, WR, Form, Recent, Champ, Mastery, Streak, Meta)
                # We now explicitly include Index 6 (Streak) for fairness
                feats[i][:8] = team_mean[:8]

                # Update details for the "Math" UI to be transparent
                d["rank"]["score"] = round(float(feats[i][0]), 3)
                d["rank"]["tier"] = "Hidden (Estimated)"

                # Season WR
                d["season_wr"]["wr"] = round(float(feats[i][1]), 3)
                d["season_wr"]["label"] = f"{int(feats[i][1]*100)}% (Estimated)"

                d["form"]["avg_score"] = int(feats[i][2] * 100)
                d["form"]["label"] = "Estimated"

                # Recent WR & Last 5 Visualization
                recent_wr = round(float(feats[i][3]), 3)
                d["recent_wr"]["wr"] = recent_wr
                d["recent_wr"]["label"] = "(Estimated)"
                # Generate a representative [True, True, False, ...] list based on WR
                wins_to_show = int(recent_wr * 5)
                d["recent_wr"]["last5"] = [True] * wins_to_show + [False] * (5 - wins_to_show)

                # Champ WR
                d["champ_wr"]["wr"] = round(float(feats[i][4]), 3)
                d["champ_wr"]["label"] = "(Estimated)"

                # Streak
                d["streak"]["value"] = round(float(feats[i][6] * 5), 1)
                d["streak"]["label"] = "(Estimated)"

                d["meta_wr"]["wr"] = round(float(feats[i][7]), 3)
                d["meta_wr"]["label"] = "(Estimated)"

    impute_team(blue_feats, blue_details)
    impute_team(red_feats, red_details)"""

predict_new = """    blue_feats, blue_details = _get_team_features(blue_raw, blue_roles, red_role_map, live_stats, champ_dict, lobby_mean_rank_score)
    red_feats, red_details  = _get_team_features(red_raw, red_roles, blue_role_map, live_stats, champ_dict, lobby_mean_rank_score)

    _impute_team_hidden_players(blue_feats, blue_details)
    _impute_team_hidden_players(red_feats, red_details)"""

# Insert the helpers before predict
content = content.replace("async def predict", helpers + "\n\nasync def predict")
content = content.replace(predict_old, predict_new)

with open("backend/app/services/win_predictor.py", "w") as f:
    f.write(content)
