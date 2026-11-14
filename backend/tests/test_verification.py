import re
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update

from adify_api.accounts.models import Account
from adify_api.core import mail
from adify_api.verification.models import VerificationCode

pytestmark = pytest.mark.anyio

EMAIL = "/api/v1/accounts/me/verification/email"
PHONE = "/api/v1/accounts/me/verification/phone"


async def sign_up(
    client: AsyncClient,
    role: str,
    email: str,
    phone: str,
    *,
    request_email_code: bool = True,
) -> dict[str, str]:
    body = {
        "display_name": f"Test {role}",
        "email": email,
        "phone": phone,
        "role": role,
        "password": "secret123",
    }
    assert (await client.post("/api/v1/accounts", json=body)).status_code == 201
    tokens = await client.post(
        "/api/v1/auth/sign-in", json={"email": email, "password": "secret123"}
    )
    headers = {"Authorization": f"Bearer {tokens.json()['access_token']}"}
    if request_email_code:
        response = await client.post(f"{EMAIL}/code", headers=headers)
        assert response.status_code == 202, response.text
    return headers


@pytest.fixture
async def customer(client: AsyncClient) -> dict[str, str]:
    return await sign_up(client, "customer", "customer@example.com", "+380671111111")


def last_code(outbox: list[EmailMessage]) -> str:
    return re.search(r"\b(\d{6})\b", outbox[-1].get_content()).group(1)


def error_type(response) -> str:
    return response.json()["detail"][0]["type"]


async def allow_resend(sessionmaker) -> None:
    async with sessionmaker() as session:
        await session.execute(
            update(VerificationCode).values(created_at=datetime.now(UTC) - timedelta(minutes=2))
        )
        await session.commit()


async def verify_both(client: AsyncClient, headers, outbox) -> None:
    assert (
        await client.post(f"{EMAIL}/confirm", json={"code": last_code(outbox)}, headers=headers)
    ).status_code == 200
    assert (await client.post(f"{PHONE}/code", headers=headers)).status_code == 202
    response = await client.post(
        f"{PHONE}/confirm", json={"code": last_code(outbox)}, headers=headers
    )
    assert response.status_code == 200


async def test_registration_email_code_is_sent_only_when_requested(client: AsyncClient, outbox):
    registration = await client.post(
        "/api/v1/accounts",
        json={
            "display_name": "Test customer",
            "email": "customer@example.com",
            "phone": "+380671111111",
            "role": "customer",
            "password": "secret123",
        },
    )
    assert registration.status_code == 201
    assert outbox == []

    tokens = await client.post(
        "/api/v1/auth/sign-in",
        json={"email": "customer@example.com", "password": "secret123"},
    )
    headers = {"Authorization": f"Bearer {tokens.json()['access_token']}"}
    status = await client.get("/api/v1/accounts/me/verification", headers=headers)
    assert status.json()["email"]["code_sent"] is False

    sent = await client.post(f"{EMAIL}/code", headers=headers)
    assert sent.status_code == 202
    message = outbox[-1]

    assert message["To"] == "customer@example.com"
    code = last_code(outbox)
    assert message["Subject"] == f"{code} is your Adify verification code"
    assert f"/account?email_code={code}#verification" in message.get_content()


async def test_email_code_verifies_the_email(client: AsyncClient, customer, outbox):
    response = await client.post(
        f"{EMAIL}/confirm", json={"code": last_code(outbox)}, headers=customer
    )

    assert response.status_code == 200
    assert response.json()["email_verified"] is True
    assert response.json()["phone_verified"] is False
    me = await client.get("/api/v1/accounts/me", headers=customer)
    assert me.json()["email_verified"] is True


async def test_sms_code_verifies_the_phone(client: AsyncClient, customer, outbox):
    sent = await client.post(f"{PHONE}/code", headers=customer)

    assert sent.status_code == 202
    assert sent.json() == {
        "channel": "phone",
        "destination": "+380671111111",
        "expires_in": 900,
        "resend_in": 60,
    }
    assert outbox[-1]["Subject"] == "SMS to +380671111111"
    response = await client.post(
        f"{PHONE}/confirm", json={"code": last_code(outbox)}, headers=customer
    )
    assert response.json()["phone_verified"] is True


async def test_wrong_code_counts_down_and_then_expires_the_code(
    client: AsyncClient, customer, outbox
):
    code = last_code(outbox)
    wrong = "000000" if code != "000000" else "111111"

    first = await client.post(f"{EMAIL}/confirm", json={"code": wrong}, headers=customer)
    assert (first.status_code, error_type(first)) == (400, "code_incorrect")
    assert first.json()["detail"][0]["msg"] == "This code is incorrect. 4 attempts left."
    for _ in range(3):
        await client.post(f"{EMAIL}/confirm", json={"code": wrong}, headers=customer)
    last = await client.post(f"{EMAIL}/confirm", json={"code": wrong}, headers=customer)
    assert error_type(last) == "code_attempts_exceeded"

    late = await client.post(f"{EMAIL}/confirm", json={"code": code}, headers=customer)
    assert error_type(late) == "code_used"


async def test_rejects_malformed_codes(client: AsyncClient, customer):
    for code in ("12345", "1234567", "abcdef"):
        response = await client.post(f"{EMAIL}/confirm", json={"code": code}, headers=customer)
        assert response.status_code == 422


async def test_expired_code_is_rejected(client: AsyncClient, customer, outbox, sessionmaker):
    async with sessionmaker() as session:
        await session.execute(
            update(VerificationCode).values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
        )
        await session.commit()

    response = await client.post(
        f"{EMAIL}/confirm", json={"code": last_code(outbox)}, headers=customer
    )

    assert error_type(response) == "code_expired"


async def test_resend_waits_a_minute_and_replaces_the_old_code(
    client: AsyncClient, customer, outbox, sessionmaker
):
    old = last_code(outbox)
    too_soon = await client.post(f"{EMAIL}/code", headers=customer)
    assert (too_soon.status_code, error_type(too_soon)) == (429, "resend_too_soon")
    assert 0 < int(too_soon.headers["retry-after"]) <= 60

    await allow_resend(sessionmaker)
    assert (await client.post(f"{EMAIL}/code", headers=customer)).status_code == 202
    new = last_code(outbox)

    if new != old:
        stale = await client.post(f"{EMAIL}/confirm", json={"code": old}, headers=customer)
        assert error_type(stale) == "code_incorrect"
    assert (
        await client.post(f"{EMAIL}/confirm", json={"code": new}, headers=customer)
    ).status_code == 200


async def test_phone_code_requires_a_request_first(client: AsyncClient, customer):
    response = await client.post(f"{PHONE}/confirm", json={"code": "123456"}, headers=customer)

    assert error_type(response) == "code_not_requested"


async def test_code_stops_counting_when_the_contact_changes(
    client: AsyncClient, customer, outbox, sessionmaker
):
    code = last_code(outbox)
    async with sessionmaker() as session:
        await session.execute(update(Account).values(email="changed@example.com"))
        await session.commit()

    response = await client.post(f"{EMAIL}/confirm", json={"code": code}, headers=customer)

    assert error_type(response) == "code_not_requested"


async def test_verified_channel_needs_no_new_code(client: AsyncClient, customer, outbox):
    await client.post(f"{EMAIL}/confirm", json={"code": last_code(outbox)}, headers=customer)

    response = await client.post(f"{EMAIL}/code", headers=customer)

    assert (response.status_code, error_type(response)) == (409, "already_verified")


async def test_codes_are_stored_only_as_keyed_hashes(
    client: AsyncClient, customer, outbox, sessionmaker
):
    async with sessionmaker() as session:
        record = await session.scalar(select(VerificationCode))

    assert last_code(outbox) not in record.code_hash
    assert record.destination == "customer@example.com"


async def test_verification_requires_sign_in(client: AsyncClient):
    assert (await client.post(f"{EMAIL}/code")).status_code == 401
    assert (await client.post(f"{EMAIL}/confirm", json={"code": "123456"})).status_code == 401


async def test_delivery_failure_is_reported(client: AsyncClient, customer, monkeypatch):
    def broken(message):
        raise OSError("connection refused")

    monkeypatch.setattr(mail, "_send", broken)
    response = await client.post(f"{PHONE}/code", headers=customer)

    assert (response.status_code, error_type(response)) == (503, "delivery_failed")


async def test_registration_succeeds_when_mail_is_down(client: AsyncClient, monkeypatch):
    def broken(message):
        raise OSError("connection refused")

    monkeypatch.setattr(mail, "_send", broken)
    await sign_up(
        client,
        "provider",
        "provider@example.com",
        "+380672222222",
        request_email_code=False,
    )


OFFER = {
    "category": "website-banners",
    "title": "Your brand on a design journal",
    "description": "A display banner placement on an independent design journal.",
    "price_uah": "3500.50",
    "delivery_days": 5,
    "specs": [{"label": "Dimensions", "value": "728 x 90 px"}],
}
REQUEST = {
    "category": "sponsored-articles",
    "title": "Looking for a home for our story",
    "description": "We want a website to publish a sponsored article about our brand.",
    "budget_uah": "4500",
    "specs": [{"label": "Length", "value": "1,000 words"}],
}


@pytest.fixture
async def offer(client: AsyncClient, outbox) -> str:
    provider = await sign_up(client, "provider", "provider@example.com", "+380672222222")
    await verify_both(client, provider, outbox)
    response = await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def test_unverified_users_are_blocked_with_an_explanation(client: AsyncClient, offer):
    customer = await sign_up(client, "customer", "customer@example.com", "+380671111111")

    for path, body in (
        (f"/api/v1/listings/{offer}/phone-reveal", None),
        (f"/api/v1/listings/{offer}/chats", None),
        ("/api/v1/listings/requests", REQUEST),
    ):
        response = await client.post(path, json=body, headers=customer)
        assert (response.status_code, error_type(response)) == (403, "verification_required")
        assert response.json()["detail"][0]["msg"] == (
            "Verify your email address and phone number to continue."
        )


async def test_half_verified_users_learn_what_is_missing(client: AsyncClient, offer, outbox):
    customer = await sign_up(client, "customer", "customer@example.com", "+380671111111")
    await client.post(f"{EMAIL}/confirm", json={"code": last_code(outbox)}, headers=customer)

    response = await client.post(f"/api/v1/listings/{offer}/phone-reveal", headers=customer)

    assert response.json()["detail"][0]["msg"] == "Verify your phone number to continue."


async def test_verified_users_reveal_phones_create_listings_and_may_chat(
    client: AsyncClient, offer, outbox
):
    customer = await sign_up(client, "customer", "customer@example.com", "+380671111111")
    await verify_both(client, customer, outbox)

    reveal = await client.post(f"/api/v1/listings/{offer}/phone-reveal", headers=customer)
    assert reveal.status_code == 200
    assert reveal.json() == {"phone": "+380672222222"}

    chat = await client.post(f"/api/v1/listings/{offer}/chats", headers=customer)
    assert chat.status_code == 201

    created = await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    assert created.status_code == 201


async def test_chat_rules_still_apply_after_verification(client: AsyncClient, offer, outbox):
    other = await sign_up(client, "provider", "other@example.com", "+380673333333")
    await verify_both(client, other, outbox)

    same_role = await client.post(f"/api/v1/listings/{offer}/chats", headers=other)

    assert (same_role.status_code, error_type(same_role)) == (403, "same_role_chat")


async def test_owner_cannot_chat_about_own_listing(client: AsyncClient, offer):
    owner = await client.post(
        "/api/v1/auth/sign-in", json={"email": "provider@example.com", "password": "secret123"}
    )
    headers = {"Authorization": f"Bearer {owner.json()['access_token']}"}

    response = await client.post(f"/api/v1/listings/{offer}/chats", headers=headers)

    assert error_type(response) == "own_listing"


async def test_status_tells_when_a_code_is_waiting(client: AsyncClient, customer, outbox):
    status = await client.get("/api/v1/accounts/me/verification", headers=customer)

    assert status.status_code == 200
    assert status.json()["email"] == {
        "verified": False,
        "destination": "customer@example.com",
        "code_sent": True,
        "resend_in": status.json()["email"]["resend_in"],
    }
    assert 0 < status.json()["email"]["resend_in"] <= 60
    assert status.json()["phone"] == {
        "verified": False,
        "destination": "+380671111111",
        "code_sent": False,
        "resend_in": 0,
    }

    await client.post(f"{EMAIL}/confirm", json={"code": last_code(outbox)}, headers=customer)
    after = await client.get("/api/v1/accounts/me/verification", headers=customer)
    assert after.json()["email"]["verified"] is True
    assert after.json()["email"]["code_sent"] is False


async def test_status_forgets_expired_codes(client: AsyncClient, customer, sessionmaker):
    async with sessionmaker() as session:
        await session.execute(
            update(VerificationCode).values(
                expires_at=datetime.now(UTC) - timedelta(seconds=1),
                created_at=datetime.now(UTC) - timedelta(minutes=16),
            )
        )
        await session.commit()

    status = await client.get("/api/v1/accounts/me/verification", headers=customer)

    assert status.json()["email"]["code_sent"] is False
    assert status.json()["email"]["resend_in"] == 0
