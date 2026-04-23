# Rift IQ

Rift IQ is a high-performance coaching and analytics platform for League of Legends that transforms raw match data into actionable competitive intelligence. By leveraging machine learning and large language models, it provides a level of insight that goes far beyond traditional stat-tracking sites.

![React](https://img.shields.io/badge/React-19-61DAFB?style=flat&logo=react&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-38B2AC?style=flat&logo=tailwind-css&logoColor=white)
![Groq](https://img.shields.io/badge/Groq_AI-LLaMA_3.3_70B-orange?style=flat)

Live at [RiftIQ](https://league-coach.vercel.app/)

---

## Screenshots

![Rift IQ Dashboard](./screenshot.png)

## Core Features

### Lobby-Relative Benchmarking
Most tools compare you to global averages, which can be misleading depending on the specific game state. Rift IQ benchmarks your performance directly against the other nine players in your actual match. This provides a true reflection of your impact on the game, identifying whether you were truly the "diff" or just riding a team lead.

### ML Win Predictor
Our real-time win probability engine uses a custom XGBoost model trained on thousands of high-level matches. It features a refined "Streamer Mode" that handles missing data through intelligent imputation, ensuring accurate predictions even when player profiles are private. Every prediction comes with a confidence score to help you understand the volatility of the match.

### Deep Duo Stats
Scout your synergy with premade partners using our dedicated duo analysis. Rift IQ tracks shared winrates, identifies your most successful champion pairings, and provides a breakdown of how you perform when playing together versus playing solo.

### AI Coaching
Get personalized, professional-grade advice from an AI coach powered by LLaMA 3.3 70B via Groq. Instead of generic tips, the coach analyzes your specific performance deltas in vision, combat, and economy to give you 3 to 4 high-impact improvements for your next game.

### LP Trend Analysis
Visualize your climb with interactive graphs backed by a local SQLite database. Track your LP gains and losses over time, identify winning streaks, and see how your performance score correlates with your actual rank progression.

---

## Technical Architecture

Rift IQ is built with a modern, asynchronous stack designed for speed and reliability:

- **Frontend**: A responsive React 19 application styled with Tailwind CSS, featuring interactive Recharts visualizations and a seamless "Streamer Mode" toggle.
- **Backend**: A high-performance FastAPI server that orchestrates parallel data fetching from the Riot API and manages the ML inference pipeline.
- **Intelligence**: Integration with Groq for ultra-fast LLM inference and a custom-trained XGBoost model for win probability estimation.
- **Storage**: A lightweight SQLite implementation for persistent match history and trend tracking without the overhead of a full database cluster.

---

## Getting Started

To run Rift IQ locally, you will need a [Riot API key](https://developer.riotgames.com/) and a [Groq API key](https://console.groq.com/).

### Backend Setup

1. Navigate to the backend directory: `cd backend`
2. Install dependencies: `pip install -r requirements.txt`
3. Configure your environment: `cp .env.example .env` and add your keys.
4. Start the server: `uvicorn main:app --reload`

### Frontend Setup

1. Navigate to the frontend directory: `cd frontend`
2. Install dependencies: `npm install`
3. Launch the development server: `npm run dev`

Once both are running, open `http://localhost:5173` in your browser to start your analysis.

---

## Environment Configuration

Your `.env` file should include the following variables:

```env
RIOT_API_KEY=your_riot_api_key
GROQ_API_KEY=your_groq_api_key
RIOT_REGION=na1
RIOT_ROUTING=americas
```

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `GET` | `/summoner/{name}/{tag}` | Resolves a Riot ID to a PUUID. |
| `GET` | `/analyze/{puuid}` | Performs full match analysis and generates AI coaching. |
| `GET` | `/history/{puuid}` | Retrieves paginated match history from the local cache. |
| `GET` | `/match/{id}/details` | Fetches a detailed 10-player scoreboard for a specific match. |
| `POST` | `/ask` | Sends a follow-up question to the AI coach. |

---

## How It Works

When you request an analysis, Rift IQ triggers a complex data pipeline:

1. **Data Ingestion**: The backend fetches your most recent ranked matches in parallel using asynchronous HTTP requests.
2. **Feature Engineering**: Raw match data is processed into lobby-relative metrics, comparing your stats to the averages of the other players in the game.
3. **ML Inference**: The XGBoost model analyzes the game state to calculate win probability and performance scores.
4. **AI Synthesis**: A structured prompt containing your performance deltas is sent to LLaMA 3.3 70B, which generates a natural language coaching narrative.
5. **Persistence**: Results are cached in SQLite to ensure fast subsequent loads and to power the LP trend visualizations.
