import os
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.session import Base, get_db
from app.main import app
from app.models.user import User, UserRole

TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://workflow:workflow_pass@localhost:5432/workflow_test",
)

engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_user(db: AsyncSession):
    user = User(
        id=uuid.uuid4(),
        email="admin@test.com",
        display_name="Admin",
        hashed_password=hash_password("Admin1234"),
        role=UserRole.admin,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user):
    resp = await client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": "Admin1234"})
    return resp.json()["access_token"]
