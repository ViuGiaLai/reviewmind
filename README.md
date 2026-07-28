# ReviewMind

ReviewMind is a document-review MVP built around a reusable Python engine. The FastAPI layer only adapts HTTP requests to the engine; the review domain has no dependency on FastAPI.

## What is implemented

- Markdown/text parsing into a normalized `DocumentModel`
- Config-driven Academic, Business, and SOP profiles
- Extensible knowledge packs (an IEEE starter pack is included)
- Ordered syntax, semantic, cross-reference, and AI-extension rule stages
- Issues with evidence, confidence, recommendations, permission-aware autofix flags, score and Markdown report
- API endpoint and a React/Vite starter interface

## Run locally

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

The frontend expects the API at `http://localhost:8000` (override with `VITE_API_URL`).

## Design boundary

`backend/app/review` is the portable domain engine. It can be packaged, invoked by a CLI, or used from ResearchMind without importing `app.api`.
