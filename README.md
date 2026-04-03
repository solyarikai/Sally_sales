# LeadGen Automation

A lead generation automation platform for enriching, managing, and exporting leads with AI-powered features.

## Features

- **Multi-tenant Architecture**: Organize leads by companies and environments
- **Data Import**: CSV files and Google Sheets support
- **AI Enrichment**: Use OpenAI to enrich lead data with custom prompts
- **Deduplication**: Smart matching to prevent duplicate leads
- **Prospect Management**: Track lead status, tags, notes, and activities
- **Export**: CSV export and clipboard copy for easy integration
- **Integrations**: Instantly.ai support for email campaigns

## Tech Stack

### Backend
- **FastAPI** - Modern async Python web framework
- **SQLAlchemy** - Async ORM with PostgreSQL/SQLite support
- **OpenAI API** - AI enrichment capabilities
- **Alembic** - Database migrations

### Frontend
- **React 19** - UI library
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **Zustand** - State management
- **AG Grid** - Data tables

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL 16+ (or SQLite for development)
- Docker (optional, for PostgreSQL)

### 1. Database Setup

**Option A: Using Docker (recommended)**

```bash
docker-compose up -d
```

**Option B: Manual PostgreSQL**

Create a database named `leadgen` with user `leadgen`.

**Option C: SQLite (development only)**

Update `DATABASE_URL` in `.env` to use SQLite.

### 2. Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env and add your OpenAI API key

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The app will be available at http://localhost:5173

## Configuration

### Environment Variables

Copy `backend/.env.example` to `backend/.env` and configure:

```env
# Required
DATABASE_URL=postgresql+asyncpg://leadgen:leadgen_secret@localhost:5432/leadgen
OPENAI_API_KEY=sk-your-openai-api-key

# Optional
DEFAULT_OPENAI_MODEL=gpt-4o-mini
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
INSTANTLY_API_KEY=your-instantly-api-key
```

## API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
LeadGen Automation/
├── backend/
│   ├── alembic/           # Database migrations
│   ├── app/
│   │   ├── api/           # API endpoints
│   │   ├── core/          # Configuration
│   │   ├── db/            # Database setup
│   │   ├── models/        # SQLAlchemy models
│   │   ├── schemas/       # Pydantic schemas
│   │   ├── services/      # Business logic
│   │   └── main.py        # FastAPI app
│   ├── tests/             # Test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── api/           # API client
│   │   ├── components/    # React components
│   │   ├── hooks/         # Custom hooks
│   │   ├── pages/         # Page components
│   │   ├── store/         # Zustand store
│   │   └── types/         # TypeScript types
│   └── package.json
└── docker-compose.yml
```

## Running Tests

```bash
cd backend

# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test file
pytest tests/test_api/test_companies.py
```

## Development

### Database Migrations

```bash
# Create a new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1
```

### Code Style

Backend uses standard Python conventions. Frontend uses ESLint.

```bash
# Frontend linting
cd frontend && npm run lint
```

## License

Private - All rights reserved.
