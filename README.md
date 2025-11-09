# nerdboard - AI Operations Intelligence Platform

**48-Hour AI Product Sprint**: Predictive capacity planning for education marketplaces

---

## Quick Start (Docker Compose - Recommended)

### Prerequisites
- Docker Desktop installed
- Git

### One-Command Setup

```bash
# Clone and start entire stack
git clone https://github.com/example/nerdboard.git
cd nerdboard
docker-compose up -d
```

That's it! The complete stack is now running:

- **Frontend**: http://localhost:5173 (React dashboard)
- **Backend API**: http://localhost:8000 (FastAPI)
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **PostgreSQL**: localhost:5432
- **Redis**: localhost:6379

### Useful Commands

```bash
# View logs
docker-compose logs -f backend
docker-compose logs -f frontend

# Stop stack
docker-compose down

# Rebuild after code changes
docker-compose up -d --build

# Run database migrations
docker-compose exec backend alembic upgrade head

# Seed demo data
docker-compose exec backend python scripts/seed_demo_data.py

# Access Redis CLI
docker-compose exec redis redis-cli

# Access PostgreSQL
docker-compose exec postgres psql -U postgres -d nerdboard
```

---

## Manual Setup (Without Docker)

### Prerequisites
- Node.js 20+
- Python 3.11+
- PostgreSQL 18
- Redis 7.x

### Backend Setup

```bash
cd nerdboard-backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your database and Redis URLs

# Run migrations
alembic upgrade head

# Seed demo data
python scripts/seed_demo_data.py

# Start backend
uvicorn app.main:app --reload
```

### Frontend Setup

```bash
cd nerdboard-frontend
npm install

# Create .env file
cp .env.example .env
# Edit .env with API URL (default: http://localhost:8000/api/v1)

# Start frontend
npm run dev
```

---

## Project Structure

```
nerdboard/
├── nerdboard-frontend/       # React + TypeScript dashboard
├── nerdboard-backend/        # Python FastAPI + ML pipeline
├── docs/                     # PRD, epics, architecture
│   ├── PRD.md
│   ├── epics.md
│   └── architecture.md
├── docker-compose.yml        # Local development stack
└── README.md                 # This file
```

---

## Architecture Overview

**Three-Tier Architecture:**

1. **Frontend**: Vite + React 18 + TypeScript
   - Recharts for visualization
   - Zustand for state management
   - Responsive dashboard with explainability panels

2. **Backend API**: Python FastAPI
   - RESTful API with automatic OpenAPI docs
   - SQLAlchemy async ORM
   - Redis caching for performance

3. **ML Pipeline**: scikit-learn + SHAP
   - RandomForest/GradientBoosting for capacity predictions
   - SHAP TreeExplainer for transparent explanations
   - Hourly prediction scheduler

**Data Stack:**
- PostgreSQL 18 (relational data)
- Redis 7.x (caching: 30s-10min TTL)

**Deployment:**
- Frontend: Vercel (zero-config)
- Backend: Railway (with managed PostgreSQL + Redis)
- Alternative: AWS Lambda + RDS + ElastiCache

---

## Key Features

### 1. Explainable AI Predictions
- Capacity shortage predictions (2-8 week horizons)
- SHAP-powered explanations showing WHY predictions were made
- Confidence scoring for trustworthy alerts

### 2. Operations Dashboard
- Real-time capacity status by subject
- Alert feed with urgency indicators (green/yellow/red)
- Click any prediction to see detailed reasoning
- Metrics: customer health, session velocity, churn risk

### 3. Mock Data Simulation
- 50+ simulated data streams
- Historical patterns (12 months)
- Real-time stream updates for demo

---

## Development Workflow

### Sprint Planning (from epics.md)

**Phase 1 - Foundation (Hours 1-12):**
- Story 1.1: Database schema & setup
- Story 1.2: Historical data generator
- Story 1.3: Real-time simulator

**Phase 2 - Intelligence (Hours 12-24):**
- Story 2.1-2.7: ML pipeline with SHAP explainability
- Story 3.1-3.6: API endpoints and integration

**Phase 3 - UI (Hours 24-36):**
- Story 4.1-4.9: Dashboard components and interactions

**Phase 4 - Launch (Hours 36-48):**
- Story 5.1-5.5: Deployment and demo preparation

### Testing

```bash
# Backend tests
cd nerdboard-backend
pytest tests/

# Frontend tests
cd nerdboard-frontend
npm test

# Integration tests (with Docker Compose running)
npm run test:e2e
```

---

## API Examples

### Get Dashboard Overview
```bash
curl http://localhost:8000/api/v1/dashboard/overview
```

### Get Predictions
```bash
curl http://localhost:8000/api/v1/predictions?subject=Physics&urgency=critical
```

### Get Prediction Explanation
```bash
curl http://localhost:8000/api/v1/predictions/{id}/explanation
```

Full API documentation: http://localhost:8000/docs

---

## Environment Variables

### Backend (.env)
```bash
DATABASE_URL=postgresql://postgres:dev_password@localhost:5432/nerdboard
REDIS_URL=redis://localhost:6379/0
DEMO_TOKEN=nerdboard_demo_2025
ENV=development
```

### Frontend (.env)
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_ENV=development
```

---

## Documentation

- **[PRD](docs/PRD.md)** - Product Requirements Document
- **[Epics](docs/epics.md)** - 5 epics with 35 bite-sized stories
- **[Architecture](docs/architecture.md)** - Complete technical architecture

---

## Local Development Benefits

✅ **100% Local** - Zero cloud dependencies until deployment
✅ **Production Parity** - Same PostgreSQL 18 + Redis 7 as production
✅ **One Command** - `docker-compose up -d` starts entire stack
✅ **Isolated** - No conflicts with other local projects
✅ **Fast Iteration** - Hot reload for backend and frontend
✅ **Easy Testing** - Test caching, migrations, full integration locally

---

## Deployment

### Railway (Recommended)

1. Connect GitHub repo to Railway
2. Add PostgreSQL + Redis plugins (auto-configured)
3. Deploy backend service (auto-detects Python)
4. Deploy frontend to Vercel (auto-detects Vite)

### AWS (Alternative)

- Frontend: S3 + CloudFront or Amplify
- Backend: Lambda + API Gateway or ECS
- Database: RDS PostgreSQL 18
- Cache: ElastiCache Redis 7 or Upstash (serverless)

---

## Contributing

This is a 48-hour sprint project built with AI-assisted development.

**AI Tools Used:**
- Claude Code for architecture and implementation
- GitHub Copilot for code generation
- Cursor for rapid iteration

See [docs/PRD.md](docs/PRD.md) for full AI development documentation.

---

## License

MIT License - See LICENSE file

---

**Built for Nerdy Case 5: 48-Hour AI Product Sprint**
Demonstrating explainable AI for operational intelligence in <48 hours.
