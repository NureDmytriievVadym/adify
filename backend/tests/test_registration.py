import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adify_api.accounts.models import Account, AccountBan, AccountStatus
from adify_api.core.security import verify_password

pytestmark = pytest.mark.anyio

URL = "/api/v1/accounts"


def payload(**overrides: object) -> dict[str, object]:
    return {
        "display_name": "Olena Koval",
        "email": "olena@example.com",
        "phone": "+380671234567",
        "role": "customer",
        "password": "secret123",
    } | overrides


def error_types(response) -> dict[str, str]:
    return {error["loc"][-1]: error["type"] for error in response.json()["detail"]}


@pytest.mark.parametrize("role", ["customer", "provider"])
async def test_registers_account_with_one_role(client: AsyncClient, sessionmaker, role: str):
    response = await client.post(URL, json=payload(role=role))

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == role
    assert body["status"] == "active"
    assert body["email_verified"] is False
    assert body["phone_verified"] is False
    assert "password" not in body and "password_hash" not in body

    async with sessionmaker() as session:
        account = await session.scalar(select(Account))
    assert account.password_hash.startswith("$2b$")
    assert verify_password("secret123", account.password_hash)


async def test_normalizes_email_and_phone(client: AsyncClient):
    response = await client.post(
        URL, json=payload(email="Olena@Example.COM", phone="+380 (67) 123-45-67")
    )

    assert response.status_code == 201
    assert response.json()["email"] == "olena@example.com"
    assert response.json()["phone"] == "+380671234567"


@pytest.mark.parametrize("phone", ["+48123456789", "0671234567", "+38067123456", "+3806712345678"])
async def test_rejects_non_ukrainian_phone(client: AsyncClient, phone: str):
    response = await client.post(URL, json=payload(phone=phone))

    assert response.status_code == 422
    assert error_types(response) == {"phone": "phone_not_ukrainian"}


@pytest.mark.parametrize("password", ["short1a", "onlyletters", "12345678", ""])
async def test_rejects_password_outside_policy(client: AsyncClient, password: str):
    response = await client.post(URL, json=payload(password=password))

    assert response.status_code == 422
    assert error_types(response) == {"password": "password_policy"}


async def test_rejects_password_bcrypt_cannot_hash(client: AsyncClient):
    response = await client.post(URL, json=payload(password="a1" * 37))

    assert response.status_code == 422
    assert error_types(response) == {"password": "password_too_long"}


@pytest.mark.parametrize(
    ("body", "field", "type_"),
    [
        (payload(role=["customer", "provider"]), "role", "role_not_single"),
        (payload(role="moderator"), "role", "literal_error"),
        (payload(role="administrator"), "role", "literal_error"),
        (payload(roles=["customer", "provider"]), "roles", "extra_forbidden"),
    ],
)
async def test_rejects_anything_but_one_marketplace_role(
    client: AsyncClient, body: dict[str, object], field: str, type_: str
):
    response = await client.post(URL, json=body)

    assert response.status_code == 422
    assert error_types(response) == {field: type_}


async def test_rejects_missing_fields(client: AsyncClient):
    response = await client.post(URL, json={})

    assert response.status_code == 422
    assert set(error_types(response)) == {"display_name", "email", "phone", "role", "password"}


async def ban(sessionmaker: async_sessionmaker[AsyncSession], email: str, phone: str) -> None:
    async with sessionmaker() as session:
        account = Account(
            display_name="Banned",
            email=email,
            phone=phone,
            password_hash="x",
            role="provider",
            status=AccountStatus.BANNED,
        )
        session.add(account)
        await session.flush()
        session.add(AccountBan(account_id=account.id, email=email, phone=phone))
        await session.commit()


@pytest.mark.parametrize(
    ("overrides", "expected"),
    [
        ({"email": "banned@example.com"}, {"email": "email_banned"}),
        ({"phone": "+380509999999"}, {"phone": "phone_banned"}),
        (
            {"email": "banned@example.com", "phone": "+380509999999"},
            {"email": "email_banned", "phone": "phone_banned"},
        ),
    ],
)
async def test_rejects_contacts_of_banned_account(
    client: AsyncClient, sessionmaker, overrides: dict[str, str], expected: dict[str, str]
):
    await ban(sessionmaker, "banned@example.com", "+380509999999")

    response = await client.post(URL, json=payload(**overrides))

    assert response.status_code == 403
    assert error_types(response) == expected


async def test_ban_outlives_contact_change(client: AsyncClient, sessionmaker):
    await ban(sessionmaker, "banned@example.com", "+380509999999")
    async with sessionmaker() as session:
        account = await session.scalar(select(Account))
        account.email = "changed@example.com"
        await session.commit()

    response = await client.post(URL, json=payload(email="banned@example.com"))

    assert response.status_code == 403


async def test_rejects_already_registered_contacts(client: AsyncClient):
    assert (await client.post(URL, json=payload())).status_code == 201

    response = await client.post(URL, json=payload(email="OLENA@example.com"))

    assert response.status_code == 409
    assert error_types(response) == {"email": "email_taken", "phone": "phone_taken"}


async def test_documents_registration_contract(client: AsyncClient):
    schema = (await client.get("/openapi.json")).json()
    operation = schema["paths"][URL]["post"]

    assert {"201", "403", "409", "422"} <= set(operation["responses"])
