# AkoweAI

WhatsApp-first cooperative management system.

## Structure

```
/
├── backend/        # FastAPI application (Python)
├── frontend/       # Next.js 14 dashboard (TypeScript)
└── README.md
```

## Services

Both services are deployed independently on Railway from the same repository.

| Service  | Root Directory | Start Command                                      |
| -------- | -------------- | -------------------------------------------------- |
| Backend  | `/backend`     | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Frontend | `/frontend`    | Auto-detected by Railway (Next.js)                 |

## Local Setup

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env      # fill in your values
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local  # fill in your values
npm run dev
```

## Environment Variables

See `/backend/.env.example` and `/frontend/.env.example` for all required variables.
