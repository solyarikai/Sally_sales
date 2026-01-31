"""
Pytest configuration and fixtures for LeadGen Automation tests.

Provides:
- Async test support
- In-memory SQLite database for isolation
- Test client for API testing
- Factory fixtures for creating test data
"""

import pytest
import pytest_asyncio
import asyncio

# Configure pytest-asyncio
pytest_plugins = ('pytest_asyncio',)
from typing import AsyncGenerator, Generator
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.db import Base, get_session
from app.models import User, Company, Environment, Dataset, DataRow, Prospect, ReplyAutomation, ProcessedReply, ReplyCategory


# Test database URL - in-memory SQLite
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def engine():
    """Create a test database engine."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        future=True,
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create a test client with overridden database session."""
    
    async def override_get_session():
        yield db_session
    
    app.dependency_overrides[get_session] = override_get_session
    
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client
    
    app.dependency_overrides.clear()


# ============ Factory Fixtures ============

@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> User:
    """Create a test user."""
    user = User(
        name="Test User",
        email="test@example.com",
        is_active=True
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def test_environment(db_session: AsyncSession, test_user: User) -> Environment:
    """Create a test environment."""
    env = Environment(
        user_id=test_user.id,
        name="Test Environment",
        description="Test environment for testing",
        color="#3B82F6",
        is_active=True
    )
    db_session.add(env)
    await db_session.flush()
    await db_session.refresh(env)
    return env


@pytest_asyncio.fixture
async def test_company(db_session: AsyncSession, test_user: User, test_environment: Environment) -> Company:
    """Create a test company."""
    company = Company(
        user_id=test_user.id,
        environment_id=test_environment.id,
        name="Test Company",
        description="Test company for testing",
        website="https://testcompany.com",
        color="#3B82F6",
        is_active=True
    )
    db_session.add(company)
    await db_session.flush()
    await db_session.refresh(company)
    return company


@pytest_asyncio.fixture
async def test_dataset(db_session: AsyncSession, test_company: Company) -> Dataset:
    """Create a test dataset."""
    dataset = Dataset(
        company_id=test_company.id,
        name="Test Dataset",
        source_type="csv",
        original_filename="test.csv",
        columns=["email", "first_name", "last_name", "company"],
        row_count=3
    )
    db_session.add(dataset)
    await db_session.flush()
    await db_session.refresh(dataset)
    return dataset


@pytest_asyncio.fixture
async def test_data_rows(db_session: AsyncSession, test_dataset: Dataset) -> list[DataRow]:
    """Create test data rows."""
    rows = []
    test_data = [
        {"email": "john@example.com", "first_name": "John", "last_name": "Doe", "company": "Acme Inc"},
        {"email": "jane@example.com", "first_name": "Jane", "last_name": "Smith", "company": "Tech Corp"},
        {"email": "bob@example.com", "first_name": "Bob", "last_name": "Wilson", "company": "Startup LLC"},
    ]
    
    for i, data in enumerate(test_data):
        row = DataRow(
            dataset_id=test_dataset.id,
            row_index=i,
            data=data,
            enriched_data={}
        )
        db_session.add(row)
        rows.append(row)
    
    await db_session.flush()
    for row in rows:
        await db_session.refresh(row)
    
    return rows


@pytest_asyncio.fixture
async def test_prospect(db_session: AsyncSession, test_company: Company) -> Prospect:
    """Create a test prospect."""
    prospect = Prospect(
        company_id=test_company.id,
        email="prospect@example.com",
        first_name="Test",
        last_name="Prospect",
        company_name="Prospect Corp",
        job_title="CEO",
        custom_fields={"source": "test"},
        sources=[{"source": "test", "added_at": "2024-01-01"}],
        tags=["test", "demo"]
    )
    db_session.add(prospect)
    await db_session.flush()
    await db_session.refresh(prospect)
    return prospect


# ============ Helper Functions ============

def get_auth_headers(company_id: int) -> dict:
    """Get headers with company ID for authenticated requests."""
    return {"X-Company-ID": str(company_id)}
