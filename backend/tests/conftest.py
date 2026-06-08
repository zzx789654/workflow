import os
import uuid

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.api.v1.endpoints.auth as _auth_module
from app.db.session import Base, get_db
from app.main import app
from app.main import limiter as _main_limiter
from app.models.user import User, UserRole

TEST_DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://workflow:workflow_pass@localhost:5432/workflow_test",
)

# Disable rate limiting entirely in tests so no 429 is raised.
_auth_module.limiter.enabled = False
_main_limiter.enabled = False


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(TEST_DB_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.pop(get_db, None)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def admin_user(client: AsyncClient):
    email = f"admin_{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Admin", "password": "Admin1234"},
    )
    assert resp.status_code == 201

    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.execute(update(User).where(User.email == email).values(role=UserRole.admin))
    await engine.dispose()

    return type("AdminUser", (), {"email": email})()


@pytest_asyncio.fixture
async def admin_token(client: AsyncClient, admin_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": admin_user.email, "password": "Admin1234"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def member_user(client: AsyncClient):
    """A plain (non-admin) registered user."""
    email = f"member_{uuid.uuid4().hex[:8]}@test.com"
    resp = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Member", "password": "Member1234"},
    )
    assert resp.status_code == 201
    user_id = resp.json()["id"]
    return type("MemberUser", (), {"email": email, "id": user_id})()


@pytest_asyncio.fixture
async def member_token(client: AsyncClient, member_user):
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": member_user.email, "password": "Member1234"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest_asyncio.fixture
async def project_id(client: AsyncClient, admin_token: str):
    """Create a project owned by the admin user and return its id."""
    resp = await client.post(
        "/api/v1/projects/",
        json={"name": "Fixture Project", "color": "#123456"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest_asyncio.fixture
async def task_id(client: AsyncClient, admin_token: str, project_id: str):
    """Create a task in the fixture project and return its id."""
    resp = await client.post(
        f"/api/v1/projects/{project_id}/tasks/",
        json={"title": "Fixture Task"},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]
