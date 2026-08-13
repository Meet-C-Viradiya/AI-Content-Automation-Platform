# 🤖 AI Content Automation Platform

An AI-powered business content automation system that automatically researches any topic, creates a structured content plan, generates professional article sections using parallel AI workers, and combines them into a final article — all accessible through a REST API and real-time dashboard.

## 🎯 What It Does

1. User enters a topic (e.g. "AI Automation for Small Businesses")
2. **AI Router** analyzes the topic and decides if web research is needed
3. **Tavily Web Research** searches the internet for current information
4. **AI Content Planner** creates a structured plan with sections, goals, and word targets
5. **Parallel AI Workers** write each section simultaneously using Gemini AI
6. **Content Reducer** sorts and combines all sections into one final article
7. Results are saved to a database and displayed on the dashboard
8. Users can download the article as **Markdown** or **PDF**

## 🏗️ Architecture

```
POST /api/jobs (topic)
       │
       ▼
   Create DB Job
       │
       ▼
   ┌─────────┐
   │  Router  │ ← Gemini AI (decides research mode)
   └────┬────┘
        ▼
   ┌──────────┐
   │ Research  │ ← Tavily API (web search)
   └────┬─────┘
        ▼
  ┌─────────────┐
  │ Orchestrator │ ← Gemini AI (content plan)
  └──────┬──────┘
         ▼
   ┌─────┼─────┐
   ▼     ▼     ▼
  W1    W2    W3   ← Parallel AI Workers (Gemini)
   ▼     ▼     ▼
  W4    W5
   │     │
   └──┬──┘
      ▼
  ┌─────────┐
  │ Reducer  │ ← Sort + Combine
  └────┬────┘
       ▼
   Save to DB
       │
       ▼
   Dashboard
```

## 🛠️ Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Workflow | LangGraph (StateGraph with parallel fan-out) |
| AI Provider | Google Gemini 3.5 Flash (via LangChain) |
| Web Research | Tavily API |
| REST API | FastAPI |
| Database | SQLite + SQLAlchemy |
| Dashboard | Streamlit |
| Language | Python 3.12 |

## 📂 Project Structure

```
ai-content-automation/
├── app/
│   ├── api/
│   │   └── routes.py          # REST API endpoints
│   ├── database/
│   │   ├── database.py        # SQLAlchemy setup
│   │   └── models.py          # Job, Log, Content models
│   ├── services/
│   │   └── tavily_service.py  # Tavily web search
│   ├── workflow/
│   │   ├── graph.py           # LangGraph workflow
│   │   ├── nodes.py           # Router, Planner, Worker, Reducer
│   │   ├── runner.py          # Background job runner
│   │   └── state.py           # Workflow state schema
│   └── main.py                # FastAPI app entry
├── dashboard/
│   └── dashboard.py           # Streamlit dashboard
├── data/
│   └── automation.db          # SQLite database (auto-created)
├── tests/
│   ├── test_graph.py          # Full workflow test
│   ├── test_job.py            # Database test
│   ├── test_reducer.py        # Reducer test
│   ├── test_worker.py         # Worker test
│   └── test_workflow.py       # Node-by-node test
├── .env                       # API keys (not in repo)
├── .gitignore
├── README.md
├── requirements.txt
└── run.py                     # Single command launcher
```

## 🚀 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/ai-content-automation.git
cd ai-content-automation
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

Create a `.env` file in the project root:

```
TAVILY_API_KEY=your-tavily-api-key
GOOGLE_API_KEY=your-gemini-api-key
```

- Get Tavily key: https://tavily.com
- Get Gemini key: https://aistudio.google.com/apikey (free tier available)

### 4. Run the Platform

**Single command (starts both API + Dashboard):**

```bash
python run.py
```

**Or start separately:**

```bash
# Terminal 1 — API
python -m uvicorn app.main:app --reload

# Terminal 2 — Dashboard
streamlit run dashboard/dashboard.py
```

### 5. Access

- **Dashboard:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs

## 📡 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/jobs` | Create a new automation job |
| `GET` | `/api/jobs` | List all jobs |
| `GET` | `/api/jobs/{id}` | Get job detail with logs and content |
| `DELETE` | `/api/jobs/{id}` | Delete a job |

### Example — Create a Job

```bash
curl -X POST http://localhost:8000/api/jobs \
  -H "Content-Type: application/json" \
  -d '{"topic": "AI Automation for Small Businesses"}'
```

Response:
```json
{
  "job_id": 1,
  "topic": "AI Automation for Small Businesses",
  "status": "pending",
  "message": "Automation job created successfully"
}
```

## ✅ Key Features

- **Multi-step AI Workflow** — Router → Research → Planner → Workers → Reducer
- **Parallel Content Generation** — Workers run concurrently, not sequentially
- **Real-time Web Research** — Tavily API integration for current information
- **Automatic Fallback** — Graceful handling when AI provider is unavailable
- **Background Processing** — Jobs run asynchronously via FastAPI BackgroundTasks
- **Live Dashboard** — Auto-refreshing progress tracking
- **Export Options** — Download as Markdown or PDF
- **Job Management** — Create, view, and delete automation jobs
- **Workflow Logging** — Every step logged with timestamps

## 🧪 Running Tests

```bash
# Test full workflow end-to-end
python tests/test_graph.py

# Test individual components
python tests/test_workflow.py
python tests/test_worker.py
python tests/test_reducer.py
python tests/test_job.py
```

## 📋 Requirements Mapping

| Requirement | Implementation |
|-------------|---------------|
| Custom AI Automation Workflow | LangGraph: Router → Research → Planner → Workers → Reducer |
| Third-Party API Integration | Tavily REST API for web research |
| Custom Dashboard | Streamlit dashboard with live status, progress, and export |
| Self-Developed Project | AI content automation for business use |
| GitHub / Portfolio | This repository |
| **Bonus:** AI Agent | LangGraph workflow with parallel workers |
| **Bonus:** Gemini Integration | Google Gemini 3.5 Flash via LangChain |
| **Bonus:** AI Dashboard | Real-time job monitoring and content display |