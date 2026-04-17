import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL, timeout: 25000 });

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

export const getSummoner = (gameName, tagLine, region = "na1") =>
  api.get(`/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}`, { params: { region } }).then((r) => r.data);

export const getProfile = (puuid, region = "na1") =>
  api.get(`/profile/${puuid}`, { params: { region } }).then((r) => r.data);

export const analyzeSummoner = (puuid, gameName, count = 10, region = "na1") =>
  api.get(`/analyze/${puuid}`, { params: { game_name: gameName, count, region } }).then((r) => r.data);

export const getHistory = (puuid, start, count, queue = 420, region = "na1") =>
  api.get(`/history/${puuid}`, { params: { start, count, queue, region } }).then((r) => r.data);

export const getScoreboard = (matchId, region = "na1") =>
  api.get(`/match/${matchId}/scoreboard`, { params: { region } }).then((r) => r.data);

export const askCoach = (question, context, history) =>
  api.post("/ask", { question, context, history }).then((r) => r.data);

export const getLiveGame = (puuid, region = "na1") =>
  api.get(`/live/${puuid}`, { params: { region } }).then((r) => r.data);

export const getLiveEnrich = (puuids, queueId = 420, region = "na1") =>
  api.post("/live-enrich", { puuids, queue_id: queueId, region }).then((r) => r.data);

export const getWinPredict = (participants, live_stats) =>
  api.post("/win-predict", { participants, live_stats }).then((r) => r.data);

export const getLpHistory = (puuid, queue = 'RANKED_SOLO_5x5') =>
  api.get(`/lp-history/${puuid}`, { params: { queue } }).then((r) => r.data);

export const getTeammates = (puuid) =>
  api.get(`/teammates/${puuid}`).then((r) => r.data);

export const getAdminDataSummary = () =>
  api.get("/admin/data-summary").then((r) => r.data);

export const syncMeta = (mode = "full") =>
  api.post("/admin/sync-meta", null, { params: { mode } }).then((r) => r.data);

export const cancelSync = () =>
  api.post("/admin/cancel-sync").then((r) => r.data);

export const toggleSyncPause = () =>
  api.post("/admin/toggle-sync-pause").then((r) => r.data);

export const cleanupData = () =>
  api.post("/admin/cleanup").then((r) => r.data);

export const getIngestStatus = () =>
  api.get("/ingest/status").then((r) => r.data);

export const toggleIngest = () =>
  api.post("/ingest/toggle").then((r) => r.data);
