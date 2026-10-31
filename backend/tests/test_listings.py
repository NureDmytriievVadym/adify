import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from adify_api.core.config import get_settings

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
PDF = b"%PDF-1.7\n" + b"0" * 64
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64

REQUEST = {
    "category": "sponsored-articles",
    "title": "Looking for a home for our story",
    "description": "We want a website to publish a sponsored article about our brand.",
    "budget_uah": "4500",
    "specs": [{"label": "Length", "value": "1,000 words"}],
}
OFFER = {
    "category": "website-banners",
    "title": "Your brand on a design journal",
    "description": "A display banner placement on an independent design journal.",
    "price_uah": "3500.50",
    "delivery_days": 5,
    "specs": [{"label": "Dimensions", "value": "728 x 90 px"}],
}


@pytest.fixture(autouse=True)
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))
    return tmp_path


async def sign_up(client: AsyncClient, role: str, email: str, phone: str) -> dict[str, str]:
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
    return {"Authorization": f"Bearer {tokens.json()['access_token']}"}


@pytest.fixture
async def customer(client: AsyncClient) -> dict[str, str]:
    return await sign_up(client, "customer", "customer@example.com", "+380671111111")


@pytest.fixture
async def provider(client: AsyncClient) -> dict[str, str]:
    return await sign_up(client, "provider", "provider@example.com", "+380672222222")


def error_type(response) -> str:
    return response.json()["detail"][0]["type"]


async def upload(client, listing_id, headers, data=PNG, filename="brief.png"):
    return await client.post(
        f"/api/v1/listings/{listing_id}/attachments",
        params={"filename": filename},
        content=data,
        headers=headers | {"Content-Type": "application/octet-stream"},
    )


# ADY-008


async def test_customer_creates_an_ad_request(client: AsyncClient, customer):
    response = await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "request"
    assert body["category"] == "sponsored-articles"
    assert body["price_uah"] == "4500.00"
    assert body["delivery_days"] is None
    assert body["specs"] == [{"label": "Length", "value": "1,000 words"}]
    assert body["attachments"] == []
    assert body["owner"]["display_name"] == "Test customer"


async def test_request_accepts_an_optional_delivery_time(client: AsyncClient, customer):
    response = await client.post(
        "/api/v1/listings/requests", json=REQUEST | {"delivery_days": 14}, headers=customer
    )

    assert response.status_code == 201
    assert response.json()["delivery_days"] == 14


async def test_provider_cannot_create_a_request(client: AsyncClient, provider):
    response = await client.post("/api/v1/listings/requests", json=REQUEST, headers=provider)

    assert response.status_code == 403
    assert error_type(response) == "role_not_allowed"


async def test_creating_a_listing_requires_sign_in(client: AsyncClient):
    for path, body in (("requests", REQUEST), ("offers", OFFER)):
        response = await client.post(f"/api/v1/listings/{path}", json=body)
        assert response.status_code == 401
        assert error_type(response) == "not_authenticated"


@pytest.mark.parametrize(
    ("change", "kind"),
    [
        ({"title": "Hi"}, "string_too_short"),
        ({"title": "x" * 121}, "string_too_long"),
        ({"description": "Too short."}, "string_too_short"),
        ({"category": "billboards"}, "enum"),
        ({"budget_uah": "0"}, "greater_than"),
        ({"budget_uah": "-5"}, "greater_than"),
        ({"budget_uah": "12.345"}, "decimal_max_places"),
        ({"budget_uah": "100000000"}, "less_than_equal"),
        ({"delivery_days": 0}, "greater_than_equal"),
        ({"delivery_days": 366}, "less_than_equal"),
        ({"specs": [{"label": "", "value": "x"}]}, "string_too_short"),
        ({"specs": [{"label": "L", "value": "v"}] * 11}, "too_long"),
        ({"type": "offer"}, "extra_forbidden"),
    ],
)
async def test_rejects_invalid_requests(client: AsyncClient, customer, change, kind):
    response = await client.post(
        "/api/v1/listings/requests", json=REQUEST | change, headers=customer
    )

    assert response.status_code == 422
    assert error_type(response) == kind


async def test_request_budget_is_required(client: AsyncClient, customer):
    body = {key: value for key, value in REQUEST.items() if key != "budget_uah"}

    response = await client.post("/api/v1/listings/requests", json=body, headers=customer)

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "budget_uah"]


# ADY-009


async def test_provider_creates_an_ad_offering(client: AsyncClient, provider):
    response = await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)

    assert response.status_code == 201
    body = response.json()
    assert body["type"] == "offer"
    assert body["price_uah"] == "3500.50"
    assert body["delivery_days"] == 5
    assert body["owner"]["role"] == "provider"


async def test_customer_cannot_create_an_offer(client: AsyncClient, customer):
    response = await client.post("/api/v1/listings/offers", json=OFFER, headers=customer)

    assert response.status_code == 403
    assert error_type(response) == "role_not_allowed"


async def test_offer_requires_price_and_delivery_time(client: AsyncClient, provider):
    for missing in ("price_uah", "delivery_days"):
        body = {key: value for key, value in OFFER.items() if key != missing}
        response = await client.post("/api/v1/listings/offers", json=body, headers=provider)
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"] == ["body", missing]


async def test_offer_rejects_a_budget_field(client: AsyncClient, provider):
    body = {key: value for key, value in OFFER.items() if key != "price_uah"} | {"budget_uah": 100}

    response = await client.post("/api/v1/listings/offers", json=body, headers=provider)

    assert response.status_code == 422


# ADY-010


async def test_listing_details_are_public_and_hide_contacts(client: AsyncClient, provider):
    created = await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)

    response = await client.get(f"/api/v1/listings/{created.json()['id']}")

    assert response.status_code == 200
    assert response.json() == created.json()
    assert "provider@example.com" not in response.text
    assert "+380672222222" not in response.text


async def test_unknown_listing_is_not_found(client: AsyncClient):
    response = await client.get(f"/api/v1/listings/{uuid.uuid4()}")

    assert response.status_code == 404
    assert error_type(response) == "listing_not_found"


async def test_owner_attaches_and_anyone_downloads_files(client: AsyncClient, customer, storage):
    listing = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()

    uploaded = await upload(client, listing["id"], customer, PDF, "../../etc/brief.pdf")

    assert uploaded.status_code == 201
    attachment = uploaded.json()
    assert attachment["filename"] == "brief.pdf"
    assert attachment["content_type"] == "application/pdf"
    assert attachment["size"] == len(PDF)
    assert (storage / attachment["id"]).read_bytes() == PDF

    details = await client.get(f"/api/v1/listings/{listing['id']}")
    assert [item["id"] for item in details.json()["attachments"]] == [attachment["id"]]

    download = await client.get(attachment["url"])
    assert download.status_code == 200
    assert download.content == PDF
    assert download.headers["content-type"] == "application/pdf"
    assert download.headers["x-content-type-options"] == "nosniff"


@pytest.mark.parametrize(
    ("data", "content_type"),
    [(PNG, "image/png"), (b"\xff\xd8\xff\xe0" + b"0" * 32, "image/jpeg"), (MP4, "video/mp4")],
)
async def test_detects_the_type_from_the_content(client, customer, data, content_type):
    listing = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()

    response = await upload(client, listing["id"], customer, data, "file.bin")

    assert response.status_code == 201
    assert response.json()["content_type"] == content_type


async def test_rejects_files_that_are_not_allowed(client: AsyncClient, customer):
    listing = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()

    html = await upload(client, listing["id"], customer, b"<script>alert(1)</script>", "a.png")
    empty = await upload(client, listing["id"], customer, b"", "empty.png")

    assert html.status_code == 415
    assert error_type(html) == "attachment_type_not_allowed"
    assert empty.status_code == 422
    assert error_type(empty) == "attachment_empty"


async def test_rejects_oversized_files(client: AsyncClient, customer, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_attachment_bytes", 100)
    listing = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()

    response = await upload(client, listing["id"], customer, PNG + b"0" * 100)

    assert response.status_code == 413
    assert error_type(response) == "attachment_too_large"


async def test_limits_the_number_of_attachments(client: AsyncClient, customer, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_attachments", 2)
    listing = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()

    statuses = [(await upload(client, listing["id"], customer)).status_code for _ in range(3)]

    assert statuses == [201, 201, 409]


async def test_only_the_owner_changes_attachments(client: AsyncClient, customer, provider):
    listing = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()
    attachment = (await upload(client, listing["id"], customer)).json()

    foreign_upload = await upload(client, listing["id"], provider)
    foreign_delete = await client.delete(attachment["url"], headers=provider)
    anonymous_upload = await upload(client, listing["id"], {})

    assert foreign_upload.status_code == 403
    assert error_type(foreign_upload) == "not_listing_owner"
    assert foreign_delete.status_code == 403
    assert anonymous_upload.status_code == 401


async def test_owner_deletes_an_attachment(client: AsyncClient, customer, storage):
    listing = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()
    attachment = (await upload(client, listing["id"], customer)).json()

    deleted = await client.delete(attachment["url"], headers=customer)

    assert deleted.status_code == 204
    assert not (storage / attachment["id"]).exists()
    assert (await client.get(attachment["url"])).status_code == 404
    details = await client.get(f"/api/v1/listings/{listing['id']}")
    assert details.json()["attachments"] == []
    again = await client.delete(attachment["url"], headers=customer)
    assert error_type(again) == "attachment_not_found"


async def test_attachments_of_unknown_listings_are_not_found(client: AsyncClient, customer):
    response = await upload(client, uuid.uuid4(), customer)

    assert response.status_code == 404
    assert error_type(response) == "listing_not_found"


# Browsing


async def test_public_list_shows_requests_and_offers_newest_first(
    client: AsyncClient, customer, provider
):
    request = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()
    offer = (await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)).json()

    response = await client.get("/api/v1/listings")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {request["id"], offer["id"]}
    assert "@example.com" not in response.text


async def test_public_list_filters_by_type_and_category(client: AsyncClient, customer, provider):
    await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)

    requests = (await client.get("/api/v1/listings", params={"type": "request"})).json()
    banners = (await client.get("/api/v1/listings", params={"category": "website-banners"})).json()

    assert [item["type"] for item in requests["items"]] == ["request"]
    assert [item["category"] for item in banners["items"]] == ["website-banners"]


async def test_public_list_is_paged(client: AsyncClient, customer):
    for _ in range(3):
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)

    page = (await client.get("/api/v1/listings", params={"limit": 2, "offset": 2})).json()

    assert page["total"] == 3
    assert len(page["items"]) == 1
    too_many = await client.get("/api/v1/listings", params={"limit": 51})
    assert too_many.status_code == 422


async def test_my_listings_only_shows_the_owners_listings(client: AsyncClient, customer, provider):
    mine = (await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)).json()
    await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)

    response = await client.get("/api/v1/listings/mine", headers=customer)

    assert response.status_code == 200
    assert [item["id"] for item in response.json()["items"]] == [mine["id"]]
    assert response.json()["total"] == 1


async def test_my_listings_requires_sign_in(client: AsyncClient):
    response = await client.get("/api/v1/listings/mine")

    assert response.status_code == 401
