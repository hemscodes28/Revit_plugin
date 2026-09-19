# RevitAI — AI-Powered Revit Assistant

RevitAI is a production-grade, AI-powered BIM assistant integrated directly into Autodesk Revit 2024. It seamlessly bridges natural language conversations with live Revit model operations, offering context-aware search, automatic active project synchronization, view opening, element selection, and intelligent project-isolated query execution.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              Autodesk Revit 2024.3                      │
│  - Active Document Listener (DocumentChanged/ViewActivated) │
│  - HttpListener REST API Endpoint (Port 8001)           │
│  - ExternalEvent Handler (UIDocument Operations)         │
└────────────────────────────┬────────────────────────────┘
                             │ HTTP / Local REST
                             ▼
┌─────────────────────────────────────────────────────────┐
│                 Electron Desktop App                    │
│  - React 18 + TypeScript + Tailwind CSS                 │
│  - Real-time Active Project Status Bar                   │
│  - Chatbot Interface & Quick Action Cards               │
└────────────────────────────┬────────────────────────────┘
                             │ REST API (HTTP Port 8000)
                             ▼
┌─────────────────────────────────────────────────────────┐
│                   FastAPI Backend                       │
│  - Intent Classifier (Gemini 2.5/3.6 Flash + Deterministic)│
│  - Semantic Search Engine (MiniLM Embeddings + pgvector)│
│  - Project Sync & Invalidation Manager                  │
│  - Revit Element Action Processor                       │
└────────────────────────────┬────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────┐
│             PostgreSQL + pgvector Database              │
│  - `revit_projects` (Isolated project metadata)          │
│  - `revit_views` (Views, view types, level mappings)     │
│  - `revit_elements` (Categories, parameters, embeddings) │
└─────────────────────────────────────────────────────────┘
```

---

## Features

- **Automatic Active Project Detection**: Automatically senses when you switch active projects in Revit (e.g. `Project A` $\rightarrow$ `Project B` $\rightarrow$ `Project A`), invalidating old search contexts and syncing the active document seamlessly.
- **Hybrid Natural Language Intent Engine**: Utilizes Google Gemini for conversational intent classification with a robust, zero-latency deterministic fallback parser.
- **Project Isolation**: Guarantees that search queries, level filtering, and view results are strictly isolated to the active Revit project.
- **Safe Element Actions**: Supports `OPEN`, `SELECT`, `HIGHLIGHT`, and `ZOOM` actions on Revit elements and views with mandatory `project_id` cross-verification before execution.
- **Lazy-Loaded Neural Embeddings**: SentenceTransformers embedding model is lazy-loaded on demand to optimize RAM and eliminate Windows OS paging errors (`os error 1455`).

---

## Prerequisites & Requirements

- **Operating System**: Windows 10/11 64-bit
- **Autodesk Revit**: Revit 2024.3
- **Python**: Python 3.10 to 3.14 (Virtual environment required)
- **Node.js**: Node.js v18.0.0 or higher (npm v9+)
- **Database**: PostgreSQL 15+ with `pgvector` extension enabled

---

## Installation & Setup

### 1. Database Setup
Ensure PostgreSQL is running and `pgvector` is installed:
```sql
CREATE DATABASE revitai;
\c revitai;
CREATE EXTENSION IF NOT EXISTS vector;
```

### 2. Backend Setup
1. Clone the repository and navigate to the backend:
   ```bash
   cd RevitAI
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install Python dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
4. Configure `.env`:
   ```ini
   GEMINI_API_KEY=your_gemini_api_key_here
   REVITAI_DATABASE_URL=postgresql://postgres:your_password@localhost:5432/revitai
   ```
5. Run database migrations:
   ```bash
   python -m backend.database
   ```
6. Start FastAPI server:
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```

### 3. C# Revit Plugin Installation
1. Open `RevitPlugin/RevitPlugin.sln` in Visual Studio 2022 or build via CLI:
   ```bash
   dotnet build RevitPlugin/RevitPlugin.csproj -c Release
   ```
2. Copy compiled `.dll` and `.addin` file into Revit Addins directory:
   `C:\Users\<User>\AppData\Roaming\Autodesk\Revit\Addins\2024\`

### 4. Electron Desktop App Setup
1. Install Node modules:
   ```bash
   npm install
   ```
2. Start development mode:
   ```bash
   npm run dev
   ```

---

## Test Execution & Verification

Run the master test suite (covering all 20 production acceptance tests):
```bash
.venv\Scripts\python.exe -m unittest backend/test_production_master.py
```

Run all backend unit tests across the entire codebase:
```bash
.venv\Scripts\python.exe -m unittest discover -s backend -p "test_*.py"
```

---

## Production Building

To compile the production desktop application:
```bash
npm run build
```
Output artifacts will be generated in `out/main`, `out/preload`, and `out/renderer`.

---

## Revit Element Action Safety Protocol

RevitAI enforces strict safety checks prior to executing element operations:
1. **Active Project Verification**: Checks if `element.project_id == active_project.project_id`. If project IDs mismatch, the command is aborted with an explanatory message.
2. **ExternalEvent Threading**: All UI interactions (`uidoc.Selection.SetElementIds`, `uidoc.ShowElements`) execute safely inside Revit's main thread via `IExternalEventHandler`.
