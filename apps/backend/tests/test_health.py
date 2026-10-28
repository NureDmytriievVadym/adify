import asyncio

from httpx import ASGITransport, AsyncClient

from adify_api.main import create_app


def test_liveness_and_openapi_contract():
    asyncio.run(check_contract())


async def check_contract():
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

        schema = (await client.get("/openapi.json")).json()
        assert "/api/v1/health" in schema["paths"]
        assert schema["info"]["title"] == "Adify API"
