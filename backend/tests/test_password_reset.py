import re
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from conftest import verify_contacts
from httpx import AsyncClient
from sqlalchemy import select, update

from adify_api.auth.models import PasswordResetToken, RefreshToken
from adify_api.core.config import get_settings

pytestmark = pytest.mark.anyio

REQUEST = "/api/v1/auth/password-reset"
CONFIRM = "/api/v1/auth/password-reset/confirm"
SIGN_IN = "/api/v1/auth/sign-in"
EMAIL = "olena@example.com"
OLD, NEW = "secret123", "fresh456pass"


@pytest.fixture(autouse=True)
async def account(client: AsyncClient, sessionmaker, outbox: list[EmailMessage]) -> None:
    body = {
        "display_name": "Olena Koval",
        "email": EMAIL,
        "phone": "+380671234567",
        "role": "provider",
        "password": OLD,
    }
    assert (await client.post("/api/v1/accounts", json=body)).status_code == 201
    await verify_contacts(sessionmaker, EMAIL)
    outbox.clear()  # drop the registration verification email


def reset_token(outbox: list[EmailMessage]) -> str:
    message = outbox[-1]
    assert message["To"] == EMAIL
    assert message["Subject"] == "Reset your Adify password"
    link = re.search(r"http://localhost:5173/reset-password\?token=(\S+)", message.get_content())
    return link.group(1)


async def sign_in(client: AsyncClient, password: str) -> int:
    return (await client.post(SIGN_IN, json={"email": EMAIL, "password": password})).status_code


def error_type(response) -> str:
    return response.json()["detail"][0]["type"]


async def test_reset_replaces_password_and_link_works_once(client, outbox):
    assert (await client.post(REQUEST, json={"email": "Olena@Example.com"})).status_code == 202
    token = reset_token(outbox)

    assert (await client.post(CONFIRM, json={"token": token, "password": NEW})).status_code == 204
    assert await sign_in(client, NEW) == 200
    assert await sign_in(client, OLD) == 401

    again = await client.post(CONFIRM, json={"token": token, "password": "other789pass"})
    assert again.status_code == 400
    assert error_type(again) == "reset_link_invalid"
    assert again.json()["detail"][0]["msg"].startswith("This link has expired or has already")


async def test_reset_signs_out_every_session(client, outbox, sessionmaker):
    signed_in = await client.post(SIGN_IN, json={"email": EMAIL, "password": OLD})
    refresh = signed_in.json()["refresh_token"] or signed_in.cookies["adify_refresh"]

    await client.post(REQUEST, json={"email": EMAIL})
    await client.post(CONFIRM, json={"token": reset_token(outbox), "password": NEW})

    async with sessionmaker() as session:
        tokens = (await session.scalars(select(RefreshToken))).all()
    assert tokens and all(token.revoked_at is not None for token in tokens)
    response = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert response.status_code == 401


@pytest.mark.parametrize("email", ["nobody@example.com", "not-an-account@example.org"])
async def test_unknown_email_gets_the_same_answer_and_no_mail(client, outbox, email):
    response = await client.post(REQUEST, json={"email": email})

    assert response.status_code == 202
    assert outbox == []


async def test_unverified_email_gets_no_link(client, outbox):
    body = {
        "display_name": "Taras",
        "email": "taras@example.com",
        "phone": "+380671234568",
        "role": "customer",
        "password": OLD,
    }
    await client.post("/api/v1/accounts", json=body)
    outbox.clear()

    response = await client.post(REQUEST, json={"email": "taras@example.com"})

    assert response.status_code == 202
    assert outbox == []


async def test_expired_link_is_refused(client, outbox, sessionmaker):
    await client.post(REQUEST, json={"email": EMAIL})
    token = reset_token(outbox)
    async with sessionmaker() as session:
        await session.execute(
            update(PasswordResetToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()

    response = await client.post(CONFIRM, json={"token": token, "password": NEW})

    assert response.status_code == 400
    assert error_type(response) == "reset_link_invalid"
    assert await sign_in(client, OLD) == 200


async def test_unknown_token_is_refused(client):
    response = await client.post(CONFIRM, json={"token": "made-up", "password": NEW})

    assert response.status_code == 400
    assert error_type(response) == "reset_link_invalid"


async def test_repeat_request_within_wait_sends_nothing(client, outbox):
    await client.post(REQUEST, json={"email": EMAIL})
    response = await client.post(REQUEST, json={"email": EMAIL})

    assert response.status_code == 202
    assert len(outbox) == 1


async def test_new_link_replaces_the_previous_one(client, outbox, sessionmaker):
    await client.post(REQUEST, json={"email": EMAIL})
    first = reset_token(outbox)
    wait = timedelta(seconds=get_settings().password_reset_resend_seconds + 1)
    async with sessionmaker() as session:
        await session.execute(
            update(PasswordResetToken).values(created_at=datetime.now(UTC) - wait)
        )
        await session.commit()
    await client.post(REQUEST, json={"email": EMAIL})
    second = reset_token(outbox)

    stale = await client.post(CONFIRM, json={"token": first, "password": NEW})
    assert stale.status_code == 400
    fresh = await client.post(CONFIRM, json={"token": second, "password": NEW})
    assert fresh.status_code == 204


async def test_new_password_follows_the_registration_policy(client, outbox):
    await client.post(REQUEST, json={"email": EMAIL})
    token = reset_token(outbox)

    response = await client.post(CONFIRM, json={"token": token, "password": "short1"})

    assert response.status_code == 422
    assert error_type(response) == "password_policy"
    # A rejected password does not use up the link.
    ok = await client.post(CONFIRM, json={"token": token, "password": NEW})
    assert ok.status_code == 204


async def test_only_the_token_hash_is_stored(client, outbox, sessionmaker):
    await client.post(REQUEST, json={"email": EMAIL})
    token = reset_token(outbox)

    async with sessionmaker() as session:
        stored = await session.scalar(select(PasswordResetToken))
    assert stored.token_hash != token and len(stored.token_hash) == 64
