"""ADY-022: work stages, deadlines, and evidence on an order."""

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from test_orders import sign_up
from test_payments import FakeMono, error_type
from test_start_work import create_order, pay

from adify_api.core.config import get_settings
from adify_api.orders.models import Order, OrderStatus
from adify_api.payments.mono import get_mono

pytestmark = pytest.mark.anyio

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
TEXT = b"A screenshot of the banner placement.\n"
EICAR = b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"


def days(n: int) -> str:
    return (datetime.now(UTC).date() + timedelta(days=n)).isoformat()


@pytest.fixture(autouse=True)
def storage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(get_settings(), "storage_dir", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def no_mono_settings(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "mono_token", "")
    monkeypatch.setattr(settings, "api_public_url", "")
    monkeypatch.setattr(settings, "clamav_host", "")


@pytest.fixture
def mono(app) -> FakeMono:
    fake = FakeMono()
    app.dependency_overrides[get_mono] = lambda: fake
    return fake


@pytest.fixture
async def customer(client, sessionmaker):
    return await sign_up(client, sessionmaker, "customer", "customer@example.com", "+380671111111")


@pytest.fixture
async def provider(client, sessionmaker):
    return await sign_up(client, sessionmaker, "provider", "provider@example.com", "+380672222222")


@pytest.fixture
async def started(client, mono, customer, provider) -> str:
    order = await create_order(client, customer, provider)
    await pay(client, mono, customer, order)
    assert (await client.post(f"/api/v1/orders/{order}/start", headers=provider)).is_success
    return order


async def get_order(client: AsyncClient, order: str, headers) -> dict:
    return (await client.get(f"/api/v1/orders/{order}", headers=headers)).json()


async def add_stage(client: AsyncClient, order: str, headers, **body):
    return await client.post(f"/api/v1/orders/{order}/stages", json=body, headers=headers)


async def evidence(client: AsyncClient, order: str, headers, note=None, files=None):
    data = {"note": note} if note is not None else {}
    return await client.post(
        f"/api/v1/orders/{order}/evidence", data=data, files=files or [], headers=headers
    )


async def set_status(sessionmaker, order: str, status: OrderStatus) -> None:
    async with sessionmaker() as session:
        await session.execute(
            update(Order).where(Order.id == uuid.UUID(order)).values(status=status)
        )
        await session.commit()


# FR-037: stages and deadlines


async def test_either_participant_adds_a_stage(client: AsyncClient, customer, provider, started):
    by_provider = await add_stage(
        client, started, provider, title="Creative review", deadline=days(10)
    )
    by_customer = await add_stage(
        client, started, customer, title="Final report", deadline=days(18)
    )

    assert by_provider.status_code == 201
    stage = by_provider.json()["stages"][-1]
    assert stage["title"] == "Creative review"
    assert stage["deadline"] == days(10)
    assert stage["completed_at"] is None
    assert stage["completed_by"] is None
    assert by_customer.status_code == 201
    assert [item["title"] for item in by_customer.json()["stages"]] == [
        "Banner goes live",
        "Placement report",
        "Creative review",
        "Final report",
    ]
    assert (await get_order(client, started, customer))["stages"] == by_customer.json()["stages"]


@pytest.mark.parametrize(
    ("body", "kind"),
    [
        ({"title": "Yesterday", "deadline": days(-1)}, "stage_deadline_past"),
        ({}, "missing"),
        ({"title": "x" * 121}, "string_too_long"),
    ],
)
async def test_rejects_invalid_stages(client: AsyncClient, provider, started, body, kind):
    response = await add_stage(client, started, provider, **body)

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == kind


async def test_a_stage_deadline_cannot_pass_the_order_deadline(
    client: AsyncClient, provider, started
):
    response = await add_stage(client, started, provider, title="Too late", deadline=days(25))

    assert response.status_code == 422
    assert error_type(response) == "stage_deadline_after_order"


async def test_an_order_has_at_most_ten_stages(client: AsyncClient, provider, started):
    for index in range(8):
        response = await add_stage(
            client, started, provider, title=f"Extra stage {index}", deadline=days(10)
        )
        assert response.status_code == 201

    response = await add_stage(client, started, provider, title="Eleventh", deadline=days(10))

    assert response.status_code == 409
    assert error_type(response) == "stage_limit"


async def test_a_stage_is_completed_and_reopened(client: AsyncClient, customer, provider, started):
    stage = (await get_order(client, started, provider))["stages"][0]

    completed = await client.post(
        f"/api/v1/orders/{started}/stages/{stage['id']}/complete", headers=customer
    )
    again = await client.post(
        f"/api/v1/orders/{started}/stages/{stage['id']}/complete", headers=provider
    )
    reopened = await client.post(
        f"/api/v1/orders/{started}/stages/{stage['id']}/reopen", headers=provider
    )

    assert completed.status_code == 200
    done = completed.json()["stages"][0]
    assert done["completed_at"] is not None
    assert done["completed_by"]["display_name"] == "Test customer 11"
    assert again.status_code == 409
    assert error_type(again) == "stage_already_completed"
    assert reopened.status_code == 200
    assert reopened.json()["stages"][0]["completed_at"] is None
    assert reopened.json()["stages"][0]["completed_by"] is None


async def test_stage_actions_reject_unknown_stages_and_wrong_states(
    client: AsyncClient, provider, started, sessionmaker
):
    unknown = await client.post(
        f"/api/v1/orders/{started}/stages/{uuid.uuid4()}/complete", headers=provider
    )
    await set_status(sessionmaker, started, OrderStatus.DISPUTED)
    frozen = await add_stage(client, started, provider, title="Frozen", deadline=days(5))

    assert unknown.status_code == 404
    assert error_type(unknown) == "stage_not_found"
    assert frozen.status_code == 409
    assert error_type(frozen) == "order_not_workable"


async def test_outsiders_cannot_add_stages(client: AsyncClient, sessionmaker, started):
    outsider = await sign_up(client, sessionmaker, "provider", "other@example.com", "+380673333333")

    response = await add_stage(client, started, outsider, title="Intrusion", deadline=days(5))

    assert response.status_code == 403
    assert error_type(response) == "not_order_participant"


# FR-041: evidence


async def test_evidence_with_a_note_and_screenshot_is_visible_to_both(
    client: AsyncClient, customer, provider, started, storage
):
    response = await evidence(
        client,
        started,
        provider,
        note="  Screenshot of the live banner.  ",
        files=[("files", ("banner.png", PNG, "image/png"))],
    )

    assert response.status_code == 201
    [entry] = response.json()["evidence"]
    assert entry["note"] == "Screenshot of the live banner."
    assert entry["author"]["display_name"] == "Test provider 22"
    assert entry["files"][0]["filename"] == "banner.png"
    assert entry["files"][0]["content_type"] == "image/png"
    assert entry["files"][0]["size"] == len(PNG)
    assert (storage / entry["files"][0]["id"]).read_bytes() == PNG
    seen = (await get_order(client, started, customer))["evidence"]
    assert [item["id"] for item in seen] == [entry["id"]]
    assert seen[0]["note"] == entry["note"]
    assert seen[0]["author"]["display_name"] == entry["author"]["display_name"]
    assert [file["id"] for file in seen[0]["files"]] == [entry["files"][0]["id"]]

    download = await client.get(entry["files"][0]["url"], headers=customer)
    assert download.status_code == 200
    assert download.content == PNG
    assert download.headers["content-type"] == "image/png"
    assert download.headers["x-content-type-options"] == "nosniff"


async def test_evidence_accepts_a_note_alone_or_a_file_alone(
    client: AsyncClient, customer, provider, started
):
    note_only = await evidence(client, started, customer, note="A written update.")
    file_only = await evidence(
        client, started, customer, files=[("files", ("notes.txt", TEXT, "text/plain"))]
    )

    assert note_only.status_code == 201
    assert note_only.json()["evidence"][0]["note"] == "A written update."
    assert note_only.json()["evidence"][0]["files"] == []
    assert file_only.status_code == 201
    assert file_only.json()["evidence"][1]["note"] is None
    assert file_only.json()["evidence"][1]["files"][0]["content_type"] == "text/plain"


async def test_empty_evidence_is_rejected(client: AsyncClient, provider, started):
    response = await evidence(client, started, provider, note="   ")

    assert response.status_code == 422
    assert error_type(response) == "evidence_empty"


async def test_eicar_is_rejected_by_the_malware_scan(
    client: AsyncClient, provider, started, storage
):
    response = await evidence(
        client, started, provider, files=[("files", ("eicar.txt", EICAR, "text/plain"))]
    )

    assert response.status_code == 422
    assert error_type(response) == "malware_detected"
    assert "Eicar-Test-Signature" in response.json()["detail"][0]["msg"]
    assert (await get_order(client, started, provider))["evidence"] == []
    assert list(storage.iterdir()) == []


async def test_evidence_file_limits(client: AsyncClient, provider, started, monkeypatch):
    too_many = await evidence(
        client,
        started,
        provider,
        files=[("files", (f"file-{index}.txt", TEXT, "text/plain")) for index in range(6)],
    )

    monkeypatch.setattr(get_settings(), "max_evidence_bytes", 100)
    too_large = await evidence(
        client,
        started,
        provider,
        files=[("files", ("large.png", PNG + b"0" * 100, "image/png"))],
    )
    note = await evidence(client, started, provider, note="x" * 2001)

    assert too_many.status_code == 422
    assert error_type(too_many) == "too_many_evidence_files"
    assert too_large.status_code == 413
    assert error_type(too_large) == "evidence_file_too_large"
    assert note.status_code == 422
    assert error_type(note) == "evidence_note_too_long"


async def test_a_configured_but_unreachable_scanner_rejects_the_upload(
    client: AsyncClient, provider, started, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", 9)
    monkeypatch.setattr(settings, "clamav_timeout_seconds", 0.2)

    response = await evidence(
        client, started, provider, files=[("files", ("clean.txt", TEXT, "text/plain"))]
    )

    assert response.status_code == 503
    assert error_type(response) == "malware_scan_unavailable"


async def test_eicar_is_rejected_even_when_clamav_is_unreachable(
    client: AsyncClient, provider, started, monkeypatch
):
    settings = get_settings()
    monkeypatch.setattr(settings, "clamav_host", "127.0.0.1")
    monkeypatch.setattr(settings, "clamav_port", 9)
    monkeypatch.setattr(settings, "clamav_timeout_seconds", 0.2)

    response = await evidence(
        client, started, provider, files=[("files", ("eicar.txt", EICAR, "text/plain"))]
    )

    assert response.status_code == 422
    assert error_type(response) == "malware_detected"


async def test_evidence_is_limited_to_working_states(
    client: AsyncClient, customer, provider, sessionmaker, started
):
    await client.post(f"/api/v1/orders/{started}/review", headers=provider)
    in_review = await evidence(client, started, customer, note="Completion note.")
    await set_status(sessionmaker, started, OrderStatus.DISPUTED)
    disputed = await evidence(client, started, customer, note="Dispute note.")

    assert in_review.status_code == 201
    assert disputed.status_code == 409
    assert error_type(disputed) == "order_not_workable"


async def test_evidence_download_is_for_participants_only(
    client: AsyncClient, sessionmaker, customer, provider, started
):
    created = await evidence(
        client, started, provider, files=[("files", ("banner.png", PNG, "image/png"))]
    )
    url = created.json()["evidence"][0]["files"][0]["url"]
    outsider = await sign_up(client, sessionmaker, "customer", "other@example.com", "+380673333333")

    guest = await client.get(url)
    stranger = await client.get(url, headers=outsider)

    assert guest.status_code == 401
    assert stranger.status_code == 403


async def test_a_file_of_any_type_is_stored_as_an_attachment(
    client: AsyncClient, provider, started
):
    response = await evidence(
        client,
        started,
        provider,
        files=[("files", ("creative.bin", b"\x00\x01\x02binary", "application/octet-stream"))],
    )

    assert response.status_code == 201
    file = response.json()["evidence"][0]["files"][0]
    assert file["content_type"] == "application/octet-stream"
    download = await client.get(file["url"], headers=provider)
    assert download.headers["content-disposition"].startswith("attachment")
