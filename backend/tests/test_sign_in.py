from datetime import UTC, datetime, timedelta

import jwt
import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from adify_api.accounts.models import Account, AccountStatus
from adify_api.auth.models import RefreshToken
from adify_api.core.config import get_settings

pytestmark = pytest.mark.anyio

SIGN_IN = "/api/v1/auth/sign-in"
REFRESH = "/api/v1/auth/refresh"
SIGN_OUT = "/api/v1/auth/sign-out"
ME = "/api/v1/accounts/me"
CREDENTIALS = {"email": "olena@example.com", "password": "secret123"}


@pytest.fixture(autouse=True)
async def account(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/accounts",
        json={
            "display_name": "Olena Koval",
            "email": "olena@example.com",
            "phone": "+380671234567",
            "role": "provider",
            "password": "secret123",
        },
    )
    assert response.status_code == 201


def error_type(response) -> str:
    return response.json()["detail"][0]["type"]


def bearer(response) -> dict[str, str]:
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


async def test_signs_in_and_opens_own_account(client: AsyncClient):
    response = await client.post(SIGN_IN, json=CREDENTIALS | {"email": "Olena@Example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 15 * 60
    assert body["refresh_token"] is None
    assert body["account"]["role"] == "provider"
    claims = jwt.decode(body["access_token"], get_settings().jwt_secret, algorithms=["HS256"])
    assert claims["sub"] == body["account"]["id"] and claims["role"] == "provider"

    cookie = response.headers["set-cookie"]
    assert cookie.startswith("adify_refresh=")
    assert "HttpOnly" in cookie and "Path=/api/v1/auth" in cookie and "SameSite=lax" in cookie

    me = await client.get(ME, headers=bearer(response))
    assert me.status_code == 200
    assert me.json()["email"] == "olena@example.com"


async def test_unverified_account_can_sign_in(client: AsyncClient):
    response = await client.post(SIGN_IN, json=CREDENTIALS)

    assert response.json()["account"]["email_verified"] is False
    assert response.status_code == 200


@pytest.mark.parametrize(
    "credentials",
    [
        CREDENTIALS | {"password": "secret124"},
        CREDENTIALS | {"password": ""},
        CREDENTIALS | {"email": "nobody@example.com"},
    ],
)
async def test_invalid_credentials_share_one_error(client: AsyncClient, credentials):
    response = await client.post(SIGN_IN, json=credentials)

    assert response.status_code == 401
    assert response.json() == {
        "detail": [
            {
                "loc": ["body"],
                "msg": "Incorrect email address or password.",
                "type": "invalid_credentials",
            }
        ]
    }
    assert "set-cookie" not in response.headers


async def test_rejects_malformed_email(client: AsyncClient):
    response = await client.post(SIGN_IN, json=CREDENTIALS | {"email": "olena"})

    assert response.status_code == 422


@pytest.mark.parametrize(
    ("status", "type_"),
    [(AccountStatus.SUSPENDED, "account_suspended"), (AccountStatus.BANNED, "account_banned")],
)
async def test_explains_suspension_and_ban_only_with_correct_password(
    client: AsyncClient, sessionmaker, status: AccountStatus, type_: str
):
    async with sessionmaker() as session:
        await session.execute(update(Account).values(status=status))
        await session.commit()

    wrong = await client.post(SIGN_IN, json=CREDENTIALS | {"password": "secret124"})
    right = await client.post(SIGN_IN, json=CREDENTIALS)

    assert (wrong.status_code, error_type(wrong)) == (401, "invalid_credentials")
    assert (right.status_code, error_type(right)) == (403, type_)


async def test_refresh_rotates_the_cookie_token(client: AsyncClient):
    await client.post(SIGN_IN, json=CREDENTIALS)
    old_token = client.cookies["adify_refresh"]

    refreshed = await client.post(REFRESH)

    assert refreshed.status_code == 200
    assert client.cookies["adify_refresh"] != old_token
    assert (await client.get(ME, headers=bearer(refreshed))).status_code == 200

    client.cookies.clear()
    client.cookies.set("adify_refresh", old_token)
    replay = await client.post(REFRESH)
    assert (replay.status_code, error_type(replay)) == (401, "invalid_refresh_token")


async def test_native_clients_receive_refresh_token_in_body(client: AsyncClient):
    signed_in = await client.post(SIGN_IN, json=CREDENTIALS | {"token_delivery": "body"})
    token = signed_in.json()["refresh_token"]

    assert token and "set-cookie" not in signed_in.headers
    refreshed = await client.post(REFRESH, json={"refresh_token": token, "token_delivery": "body"})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] not in (None, token)


async def test_refresh_rejects_expired_and_missing_tokens(client: AsyncClient, sessionmaker):
    assert error_type(await client.post(REFRESH)) == "invalid_refresh_token"

    await client.post(SIGN_IN, json=CREDENTIALS)
    async with sessionmaker() as session:
        await session.execute(
            update(RefreshToken).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()

    assert (await client.post(REFRESH)).status_code == 401


async def test_refresh_stops_for_banned_account(client: AsyncClient, sessionmaker):
    await client.post(SIGN_IN, json=CREDENTIALS)
    async with sessionmaker() as session:
        await session.execute(update(Account).values(status=AccountStatus.BANNED))
        await session.commit()

    response = await client.post(REFRESH)

    assert (response.status_code, error_type(response)) == (403, "account_banned")


async def test_sign_out_revokes_the_session(client: AsyncClient, sessionmaker):
    await client.post(SIGN_IN, json=CREDENTIALS)
    token = client.cookies["adify_refresh"]

    response = await client.post(SIGN_OUT)

    assert response.status_code == 204
    assert "adify_refresh" not in client.cookies
    async with sessionmaker() as session:
        assert (await session.scalar(select(RefreshToken))).revoked_at is not None
    client.cookies.set("adify_refresh", token)
    replay = await client.post(REFRESH)
    assert replay.status_code == 401


async def test_refresh_tokens_are_stored_hashed(client: AsyncClient, sessionmaker):
    await client.post(SIGN_IN, json=CREDENTIALS)

    async with sessionmaker() as session:
        stored = await session.scalar(select(RefreshToken))
    assert stored.token_hash != client.cookies["adify_refresh"]
    assert len(stored.token_hash) == 64


@pytest.mark.parametrize(
    ("headers", "type_"),
    [
        ({}, "not_authenticated"),
        ({"Authorization": "Bearer not-a-jwt"}, "invalid_access_token"),
    ],
)
async def test_me_requires_a_valid_access_token(client: AsyncClient, headers, type_):
    response = await client.get(ME, headers=headers)

    assert (response.status_code, error_type(response)) == (401, type_)
    assert response.headers["www-authenticate"] == "Bearer"


async def test_me_rejects_expired_and_forged_tokens(client: AsyncClient):
    signed_in = await client.post(SIGN_IN, json=CREDENTIALS)
    subject = signed_in.json()["account"]["id"]
    past = datetime.now(UTC) - timedelta(minutes=1)
    expired = jwt.encode({"sub": subject, "exp": past}, get_settings().jwt_secret)
    forged = jwt.encode(
        {"sub": subject, "exp": datetime.now(UTC) + timedelta(minutes=5)},
        "another-secret-of-sufficient-length",
    )

    for token in (expired, forged):
        response = await client.get(ME, headers={"Authorization": f"Bearer {token}"})
        assert response.status_code == 401
