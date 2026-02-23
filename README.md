# MedConnect India

EMR + Patient Portal for India's Digital Health Ecosystem.

## Quick Start

```bash
# Clone and start
docker-compose up --build

# Access
# Frontend: http://localhost:3000
# Backend API docs: http://localhost:8000/docs
# Health check: http://localhost:8000/health
```

## Architecture

- **Backend**: FastAPI + SQLAlchemy + Alembic (Python 3.12)
- **Frontend**: Next.js 14 + Tailwind CSS + shadcn/ui
- **Database**: PostgreSQL 16 + pgvector
- **Cache**: Redis 7
- **Deployment**: Docker Compose

## Project Structure

```
medconnect/
├── backend/          # FastAPI backend
│   ├── app/          # Application code
│   ├── alembic/      # Database migrations
│   └── tests/        # API tests
├── frontend/         # Next.js frontend
│   └── src/          # Source code
├── nginx/            # Reverse proxy config
└── docker-compose.yml
```

## Development

### Backend (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

### Frontend (without Docker)

```bash
cd frontend
npm install
npm run dev
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/signup` | Register |
| POST | `/api/v1/auth/login` | Login |
| GET | `/api/v1/auth/me` | Current user |
| GET | `/api/v1/patients/timeline` | Patient health timeline |
| GET | `/api/v1/patients/records/:id` | Record detail |
| GET | `/api/v1/patients/prescriptions` | Patient prescriptions |
| GET | `/api/v1/doctors/patients` | Doctor's patient list |
| POST | `/api/v1/doctors/records` | Create medical record |
| POST | `/api/v1/doctors/prescriptions` | Create prescription |
| GET | `/health` | Health check |

Full API docs at `/docs` when running.
