import axios from "axios";

/**
 * Rift IQ API Client
 * 
 * Handles all communication between the frontend and the League Coach backend.
 */

const api = axios.create({ 
  baseURL: import.meta.env.VITE_API_URL, 
  timeout: 25000 
});

// --- Interceptors ---

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("admin_token");
  if (token) {
    config.headers["X-Admin-Token"] = token;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 429) {
      error.message = "Riot API is overloaded. Please wait 2 minutes.";
    } else if (error.code === 'ECONNABORTED') {
      error.message = "Request timed out. The server is taking too long.";
    }
    return Promise.reject(error);
  }
);

// --- Summoner & Profile ---

/**
 * Resolves a Riot ID (GameName#TagLine) to a PUUID.
 */
export const getSummoner = (gameName, tagLine, region = "na1") =>
  api.get(`/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}`, { params: { region } }).then((r) => r.data);

/**
 * Fetches the enriched player profile (Rank, Level, etc.).
 */
export const getProfile = (puuid, region = "na1", force = false) =>
  api.get(`/profile/${puuid}`, { params: { region, force } }).then((r) => r.data);

/**
 * Fetches champion mastery data for a specific player.
 */
export const getChampionMastery = (puuid, region = "na1") =>
  api.get(`/mastery/${puuid}`, { params: { region } }).then((r) => r.data);


// --- Analysis & History ---

/**
 * Triggers a deep analysis of a player based on recent games.
 */
export const analyzeSummoner = (puuid, gameName, count = 10, region = "na1", force = false) =>
  api.get(`/analyze/${puuid}`, { params: { game_name: gameName, count, region, force } }).then((r) => r.data);

/**
 * Fetches match history for a player with pagination and queue filtering.
 */
export const getHistory = (puuid, start, count, queue = 420, region = "na1") =>
  api.get(`/history/${puuid}`, { params: { start, count, queue, region } }).then((r) => r.data);

/**
 * Retrieves the performance scoreboard for a specific match.
 */
export const getScoreboard = (matchId, region = "na1") =>
  api.get(`/match/${matchId}/scoreboard`, { params: { region } }).then((r) => r.data);

/**
 * Fetches the match timeline data for a specific player's perspective.
 */
export const getMatchTimeline = (matchId, puuid, region = "na1") =>
  api.get(`/match/${matchId}/timeline/${puuid}`, { params: { region } }).then((r) => r.data);

/**
 * Fetches the 30-day LP history for a player from the local database.
 */
export const getLpHistory = (puuid, queue = 'RANKED_SOLO_5x5') =>
  api.get(`/lp-history/${puuid}`, { params: { queue } }).then((r) => r.data);


// --- Live Game Services ---

/**
 * Fetches active game data for a player if they are currently in-match.
 */
export const getLiveGame = (puuid, region = "na1") =>
  api.get(`/live/${puuid}`, { params: { region } }).then((r) => r.data);

/**
 * Enriches data for all participants in a live game.
 */
export const getLiveEnrich = (puuids, queueId = 420, region = "na1", force = false) =>
  api.post("/live-enrich", { puuids, queue_id: queueId, region, force }).then((r) => r.data);

/**
 * Runs the Win Predictor ML model for a set of participants.
 */
export const getWinPredict = (participants, live_stats) =>
  api.post("/win-predict", { participants, live_stats }).then((r) => r.data);


// --- AI Coaching ---

/**
 * Submits a question to the AI Coach with context and history.
 */
export const askCoach = (question, context, history) =>
  api.post("/ask", { question, context, history }).then((r) => r.data);


// --- Admin & Maintenance ---

/**
 * Gets a summary of cached data and training points.
 */
export const getAdminDataSummary = () =>
  api.get("/admin/data-summary").then((r) => r.data);

/**
 * Triggers a manual metadata sync from public sources.
 */
export const syncMeta = (mode = "full") =>
  api.post("/admin/sync-meta", null, { params: { mode } }).then((r) => r.data);

export const cancelSync = () =>
  api.post("/admin/cancel-sync").then((r) => r.data);

export const getSyncStatus = () =>
  api.get("/admin/sync-status").then((r) => r.data);

export const toggleSyncPause = () =>
  api.post("/admin/toggle-sync-pause").then((r) => r.data);

export const cleanupData = () =>
  api.post("/admin/cleanup").then((r) => r.data);

export const retrainModel = () =>
  api.post("/admin/retrain").then((r) => r.data);


// --- Ingestion Control ---

export const getIngestStatus = () =>
  api.get("/ingest/status").then((r) => r.data);

export const toggleIngest = () =>
  api.post("/ingest/toggle").then((r) => r.data);
