import axios from "axios";

const api = axios.create({ baseURL: import.meta.env.VITE_API_URL });

export const getSummoner = (gameName, tagLine) =>
  api.get(`/summoner/${encodeURIComponent(gameName)}/${encodeURIComponent(tagLine)}`).then((r) => r.data);

export const getProfile = (puuid) =>
  api.get(`/profile/${puuid}`).then((r) => r.data);

export const analyzeSummoner = (puuid, gameName) =>
  api.get(`/analyze/${puuid}`, { params: { game_name: gameName } }).then((r) => r.data);

export const getHistory = (puuid, start, count) =>
  api.get(`/history/${puuid}`, { params: { start, count } }).then((r) => r.data);

export const getScoreboard = (matchId) =>
  api.get(`/match/${matchId}/scoreboard`).then((r) => r.data);

export const askCoach = (question, context, history) =>
  api.post("/ask", { question, context, history }).then((r) => r.data);
