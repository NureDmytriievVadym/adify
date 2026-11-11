"""Development-only stand-in for Mono acquiring, so every developer can pay orders locally.

Docker Compose runs it as ``mono-mock`` and points the backend at it, so no one needs a Mono
token. It speaks the part of the acquiring API Adify uses: hold invoices, invoice status,
finalize, cancel, and the public key. Its payment page has Pay and Decline buttons; the
result is sent to the invoice's ``webHookUrl`` signed with ECDSA-SHA256, as Mono does.
The signing key is generated on start, and invoices live in memory until a restart.
"""

import base64
import html
import json
import os
import uuid
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qs

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

# Kept off the status response, as Mono does not return them either.
PRIVATE_FIELDS = ("redirectUrl", "webHookUrl", "paymentType")


def luhn_valid(number: str) -> bool:
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 12 or len(digits) != len(number.replace(" ", "")):
        return False
    total = 0
    for position, digit in enumerate(reversed(digits)):
        if position % 2:
            digit = digit * 2 - 9 if digit > 4 else digit * 2
        total += digit
    return total % 10 == 0


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _error(status_code: int, text: str) -> HTTPException:
    return HTTPException(status_code, detail={"errCode": str(status_code), "errText": text})


def create_app(
    public_url: str | None = None, webhook_transport: httpx.AsyncBaseTransport | None = None
) -> FastAPI:
    public_url = (public_url or os.environ.get("MONO_MOCK_PUBLIC_URL", "")).rstrip("/")
    key = ec.generate_private_key(ec.SECP256R1())
    pubkey = base64.b64encode(
        key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
    ).decode()
    invoices: dict[str, dict[str, Any]] = {}
    app = FastAPI(title="Mono acquiring mock", docs_url=None, redoc_url=None)

    def invoice_for(invoice_id: str | None) -> dict[str, Any]:
        if not invoice_id or invoice_id not in invoices:
            raise _error(404, "invoice not found")
        return invoices[invoice_id]

    def public(invoice: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in invoice.items() if k not in PRIVATE_FIELDS}

    async def change(invoice: dict[str, Any], status: str, **fields: Any) -> None:
        invoice.update(status=status, modifiedDate=_now(), **fields)
        if not invoice.get("webHookUrl"):
            return
        body = json.dumps(public(invoice)).encode()
        signature = base64.b64encode(key.sign(body, ec.ECDSA(hashes.SHA256()))).decode()
        try:
            async with httpx.AsyncClient(transport=webhook_transport, timeout=5) as client:
                await client.post(
                    invoice["webHookUrl"],
                    content=body,
                    headers={"Content-Type": "application/json", "X-Sign": signature},
                )
        except httpx.HTTPError:
            pass  # Like Mono, a failed delivery leaves the status API as the source of truth.

    @app.get("/api/merchant/pubkey")
    async def get_pubkey(x_token: str | None = Header(default=None)) -> dict[str, str]:
        if not x_token:
            raise _error(403, "forbidden")
        return {"key": pubkey}

    @app.post("/api/merchant/invoice/create")
    async def create_invoice(request: Request, x_token: str | None = Header(default=None)):
        if not x_token:
            raise _error(403, "forbidden")
        data = await request.json()
        amount = data.get("amount")
        if not isinstance(amount, int) or amount <= 0 or data.get("ccy", 980) != 980:
            raise _error(400, "invalid amount or ccy")
        invoice_id = f"mock_{uuid.uuid4().hex[:16]}"
        info = data.get("merchantPaymInfo") or {}
        created = _now()
        invoices[invoice_id] = {
            "invoiceId": invoice_id,
            "status": "created",
            "amount": amount,
            "ccy": 980,
            "createdDate": created,
            "modifiedDate": created,
            "reference": info.get("reference", ""),
            "destination": info.get("destination", ""),
            "redirectUrl": data.get("redirectUrl"),
            "webHookUrl": data.get("webHookUrl"),
            "paymentType": data.get("paymentType", "debit"),
        }
        return {"invoiceId": invoice_id, "pageUrl": f"{public_url}/pay/{invoice_id}"}

    @app.get("/api/merchant/invoice/status")
    async def invoice_status(invoiceId: str, x_token: str | None = Header(default=None)):  # noqa: N803
        if not x_token:
            raise _error(403, "forbidden")
        return public(invoice_for(invoiceId))

    @app.post("/api/merchant/invoice/finalize")
    async def finalize(request: Request, x_token: str | None = Header(default=None)):
        if not x_token:
            raise _error(403, "forbidden")
        data = await request.json()
        invoice = invoice_for(data.get("invoiceId"))
        amount = data.get("amount", invoice["amount"])
        if invoice["status"] != "hold" or not 0 < amount <= invoice["amount"]:
            raise _error(400, "invoice is not on hold or the amount is invalid")
        await change(invoice, "success", finalAmount=amount)
        return {"status": "success"}

    @app.post("/api/merchant/invoice/cancel")
    async def cancel(request: Request, x_token: str | None = Header(default=None)):
        if not x_token:
            raise _error(403, "forbidden")
        data = await request.json()
        invoice = invoice_for(data.get("invoiceId"))
        if invoice["status"] not in ("hold", "success"):
            raise _error(400, "only a held or paid invoice can be canceled")
        await change(invoice, "reversed", finalAmount=0)
        return {"status": "success", "createdDate": _now(), "modifiedDate": invoice["modifiedDate"]}

    def page(invoice: dict[str, Any], error: str | None = None) -> HTMLResponse:
        uah = f"{invoice['amount'] / 100:,.2f}".replace(",", " ")
        open_ = invoice["status"] == "created"
        alert = f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ""
        form = (
            f"""<form method="post">{alert}
            <label for="card">Card number (any number that passes the Luhn check)</label>
            <input id="card" name="card" value="4111 1111 1111 1111" inputmode="numeric">
            <button name="action" value="pay">Pay {uah} UAH</button>
            <button name="action" value="decline" class="decline">Decline</button></form>"""
            if open_
            else f"<p>This invoice is <strong>{html.escape(invoice['status'])}</strong>.</p>"
        )
        return HTMLResponse(
            f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mono payment (development mock)</title><style>
body{{font-family:system-ui,sans-serif;background:#f4f1ec;margin:0;padding:24px 16px}}
main{{max-width:420px;margin:40px auto;background:#fff;border-radius:16px;padding:24px}}
.mock{{background:#fff3cd;padding:8px 12px;border-radius:8px;font-size:14px}}
label{{display:block;margin:16px 0 4px;font-size:14px}}
input{{width:100%;box-sizing:border-box;padding:10px;font-size:16px}}
button{{width:100%;margin-top:12px;padding:12px;font-size:16px;border:0;border-radius:8px;
background:#111;color:#fff;cursor:pointer}}
.decline{{background:#e5e5e5;color:#111}}.error{{color:#b00020}}
</style></head><body><main>
<p class="mock">Development mock of Mono. No money moves.</p>
<h1>{uah} UAH</h1><p>{html.escape(invoice["destination"])}</p>{form}
</main></body></html>""",
            status_code=422 if error else 200,
        )

    @app.get("/pay/{invoice_id}", response_class=HTMLResponse)
    async def payment_page(invoice_id: str) -> HTMLResponse:
        return page(invoice_for(invoice_id))

    @app.post("/pay/{invoice_id}", response_model=None)
    async def submit_payment(invoice_id: str, request: Request) -> Response:
        invoice = invoice_for(invoice_id)
        form = {k: v[0] for k, v in parse_qs((await request.body()).decode()).items()}
        if invoice["status"] == "created":
            if form.get("action") == "decline":
                await change(invoice, "failure", failureReason="Declined on the mock page")
            elif not luhn_valid(form.get("card", "")):
                return page(invoice, "The card number does not pass the Luhn check.")
            else:
                held = invoice["paymentType"] == "hold"
                await change(invoice, "hold" if held else "success")
        return RedirectResponse(invoice["redirectUrl"] or f"/pay/{invoice_id}", status_code=303)

    return app


app = create_app()
