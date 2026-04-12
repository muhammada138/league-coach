import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL, timeout: 25000 });

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 429) {
      console.error("Riot API rate limit exceeded. Please try again in a few seconds.");
    }
    if (error.code === 'ECONNABORTED') {
      console.error("The request timed out. The backend or Riot API is slow.");
    }
    return Promise.reject(error);
  }
);

export const getSummoner = (gameName, tagLine) =>
  api.get(`/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}`).then((r) => r.data);

export const getProfile = (puuid) =>
  api.get(`/profile/${puuid}`).then((r) => r.data);

export const analyzeSummoner = (puuid, gameName, count = 10) =>
  api.get(`/analyze/${puuid}`, { params: { game_name: gameName, count } }).then((r) => r.data);

export const getHistory = (puuid, start, count, queue = 420) =>
  api.get(`/history/${puuid}`, { params: { start, count, queue } }).then((r) => r.data);

export const getScoreboard = (matchId) =>
  api.get(`/match/${matchId}/scoreboard`).then((r) => r.data);

export const askCoach = (question, context, history) =>
  api.post("/ask", { question, context, history }).then((r) => r.data);

export const getLiveGame = (puuid) =>
  api.get(`/live/${puuid}`).then((r) => r.data);

export const getLiveEnrich = (puuids) =>
  api.post("/live-enrich", { puuids }).then((r) => r.data);

export const getWinPredict = (participants, live_stats) =>
  api.post("/win-predict", { participants, live_stats }).then((r) => r.data);

export const getLpHistory = (puuid) =>
  api.get(`/lp-history/${puuid}`).then((r) => r.data);
