import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import verify_contacts
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from adify_api.accounts.models import Account
from adify_api.core.config import get_settings
from adify_api.listings.models import Listing, ListingType
from adify_api.orders.models import Order, OrderStatus

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


async def sign_up(
    client: AsyncClient, role: str, email: str, phone: str, sessionmaker=None
) -> dict[str, str]:
    body = {
        "display_name": f"Test {role}",
        "email": email,
        "phone": phone,
        "role": role,
        "password": "secret123",
    }
    assert (await client.post("/api/v1/accounts", json=body)).status_code == 201
    if sessionmaker is not None:
        await verify_contacts(sessionmaker, email)
    tokens = await client.post(
        "/api/v1/auth/sign-in", json={"email": email, "password": "secret123"}
    )
    return {"Authorization": f"Bearer {tokens.json()['access_token']}"}


@pytest.fixture
async def customer(client: AsyncClient, sessionmaker) -> dict[str, str]:
    return await sign_up(client, "customer", "customer@example.com", "+380671111111", sessionmaker)


@pytest.fixture
async def provider(client: AsyncClient, sessionmaker) -> dict[str, str]:
    return await sign_up(client, "provider", "provider@example.com", "+380672222222", sessionmaker)


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


# ADY-007 search (FR-016)


async def test_search_matches_title_description_and_category(
    client: AsyncClient, customer, provider
):
    offer = (await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)).json()
    request = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()

    by_title = (await client.get("/api/v1/listings", params={"q": "design journal"})).json()
    by_description = (await client.get("/api/v1/listings", params={"q": "display banner"})).json()
    by_category = (await client.get("/api/v1/listings", params={"q": "sponsored"})).json()

    assert [item["id"] for item in by_title["items"]] == [offer["id"]]
    assert [item["id"] for item in by_description["items"]] == [offer["id"]]
    assert [item["id"] for item in by_category["items"]] == [request["id"]]
    assert by_title["total"] == 1


async def test_search_is_case_insensitive_and_trims_spaces(client: AsyncClient, provider):
    await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)

    response = await client.get("/api/v1/listings", params={"q": "  DESIGN  "})

    assert response.status_code == 200
    assert response.json()["total"] == 1


async def test_search_treats_wildcards_literally(client: AsyncClient, provider):
    await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)

    for term in ("%", "_", "\\"):
        response = await client.get("/api/v1/listings", params={"q": term})
        assert response.json()["total"] == 0, term


async def test_search_without_matches_returns_an_empty_page(client: AsyncClient, provider):
    await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)

    response = await client.get("/api/v1/listings", params={"q": "nothing like this"})

    assert response.status_code == 200
    assert response.json() == {"items": [], "total": 0}


async def test_search_combines_with_type_and_respects_paging(client: AsyncClient, provider):
    for _ in range(3):
        await client.post("/api/v1/listings/offers", json=OFFER, headers=provider)

    offers = (
        await client.get(
            "/api/v1/listings", params={"q": "banner", "type": "offer", "limit": 2, "offset": 0}
        )
    ).json()
    requests = (
        await client.get("/api/v1/listings", params={"q": "banner", "type": "request"})
    ).json()

    assert offers["total"] == 3
    assert len(offers["items"]) == 2
    assert all(item["type"] == "offer" for item in offers["items"])
    assert requests["total"] == 0


@pytest.mark.parametrize("term", ["", "x" * 101])
async def test_search_rejects_invalid_length(client: AsyncClient, term: str):
    response = await client.get("/api/v1/listings", params={"q": term})

    assert response.status_code == 422


# ADY-011 filters, audience, and sorting (FR-082, FR-084–FR-086)


def offer(**overrides: object) -> dict[str, object]:
    return OFFER | overrides


async def publish(client: AsyncClient, headers: dict[str, str], body: dict[str, object]):
    response = await client.post("/api/v1/listings/offers", json=body, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


async def test_listing_accepts_a_target_audience(client: AsyncClient, provider):
    audience = {
        "age_min": 18,
        "age_max": 34,
        "country": "Ukraine",
        "socioeconomic": "Middle income",
        "traits": ["Gamers", "Students"],
    }

    listing = await publish(client, provider, offer(audience=audience))

    assert listing["audience"] == audience


async def test_listing_without_audience_returns_null(client: AsyncClient, provider):
    listing = await publish(client, provider, offer())

    assert listing["audience"] is None


@pytest.mark.parametrize(
    "audience",
    [
        {"age_min": 30, "age_max": 18},
        {"age_min": -1},
        {"age_max": 121},
        {"country": "x" * 101},
        {"traits": ["x" * 51]},
        {"traits": ["ok"] * 21},
        {"unknown": "value"},
    ],
)
async def test_rejects_invalid_audience(client: AsyncClient, provider, audience):
    response = await client.post(
        "/api/v1/listings/offers", json=offer(audience=audience), headers=provider
    )

    assert response.status_code == 422


async def test_filters_by_price_range_in_uah(client: AsyncClient, provider):
    cheap = await publish(client, provider, offer(price_uah="1000"))
    middle = await publish(client, provider, offer(price_uah="3500.50"))
    await publish(client, provider, offer(price_uah="9000"))

    response = await client.get(
        "/api/v1/listings", params={"price_min": "1000", "price_max": "4000"}
    )

    body = response.json()
    assert body["total"] == 2
    assert {item["id"] for item in body["items"]} == {cheap["id"], middle["id"]}


async def test_price_bounds_are_inclusive(client: AsyncClient, provider):
    listing = await publish(client, provider, offer(price_uah="3500.50"))

    exact = await client.get(
        "/api/v1/listings", params={"price_min": "3500.50", "price_max": "3500.50"}
    )

    assert [item["id"] for item in exact.json()["items"]] == [listing["id"]]


async def test_rejects_inverted_price_range(client: AsyncClient, provider):
    await publish(client, provider, offer())

    response = await client.get(
        "/api/v1/listings", params={"price_min": "5000", "price_max": "1000"}
    )

    assert response.status_code == 422
    assert error_type(response) == "invalid_price_range"


async def test_filters_by_maximum_delivery_time(client: AsyncClient, provider):
    fast = await publish(client, provider, offer(delivery_days=2))
    await publish(client, provider, offer(delivery_days=10))

    response = await client.get("/api/v1/listings", params={"delivery_max": 3})

    assert [item["id"] for item in response.json()["items"]] == [fast["id"]]


async def test_audience_ages_match_overlapping_ranges(client: AsyncClient, provider):
    young = await publish(client, provider, offer(audience={"age_min": 18, "age_max": 24}))
    broad = await publish(client, provider, offer(audience={"age_min": 18, "age_max": 45}))
    older = await publish(client, provider, offer(audience={"age_min": 55, "age_max": 70}))

    overlapping = await client.get("/api/v1/listings", params={"age_min": 30, "age_max": 35})
    touching = await client.get("/api/v1/listings", params={"age_min": 20, "age_max": 24})
    outside = await client.get("/api/v1/listings", params={"age_min": 30, "age_max": 35})

    assert {item["id"] for item in overlapping.json()["items"]} == {broad["id"]}
    assert {item["id"] for item in touching.json()["items"]} == {young["id"], broad["id"]}
    assert older["id"] not in {item["id"] for item in outside.json()["items"]}
    assert (await client.get("/api/v1/listings", params={"age_min": 80})).json()["total"] == 0


async def test_open_ended_audience_is_included(client: AsyncClient, provider):
    open_listing = await publish(client, provider, offer(audience={"age_min": 18}))
    other = await publish(client, provider, offer(audience={"country": "Ukraine"}))

    response = await client.get("/api/v1/listings", params={"age_max": 25})

    assert {item["id"] for item in response.json()["items"]} == {
        open_listing["id"],
        other["id"],
    }


async def test_rejects_inverted_age_range(client: AsyncClient, provider):
    await publish(client, provider, offer())

    response = await client.get("/api/v1/listings", params={"age_min": 40, "age_max": 20})

    assert response.status_code == 422
    assert error_type(response) == "invalid_age_range"


async def test_open_audience_matches_every_audience_filter(client: AsyncClient, provider):
    open_listing = await publish(client, provider, offer())

    for params in (
        {"country": "Ukraine"},
        {"socioeconomic": "middle"},
        {"traits": ["gamers"]},
        {"age_min": 30, "age_max": 40},
    ):
        response = await client.get("/api/v1/listings", params=params)
        assert [item["id"] for item in response.json()["items"]] == [open_listing["id"]], params


async def test_declared_audience_filters_out_other_audiences(client: AsyncClient, provider):
    await publish(client, provider, offer(audience={"country": "Poland", "traits": ["parents"]}))

    for params in ({"country": "Ukraine"}, {"traits": ["gamers"]}):
        response = await client.get("/api/v1/listings", params=params)
        assert response.json()["total"] == 0, params


async def test_filters_by_country_socioeconomic_and_traits(client: AsyncClient, provider):
    matching = await publish(
        client,
        provider,
        offer(
            audience={
                "country": "Ukraine",
                "socioeconomic": "Middle income",
                "traits": ["gamers", "students"],
            }
        ),
    )
    await publish(
        client,
        provider,
        offer(
            audience={"country": "Poland", "socioeconomic": "High income", "traits": ["parents"]}
        ),
    )

    by_country = await client.get("/api/v1/listings", params={"country": "ukra"})
    by_income = await client.get("/api/v1/listings", params={"socioeconomic": "middle"})
    by_trait = await client.get("/api/v1/listings", params={"traits": ["gamers"]})

    for response in (by_country, by_income, by_trait):
        assert [item["id"] for item in response.json()["items"]] == [matching["id"]]


async def test_traits_match_any_requested_value(client: AsyncClient, provider):
    first = await publish(client, provider, offer(audience={"traits": ["gamers"]}))
    second = await publish(client, provider, offer(audience={"traits": ["parents"]}))
    await publish(client, provider, offer(audience={"traits": ["commuters"]}))

    response = await client.get(
        "/api/v1/listings", params=[("traits", "gamers"), ("traits", "parents")]
    )

    assert {item["id"] for item in response.json()["items"]} == {first["id"], second["id"]}


@pytest.mark.parametrize("traits", [["x" * 51], ["ok"] * 21])
async def test_rejects_invalid_traits_filter(client: AsyncClient, provider, traits):
    await publish(client, provider, offer())

    response = await client.get("/api/v1/listings", params=[("traits", item) for item in traits])

    assert response.status_code == 422
    assert error_type(response) == "invalid_traits"


async def test_sorts_by_price_and_date(
    client: AsyncClient, provider, sessionmaker: async_sessionmaker[AsyncSession]
):
    cheap = await publish(client, provider, offer(price_uah="1000"))
    expensive = await publish(client, provider, offer(price_uah="9000"))
    # SQLite's now() has one-second resolution, so give the rows distinct timestamps.
    now = datetime.now(UTC)
    async with sessionmaker() as session:
        await session.execute(
            update(Listing)
            .where(Listing.id == uuid.UUID(cheap["id"]))
            .values(created_at=now - timedelta(days=2))
        )
        await session.execute(
            update(Listing)
            .where(Listing.id == uuid.UUID(expensive["id"]))
            .values(created_at=now - timedelta(days=1))
        )
        await session.commit()

    ascending = (await client.get("/api/v1/listings", params={"sort": "price_asc"})).json()
    descending = (await client.get("/api/v1/listings", params={"sort": "price_desc"})).json()
    newest = (await client.get("/api/v1/listings", params={"sort": "newest"})).json()
    oldest = (await client.get("/api/v1/listings", params={"sort": "oldest"})).json()

    assert [item["id"] for item in ascending["items"]] == [cheap["id"], expensive["id"]]
    assert [item["id"] for item in descending["items"]] == [expensive["id"], cheap["id"]]
    assert [item["id"] for item in newest["items"]] == [expensive["id"], cheap["id"]]
    assert [item["id"] for item in oldest["items"]] == [cheap["id"], expensive["id"]]


async def test_rejects_unknown_sort(client: AsyncClient):
    response = await client.get("/api/v1/listings", params={"sort": "popular"})

    assert response.status_code == 422


async def test_filters_combine_with_search_and_type(client: AsyncClient, provider):
    matching = await publish(
        client,
        provider,
        offer(title="A banner for gamers", price_uah="2000", delivery_days=3),
    )
    await publish(client, provider, offer(title="A banner for families", price_uah="8000"))
    await publish(
        client, provider, offer(title="A video for gamers", price_uah="2000", delivery_days=10)
    )

    response = await client.get(
        "/api/v1/listings",
        params={"q": "banner", "type": "offer", "price_max": "3000", "delivery_max": 5},
    )

    assert [item["id"] for item in response.json()["items"]] == [matching["id"]]


# FR-017: editing a listing


async def place_order(
    sessionmaker: async_sessionmaker[AsyncSession],
    listing_id: str,
    status: OrderStatus = OrderStatus.IN_PROGRESS,
) -> None:
    """Orders have no API yet, so the tests insert one between the owner and another account."""
    async with sessionmaker() as session:
        listing = await session.get(Listing, uuid.UUID(listing_id))
        assert listing is not None
        other = await session.scalar(select(Account.id).where(Account.id != listing.owner_id))
        assert other is not None
        customer, provider = (
            (listing.owner_id, other)
            if listing.type == ListingType.REQUEST
            else (other, listing.owner_id)
        )
        session.add(
            Order(listing_id=listing.id, customer_id=customer, provider_id=provider, status=status)
        )
        await session.commit()


async def edit(client: AsyncClient, listing_id: str, headers, body: dict[str, object]):
    return await client.patch(f"/api/v1/listings/{listing_id}", json=body, headers=headers)


async def test_owner_edits_the_title_and_price_and_the_listing_shows_them(
    client: AsyncClient, provider
):
    listing = await publish(client, provider, OFFER)

    response = await edit(
        client, listing["id"], provider, {"title": "  A fresh banner title  ", "price_uah": "4200"}
    )

    assert response.status_code == 200
    assert response.json()["locked_fields"] == []
    public = (await client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert public["title"] == "A fresh banner title"
    assert public["price_uah"] == "4200.00"
    assert public["description"] == OFFER["description"]
    assert public["category"] == OFFER["category"]
    assert "locked_fields" not in public


async def test_request_budget_changes_and_its_delivery_time_can_be_cleared(
    client: AsyncClient, customer
):
    created = await client.post(
        "/api/v1/listings/requests", json=REQUEST | {"delivery_days": 14}, headers=customer
    )

    response = await edit(
        client, created.json()["id"], customer, {"budget_uah": "5000.50", "delivery_days": None}
    )

    assert response.status_code == 200
    assert response.json()["price_uah"] == "5000.50"
    assert response.json()["delivery_days"] is None


async def test_an_offering_keeps_a_delivery_time(client: AsyncClient, provider):
    listing = await publish(client, provider, OFFER)

    response = await edit(client, listing["id"], provider, {"delivery_days": None})

    assert response.status_code == 422
    assert error_type(response) == "delivery_required"
    assert response.json()["detail"][0]["loc"] == ["body", "delivery_days"]


async def test_the_amount_field_matches_the_listing_type(client: AsyncClient, customer, provider):
    request = (
        await client.post("/api/v1/listings/requests", json=REQUEST, headers=customer)
    ).json()
    offering = await publish(client, provider, OFFER)

    for listing, headers, field in (
        (request, customer, "price_uah"),
        (offering, provider, "budget_uah"),
    ):
        response = await edit(client, listing["id"], headers, {field: "100"})
        assert response.status_code == 422
        assert error_type(response) == "amount_field_mismatch"
        assert response.json()["detail"][0]["loc"] == ["body", field]


async def test_category_changes_while_no_order_is_active(client: AsyncClient, provider):
    listing = await publish(client, provider, OFFER)

    response = await edit(client, listing["id"], provider, {"category": "social-media-posts"})

    assert response.status_code == 200
    assert response.json()["category"] == "social-media-posts"


@pytest.mark.parametrize(
    "status", [OrderStatus.PENDING, OrderStatus.IN_PROGRESS, OrderStatus.DISPUTED]
)
async def test_an_active_order_locks_the_category_and_saves_nothing(
    client: AsyncClient, customer, provider, sessionmaker, status
):
    listing = await publish(client, provider, OFFER)
    await place_order(sessionmaker, listing["id"], status)

    response = await edit(
        client,
        listing["id"],
        provider,
        {"category": "social-media-posts", "title": "This title must not be saved"},
    )

    assert response.status_code == 409
    assert error_type(response) == "category_locked"
    assert response.json()["detail"][0]["loc"] == ["body", "category"]
    assert "active order" in response.json()["detail"][0]["msg"]
    public = (await client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert public["category"] == OFFER["category"]
    assert public["title"] == OFFER["title"]


async def test_other_fields_stay_editable_while_an_order_is_active(
    client: AsyncClient, customer, provider, sessionmaker
):
    listing = await publish(client, provider, OFFER)
    await place_order(sessionmaker, listing["id"])
    description = "An updated description of the banner placement and its audience."

    # The web form sends the unchanged category back; that is not a change.
    response = await edit(
        client,
        listing["id"],
        provider,
        {"category": OFFER["category"], "description": description, "delivery_days": 9},
    )

    assert response.status_code == 200
    assert response.json()["description"] == description
    assert response.json()["delivery_days"] == 9
    assert response.json()["locked_fields"] == ["category"]


@pytest.mark.parametrize("status", [OrderStatus.COMPLETED, OrderStatus.CANCELLED])
async def test_closed_orders_do_not_lock_the_category(
    client: AsyncClient, customer, provider, sessionmaker, status
):
    listing = await publish(client, provider, OFFER)
    await place_order(sessionmaker, listing["id"], status)

    response = await edit(client, listing["id"], provider, {"category": "stream-ads"})

    assert response.status_code == 200
    assert response.json()["locked_fields"] == []


async def test_specs_and_audience_are_replaced_or_cleared(client: AsyncClient, provider):
    listing = await publish(client, provider, offer(audience={"age_min": 18, "country": "Ukraine"}))
    specs = [{"label": "Format", "value": "PNG"}, {"label": "Size", "value": "300 x 250 px"}]

    replaced = await edit(
        client, listing["id"], provider, {"specs": specs, "audience": {"traits": ["gamers"]}}
    )
    cleared = await edit(client, listing["id"], provider, {"specs": [], "audience": None})
    emptied = await edit(client, listing["id"], provider, {"audience": {}})

    assert replaced.json()["specs"] == specs
    assert replaced.json()["audience"] == {
        "age_min": None,
        "age_max": None,
        "country": None,
        "socioeconomic": None,
        "traits": ["gamers"],
    }
    assert cleared.json()["specs"] == []
    assert cleared.json()["audience"] is None
    assert emptied.status_code == 200
    assert emptied.json()["audience"] is None


async def test_an_empty_edit_changes_nothing(client: AsyncClient, provider):
    listing = await publish(client, provider, OFFER)

    response = await edit(client, listing["id"], provider, {})

    assert response.status_code == 200
    assert {key: value for key, value in response.json().items() if key != "locked_fields"} == (
        listing
    )


@pytest.mark.parametrize(
    ("change", "kind"),
    [
        ({"title": "Hi"}, "string_too_short"),
        ({"title": None}, "null_not_allowed"),
        ({"description": "Too short."}, "string_too_short"),
        ({"category": "billboards"}, "enum"),
        ({"category": None}, "null_not_allowed"),
        ({"price_uah": "0"}, "greater_than"),
        ({"price_uah": None}, "null_not_allowed"),
        ({"delivery_days": 366}, "less_than_equal"),
        ({"specs": None}, "null_not_allowed"),
        ({"specs": [{"label": "L", "value": "v"}] * 11}, "too_long"),
        ({"audience": {"age_min": 30, "age_max": 20}}, "value_error"),
        ({"type": "request"}, "extra_forbidden"),
        ({"owner_id": str(uuid.uuid4())}, "extra_forbidden"),
    ],
)
async def test_rejects_invalid_edits(client: AsyncClient, provider, change, kind):
    listing = await publish(client, provider, OFFER)

    response = await edit(client, listing["id"], provider, change)

    assert response.status_code == 422
    assert error_type(response) == kind


async def test_only_the_verified_owner_can_edit(
    client: AsyncClient, customer, provider, sessionmaker
):
    listing = await publish(client, provider, OFFER)
    other_provider = await sign_up(
        client, "provider", "other@example.com", "+380673333333", sessionmaker
    )

    guest = await edit(client, listing["id"], {}, {"title": "A guest edit"})
    stranger = await edit(client, listing["id"], other_provider, {"title": "A stranger edit"})
    wrong_role = await edit(client, listing["id"], customer, {"title": "A customer edit"})
    async with sessionmaker() as session:
        await session.execute(
            update(Account)
            .where(Account.email == "provider@example.com")
            .values(phone_verified=False)
        )
        await session.commit()
    unverified = await edit(client, listing["id"], provider, {"title": "An unverified edit"})

    assert guest.status_code == 401
    assert stranger.status_code == wrong_role.status_code == 403
    assert error_type(stranger) == error_type(wrong_role) == "not_listing_owner"
    assert unverified.status_code == 403
    assert error_type(unverified) == "verification_required"
    public = (await client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert public["title"] == OFFER["title"]


async def test_editing_an_unknown_listing_is_not_found(client: AsyncClient, provider):
    response = await edit(client, str(uuid.uuid4()), provider, {"title": "Nothing to edit"})

    assert response.status_code == 404
    assert error_type(response) == "listing_not_found"


async def test_owner_view_reports_the_locked_fields(
    client: AsyncClient, customer, provider, sessionmaker
):
    listing = await publish(client, provider, OFFER)
    path = f"/api/v1/listings/mine/{listing['id']}"

    before = await client.get(path, headers=provider)
    await place_order(sessionmaker, listing["id"])
    after = await client.get(path, headers=provider)
    stranger = await client.get(path, headers=customer)
    guest = await client.get(path)
    unknown = await client.get(f"/api/v1/listings/mine/{uuid.uuid4()}", headers=provider)

    assert before.status_code == 200
    assert before.json()["locked_fields"] == []
    assert before.json()["title"] == OFFER["title"]
    assert after.json()["locked_fields"] == ["category"]
    assert stranger.status_code == 403
    assert error_type(stranger) == "not_listing_owner"
    assert guest.status_code == 401
    assert unknown.status_code == 404


# FR-018, FR-019: pausing, resuming, and expiry


async def expire(sessionmaker: async_sessionmaker[AsyncSession], listing_id: str, paused=True):
    """Move a listing past the end of its lifetime, optionally paused before it expired."""
    now = datetime.now(UTC)
    async with sessionmaker() as session:
        await session.execute(
            update(Listing)
            .where(Listing.id == uuid.UUID(listing_id))
            .values(
                expires_at=now - timedelta(days=1),
                paused_at=now - timedelta(days=3) if paused else None,
            )
        )
        await session.commit()


async def public_ids(client: AsyncClient) -> list[str]:
    return [item["id"] for item in (await client.get("/api/v1/listings")).json()["items"]]


async def test_a_new_listing_is_active_for_the_configured_lifetime(
    client: AsyncClient, provider, monkeypatch
):
    monkeypatch.setattr(get_settings(), "listing_lifetime_days", 7)

    listing = await publish(client, provider, OFFER)

    assert listing["status"] == "active"
    lifetime = datetime.fromisoformat(listing["expires_at"]) - datetime.fromisoformat(
        listing["created_at"]
    )
    assert timedelta(days=7) - timedelta(minutes=1) < lifetime < timedelta(days=7, minutes=1)


async def test_owner_pauses_and_resumes_a_listing(client: AsyncClient, customer, provider):
    listing = await publish(client, provider, OFFER)
    chat = f"/api/v1/listings/{listing['id']}/chats"

    paused = await client.post(f"/api/v1/listings/{listing['id']}/pause", headers=provider)

    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert paused.json()["locked_fields"] == []
    public = (await client.get(f"/api/v1/listings/{listing['id']}")).json()
    assert public["status"] == "paused"
    assert listing["id"] not in await public_ids(client)
    mine = (await client.get("/api/v1/listings/mine", headers=provider)).json()
    assert [(item["id"], item["status"]) for item in mine["items"]] == [(listing["id"], "paused")]
    blocked = await client.post(chat, headers=customer)
    assert blocked.status_code == 409
    assert error_type(blocked) == "listing_paused"
    assert "not accepting new orders" in blocked.json()["detail"][0]["msg"]

    resumed = await client.post(f"/api/v1/listings/{listing['id']}/resume", headers=provider)

    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"
    assert listing["id"] in await public_ids(client)
    # Every order check passes again; only the chat itself is still to come.
    reopened = await client.post(chat, headers=customer)
    assert reopened.status_code == 501
    assert error_type(reopened) == "chat_not_available"


async def test_pausing_and_resuming_twice_changes_nothing(client: AsyncClient, provider):
    listing = await publish(client, provider, OFFER)
    base = f"/api/v1/listings/{listing['id']}"

    first = await client.post(f"{base}/pause", headers=provider)
    second = await client.post(f"{base}/pause", headers=provider)
    resumed = await client.post(f"{base}/resume", headers=provider)
    again = await client.post(f"{base}/resume", headers=provider)

    assert first.json() == second.json()
    assert resumed.json()["status"] == again.json()["status"] == "active"


async def test_a_paused_listing_can_still_be_edited(client: AsyncClient, provider):
    listing = await publish(client, provider, OFFER)
    await client.post(f"/api/v1/listings/{listing['id']}/pause", headers=provider)

    response = await edit(client, listing["id"], provider, {"title": "Edited while paused"})

    assert response.status_code == 200
    assert response.json()["status"] == "paused"


@pytest.mark.parametrize("paused", [True, False])
async def test_an_expired_listing_cannot_be_resumed_or_ordered(
    client: AsyncClient, customer, provider, sessionmaker, paused
):
    listing = await publish(client, provider, OFFER)
    await expire(sessionmaker, listing["id"], paused=paused)
    base = f"/api/v1/listings/{listing['id']}"

    resume = await client.post(f"{base}/resume", headers=provider)
    pause = await client.post(f"{base}/pause", headers=provider)
    chat = await client.post(f"{base}/chats", headers=customer)

    assert resume.status_code == 409
    assert error_type(resume) == "listing_expired"
    assert resume.json()["detail"][0]["msg"] == "An expired listing cannot be resumed."
    assert pause.status_code == 409
    assert error_type(pause) == "listing_expired"
    assert chat.status_code == 409
    assert error_type(chat) == "listing_expired"
    details = (await client.get(base)).json()
    assert details["status"] == "expired"
    assert listing["id"] not in await public_ids(client)


async def test_only_the_owner_pauses_and_only_a_verified_owner_resumes(
    client: AsyncClient, customer, provider, sessionmaker
):
    listing = await publish(client, provider, OFFER)
    base = f"/api/v1/listings/{listing['id']}"

    for action in ("pause", "resume"):
        guest = await client.post(f"{base}/{action}")
        stranger = await client.post(f"{base}/{action}", headers=customer)
        unknown = await client.post(f"/api/v1/listings/{uuid.uuid4()}/{action}", headers=provider)
        assert guest.status_code == 401
        assert stranger.status_code == 403
        assert error_type(stranger) == "not_listing_owner"
        assert unknown.status_code == 404

    async with sessionmaker() as session:
        await session.execute(
            update(Account)
            .where(Account.email == "provider@example.com")
            .values(email_verified=False)
        )
        await session.commit()
    # Withdrawing a listing is always possible; putting it back needs verified contacts.
    paused = await client.post(f"{base}/pause", headers=provider)
    resumed = await client.post(f"{base}/resume", headers=provider)

    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    assert resumed.status_code == 403
    assert error_type(resumed) == "verification_required"
