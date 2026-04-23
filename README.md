# Rift IQ

Rift IQ is a high-performance coaching and analytics platform for League of Legends that transforms raw match data into actionable competitive intelligence. By leveraging machine learning and large language models, it provides deep insights, real-time win predictions, and personalized coaching that goes far beyond traditional stat-tracking sites.

![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat&logo=tailwind-css&logoColor=white)
![Groq](https://img.shields.io/badge/Groq_AI-LLaMA_3.3_70B-orange?style=flat)

Live Link: [RiftIQ](https://league-coach.vercel.app/)

---

## 🚀 Core Features

### 📊 Lobby-Relative Benchmarking
Most tools compare you to global averages. Rift IQ benchmarks your performance directly against the other nine players in your actual match. This identifies whether you were truly the game-changer or simply riding a team lead.

### 🔮 ML Win Predictor (Elite Maintenance)
Our real-time win probability engine uses a custom XGBoost model trained on high-level matches. It features intelligent data imputation for private profiles and generates confidence scores to quantify match volatility.

### 🤖 AI Coaching (LLaMA 3.3 70B)
Get personalized, context-aware advice. Powered by LLaMA 3.3 via Groq, the coach analyzes your specific performance deltas (Vision, Combat, Gold Efficiency) to provide 3-4 high-impact improvements for your next game.

### 🛡️ Secure Admin Dashboard
A robust administrative suite allowing for manual data retraining, meta-data synchronization from top-tier analytics sources (Lolalytics/OP.GG), and granular cache management—all protected by secure token-based authentication.

### 📉 LP & Trend Analysis
Visualize your climb with interactive Recharts-powered graphs. Track LP gains/losses and correlate your performance score with actual rank progression over any time period.

---

## 🛠️ Technical Architecture

Rift IQ uses a domain-driven, asynchronous architecture designed for elite responsiveness:

- **Frontend**: A modular React 19 application with highly-optimized components. Built-in `useMemo` caching prevents UI lag during heavy data processing.
- **Backend (DDD)**: Decomposed monolithic API into domain-specific routers (`player`, `analysis`, `live`, `admin`, `ai`) for better maintainability and performance.
- **Security**: Implements `X-Admin-Token` middleware to secure sensitive administrative and ingestion endpoints.
- **Persistence**: Hybrid storage using local JSON for champion meta-data and SQLite for high-speed match history queries.

---

## ⚙️ environment Configuration

Your `.env` file must include the following variables to function:

```env
# Riot & External APIs
RIOT_API_KEY=your_riot_api_key
GROQ_API_KEY=your_groq_api_key

# Region Configuration
RIOT_REGION=na1
RIOT_ROUTING=americas

# Security
ADMIN_API_KEY=your_secure_admin_token
```

---

## 📡 API Reference

| Method | Route | Description |
|---|---|---|
| `GET` | `/summoner/...` | Resolves Riot ID to PUUID & Account details. |
| `GET` | `/analyze/...` | Performs full performance analysis & coaching generation. |
| `GET` | `/live/...` | Monitors live game state & identifies roles/matchups. |
| `POST` | `/admin/sync-meta` | Triggers background scraping of meta-data (Secured). |
| `GET` | `/admin/data-summary`| Retrieves global system stats & DB health (Secured). |
| `POST` | `/ask` | Interactive Q&A with the AI Coach. |

---

## 🏗️ Getting Started

### Backend Setup
1. `cd backend`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` (Add your keys)
4. `uvicorn app.main:app --reload`

### Frontend Setup
1. `cd frontend`
2. `npm install`
3. `npm run dev`

---

## 🧠 How It Works

1. **Ingest**: Matches are fetched in parallel using non-blocking async requests.
2. **Engineer**: Stats are normalized into relative deltas (e.g., "Diff vs Lane Opponent").
3. **Predict**: The ML pipeline calculates win probability based on live synergy and historical consistency.
4. **Synthesize**: Performance deltas are fed into the LLM as high-context JSON to generate precise coaching hooks.
5. **Persist**: Results are snapshotted to SQLite for rapid retrieval and trend mapping.
