"""Mono acquiring API client (SW-001): hold invoices, invoice status, webhook signatures."""

import base64
import binascii
from decimal import Decimal
from typing import Any

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import load_pem_public_key

from adify_api.core.config import get_settings

UAH = 980
# The signing key changes rarely; it is fetched again when a signature fails to verify.
_pubkey_cache: dict[str, str] = {}


class MonoError(Exception):
    """Mono could not be reached or refused the request."""


def kopiyky(amount: Decimal) -> int:
    return int((amount * 100).to_integral_value())


def verify_signature(body: bytes, signature: str | None, pubkey: str) -> bool:
    """ECDSA-SHA256 over the raw webhook body; ``X-Sign`` is base64 DER, the key base64 PEM."""
    if not signature:
        return False
    try:
        key = load_pem_public_key(base64.b64decode(pubkey))
        if not isinstance(key, ec.EllipticCurvePublicKey):
            return False
        key.verify(base64.b64decode(signature), body, ec.ECDSA(hashes.SHA256()))
    except (InvalidSignature, ValueError, binascii.Error):
        return False
    return True


class MonoClient:
    def __init__(
        self, token: str, base_url: str, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self.base_url = base_url
        self._token = token
        self._transport = transport

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers={"X-Token": self._token},
                timeout=10,
                transport=self._transport,
            ) as client:
                response = await client.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise MonoError(f"Mono is unreachable: {error}") from None
        if response.status_code != 200:
            raise MonoError(f"Mono answered {response.status_code}: {response.text[:200]}")
        try:
            return response.json()
        except ValueError:
            raise MonoError("Mono answered with a body that is not JSON.") from None

    async def create_hold_invoice(
        self,
        *,
        amount: Decimal,
        reference: str,
        destination: str,
        redirect_url: str,
        webhook_url: str | None,
    ) -> dict[str, Any]:
        """FR-038: funds are held, not charged; an unfinalized hold is canceled after 9 days."""
        body: dict[str, Any] = {
            "amount": kopiyky(amount),
            "ccy": UAH,
            "paymentType": "hold",
            "merchantPaymInfo": {"reference": reference, "destination": destination},
            "redirectUrl": redirect_url,
        }
        if webhook_url:
            body["webHookUrl"] = webhook_url
        return await self._request("POST", "/api/merchant/invoice/create", json=body)

    async def finalize_hold(self, invoice_id: str, amount: Decimal) -> dict[str, Any]:
        """FR-039: charge the held funds when the provider starts work."""
        return await self._request(
            "POST",
            "/api/merchant/invoice/finalize",
            json={"invoiceId": invoice_id, "amount": kopiyky(amount)},
        )

    async def cancel_invoice(self, invoice_id: str) -> dict[str, Any]:
        """FR-132: release a hold (or refund a charge); Mono reports the invoice reversed."""
        return await self._request(
            "POST", "/api/merchant/invoice/cancel", json={"invoiceId": invoice_id}
        )

    async def invoice_status(self, invoice_id: str) -> dict[str, Any]:
        return await self._request(
            "GET", "/api/merchant/invoice/status", params={"invoiceId": invoice_id}
        )

    async def pubkey(self, refresh: bool = False) -> str:
        if refresh or self.base_url not in _pubkey_cache:
            _pubkey_cache[self.base_url] = (await self._request("GET", "/api/merchant/pubkey"))[
                "key"
            ]
        return _pubkey_cache[self.base_url]


def get_mono() -> MonoClient | None:
    """FastAPI dependency; ``None`` while no Mono token is configured."""
    settings = get_settings()
    if not settings.mono_token:
        return None
    return MonoClient(settings.mono_token, settings.mono_api_url)
