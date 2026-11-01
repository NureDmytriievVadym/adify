from collections.abc import AsyncIterator
from email.message import EmailMessage

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from adify_api.accounts.models import Account
from adify_api.core import mail
from adify_api.core.db import Base, get_session
from adify_api.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def sessionmaker() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def client(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncClient]:
    async def session_override() -> AsyncIterator[AsyncSession]:
        async with sessionmaker() as session:
            yield session

    app = create_app()
    app.dependency_overrides[get_session] = session_override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


@pytest.fixture(autouse=True)
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """Captures every email and dev-outbox SMS instead of talking to an SMTP server."""
    messages: list[EmailMessage] = []
    monkeypatch.setattr(mail, "_send", messages.append)
    return messages


async def verify_contacts(sessionmaker: async_sessionmaker[AsyncSession], email: str) -> None:
    async with sessionmaker() as session:
        await session.execute(
            update(Account)
            .where(Account.email == email)
            .values(email_verified=True, phone_verified=True)
        )
        await session.commit()
