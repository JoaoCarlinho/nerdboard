# Nerdboard Backend

AI-powered operations intelligence platform for education marketplace capacity planning.

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.9+
- PostgreSQL 18 (via Docker)
- Redis 7.x (via Docker)

### Setup

1. **Start the database and cache:**

```bash
docker-compose up -d postgres redis
```

2. **Install Python dependencies:**

```bash
pip install -r requirements.txt
```

3. **Configure environment variables:**

```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run database migrations:**

```bash
# Generate migration (if models changed)
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

5. **Verify setup:**

```bash
# Check tables were created
docker exec nerdboard-postgres psql -U postgres -d nerdboard -c "\dt"

# Check indexes
docker exec nerdboard-postgres psql -U postgres -d nerdboard -c "\di"
```

## Database Schema

The Nerdboard database consists of 7 core tables for capacity tracking, prediction, and simulation.

### Tables

#### 1. **enrollments** - Student enrollment tracking
- `id` (UUID, PK): Unique enrollment identifier
- `student_id` (UUID): Student reference
- `subject` (VARCHAR(100)): Subject name (Math, Science, etc.)
- `cohort_id` (VARCHAR(50)): Cohort identifier
- `start_date` (TIMESTAMPTZ): Enrollment start date
- `engagement_score` (FLOAT): Student engagement (0-1)
- `created_at`, `updated_at` (TIMESTAMPTZ): Audit timestamps

**Indexes:**
- `idx_enrollments_subject_date` on (subject, start_date)
- `idx_enrollments_student` on (student_id)

#### 2. **tutors** - Tutor resources and capacity
- `id` (UUID, PK): Unique tutor identifier
- `tutor_id` (VARCHAR(100), UNIQUE): Human-readable tutor ID
- `subjects` (TEXT[]): Array of subjects tutor teaches
- `weekly_capacity_hours` (INT): Hours available per week
- `utilization_rate` (FLOAT): Utilization percentage (0-1)
- `avg_response_time_hours` (FLOAT): Average response time
- `created_at`, `updated_at` (TIMESTAMPTZ): Audit timestamps

**Indexes:**
- `idx_tutors_subjects` (GIN) on (subjects) - enables fast array queries
- `idx_tutors_tutor_id` on (tutor_id)

#### 3. **sessions** - Tutoring sessions
- `id` (UUID, PK): Unique session identifier
- `session_id` (VARCHAR(100), UNIQUE): Human-readable session ID
- `subject` (VARCHAR(100)): Session subject
- `tutor_id` (UUID, FK → tutors.id, ON DELETE SET NULL): Assigned tutor
- `student_id` (UUID): Student reference
- `scheduled_time` (TIMESTAMPTZ): Session start time
- `duration_minutes` (INT): Session duration
- `created_at`, `updated_at` (TIMESTAMPTZ): Audit timestamps

**Indexes:**
- `idx_sessions_subject_time` on (subject, scheduled_time)
- `idx_sessions_tutor` on (tutor_id)
- `idx_sessions_student` on (student_id)

**Foreign Keys:**
- `tutor_id` references `tutors(id)` ON DELETE SET NULL

#### 4. **health_metrics** - Customer health tracking
- `id` (UUID, PK): Unique metric identifier
- `customer_id` (VARCHAR(100)): Customer reference
- `date` (TIMESTAMPTZ): Metric date
- `health_score` (FLOAT): Overall health score (0-100)
- `engagement_level` (INT): Engagement metric
- `support_ticket_count` (INT): Number of support tickets
- `session_completion_rate` (FLOAT): Session completion percentage (0-1)
- `created_at`, `updated_at` (TIMESTAMPTZ): Audit timestamps

**Indexes:**
- `idx_health_customer_date` on (customer_id, date DESC)

#### 5. **capacity_snapshots** - Daily capacity tracking
- `id` (UUID, PK): Unique snapshot identifier
- `subject` (VARCHAR(100)): Subject name
- `date` (TIMESTAMPTZ): Snapshot date
- `total_capacity_hours` (INT): Total available hours
- `used_capacity_hours` (INT): Hours used
- `available_tutors_count` (INT): Number of available tutors
- `utilization_rate` (FLOAT): Capacity utilization (0-1)
- `created_at`, `updated_at` (TIMESTAMPTZ): Audit timestamps

**Indexes:**
- `idx_capacity_subject_date` on (subject, date DESC)

#### 6. **data_quality_log** - Data quality monitoring
- `id` (UUID, PK): Unique log identifier
- `check_name` (VARCHAR(200)): Quality check name
- `status` (VARCHAR(50)): Check status (passed, failed, warning)
- `quality_score` (FLOAT): Quality score (0-5)
- `affected_records_count` (INT): Number of affected records
- `error_details` (TEXT): Error description
- `checked_at` (TIMESTAMPTZ): Check execution time
- `created_at`, `updated_at` (TIMESTAMPTZ): Audit timestamps

**Indexes:**
- `idx_quality_check_status` on (check_name, status)
- `idx_quality_checked_at` on (checked_at DESC)

#### 7. **simulation_state** - Global simulation control (single-row table)
- `id` (INT, PK, CHECK = 1): Always 1 (enforces single row)
- `current_date` (TIMESTAMPTZ): Simulation current date
- `speed_multiplier` (INT): Simulation speed multiplier
- `is_running` (BOOLEAN): Simulation running status
- `last_event` (VARCHAR(500)): Last simulation event
- `updated_at` (TIMESTAMPTZ): Last update timestamp

**Constraints:**
- `single_row_check`: Ensures only one row exists (id = 1)

## Migration Workflow

### Creating a New Migration

1. **Make changes to SQLAlchemy models** in `app/models/`

2. **Generate migration:**
```bash
alembic revision --autogenerate -m "Add new_field to tutors"
```

3. **Review the generated migration** in `alembic/versions/`

4. **Apply the migration:**
```bash
alembic upgrade head
```

### Reverting a Migration

```bash
# Downgrade one migration
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade <revision_id>

# Downgrade all migrations
alembic downgrade base
```

### Viewing Migration History

```bash
# Current revision
alembic current

# Migration history
alembic history

# Show SQL for migration (without applying)
alembic upgrade head --sql
```

## Environment Variables

Create a `.env` file in the project root with these variables:

```bash
# Database Configuration
DATABASE_URL=postgresql://postgres:dev_password@localhost:5432/nerdboard

# Redis Configuration
REDIS_URL=redis://localhost:6379/0

# Authentication (MVP - Demo Token)
DEMO_TOKEN=nerdboard_demo_2025

# Environment
ENV=development

# CORS Configuration
FRONTEND_URL=http://localhost:5173

# Optional: Logging Level
LOG_LEVEL=INFO
```

## Testing

### Run All Tests

```bash
DATABASE_URL="postgresql://postgres:dev_password@localhost:5432/nerdboard" \
pytest -v
```

### Run Integration Tests Only

```bash
DATABASE_URL="postgresql://postgres:dev_password@localhost:5432/nerdboard" \
pytest tests/integration/ -v
```

### Run Performance Tests Only

```bash
DATABASE_URL="postgresql://postgres:dev_password@localhost:5432/nerdboard" \
pytest tests/performance/ -v
```

## Architecture

### Connection Pooling

- **pool_size**: 20 connections kept alive
- **max_overflow**: 30 additional connections under load (50 total max)
- **pool_recycle**: 3600 seconds (connections recycled hourly)
- **pool_pre_ping**: Enabled (verifies connection health before use)

### Async SQLAlchemy

All database operations use SQLAlchemy 2.x async ORM with asyncpg driver:

```python
from app.database import AsyncSessionLocal

async def example_query():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Tutor).limit(10))
        return result.scalars().all()
```

### Redis Caching

Redis is configured with async client for caching dashboard data:

```python
from app.database import get_redis

async def get_cached_data(key: str):
    redis = get_redis()
    return await redis.get(key)
```

## Performance Targets

- **Dashboard queries**: <100ms (p95)
- **Concurrent streams**: 50+ without degradation (<5% latency increase)
- **Historical data generation**: <30 seconds for 12 months
- **Redis cache hit rate**: >90%

## Development

### Code Style

- Follow PEP 8
- Use type hints
- Document all public functions
- Keep functions focused and testable

### Database Schema Changes

1. Always create migrations for schema changes
2. Test migrations on local database first
3. Never modify existing migrations that have been deployed
4. Document breaking changes in migration commit messages

## Troubleshooting

### Local PostgreSQL Conflicts

If you get "role postgres does not exist" errors:

```bash
# Stop local PostgreSQL service
brew services stop postgresql@14

# Or run Docker containers on different port
# Edit docker-compose.yml and change ports
```

### Alembic Migration Issues

```bash
# Reset alembic_version table (DANGEROUS - only for development)
docker exec nerdboard-postgres psql -U postgres -d nerdboard -c "DROP TABLE alembic_version;"

# Re-run migrations
alembic upgrade head
```

### Connection Pool Exhaustion

If you see "QueuePool limit exceeded" errors:

1. Check for unclosed connections in application code
2. Ensure `async with AsyncSessionLocal()` is used (auto-closes)
3. Increase `pool_size` or `max_overflow` in `app/database.py` if needed
