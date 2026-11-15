import json
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from adify_api.accounts.schemas import ErrorResponse
from adify_api.api.v1.orders import http_error as order_http_error
from adify_api.auth.dependencies import CurrentAccount, VerifiedAccount
from adify_api.core.db import get_session
from adify_api.orders import service as orders
from adify_api.orders import workflow
from adify_api.orders.service import OrderError
from adify_api.payments import service
from adify_api.payments.mono import MonoClient, MonoError, get_mono, verify_signature
from adify_api.payments.schemas import PaymentResponse
from adify_api.payments.service import PaymentError

router = APIRouter(tags=["Payments"])
logger = logging.getLogger(__name__)

SessionDep = Annotated[AsyncSession, Depends(get_session)]
MonoDep = Annotated[MonoClient | None, Depends(get_mono)]

ERRORS = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Not signed in"},
    status.HTTP_403_FORBIDDEN: {"model": ErrorResponse, "description": "Not allowed"},
    status.HTTP_404_NOT_FOUND: {"model": ErrorResponse, "description": "Not found"},
}


def http_error(error: PaymentError) -> HTTPException:
    detail = [{"loc": ["body"], "msg": error.msg, "type": error.type}]
    return HTTPException(status_code=error.status_code, detail=detail)


@router.post(
    "/orders/{order_id}/payment",
    status_code=status.HTTP_201_CREATED,
    response_model=PaymentResponse,
    responses=ERRORS
    | {
        status.HTTP_409_CONFLICT: {"model": ErrorResponse, "description": "Not awaiting payment"},
        status.HTTP_502_BAD_GATEWAY: {"model": ErrorResponse, "description": "Mono failed"},
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": ErrorResponse,
            "description": "Payments are not configured",
        },
    },
)
async def start_payment(
    order_id: uuid.UUID, account: VerifiedAccount, session: SessionDep, mono: MonoDep
) -> PaymentResponse:
    """FR-038: the customer starts paying; open `page_url` to pay on Mono's page.

    Mono holds the funds until the provider starts work. An open invoice is reused.
    """
    try:
        order = await orders.get_order(session, order_id, account)
        payment = await service.start_payment(session, order, account, mono)
    except OrderError as error:
        raise order_http_error(error) from None
    except PaymentError as error:
        raise http_error(error) from None
    return PaymentResponse.for_viewer(payment, order, account)


@router.get("/orders/{order_id}/payment", response_model=PaymentResponse, responses=ERRORS)
async def get_payment(
    order_id: uuid.UUID, account: CurrentAccount, session: SessionDep, mono: MonoDep
) -> PaymentResponse:
    """The order's latest payment for its participants, synced from Mono while it is open."""
    try:
        order = await orders.get_order(session, order_id, account)
        payment = await service.sync_payment(session, order, mono)
        if mono is not None:
            await workflow.release_stray_hold(session, payment, mono)
    except OrderError as error:
        raise order_http_error(error) from None
    except PaymentError as error:
        raise http_error(error) from None
    return PaymentResponse.for_viewer(payment, order, account)


def _webhook_error(status_code: int, type_: str, msg: str) -> HTTPException:
    detail = [{"loc": ["header", "X-Sign"], "msg": msg, "type": type_}]
    return HTTPException(status_code=status_code, detail=detail)


@router.post("/payments/mono/webhook", status_code=status.HTTP_200_OK, include_in_schema=False)
async def mono_webhook(
    request: Request,
    session: SessionDep,
    mono: MonoDep,
    x_sign: Annotated[str | None, Header(alias="X-Sign")] = None,
) -> Response:
    """Mono's invoice status callback. Unsigned or wrongly signed calls change nothing.

    Mono retries a call that is not answered with 200, so only a missing key answers 503.
    """
    if mono is None:
        raise _webhook_error(503, "payments_unavailable", "Payments are not configured.")
    body = await request.body()
    try:
        signed = verify_signature(body, x_sign, await mono.pubkey())
        if not signed:
            # The key may have been rotated since it was cached.
            signed = verify_signature(body, x_sign, await mono.pubkey(refresh=True))
    except MonoError as error:
        logger.error("Mono public key unavailable: %s", error)
        raise _webhook_error(503, "payments_unavailable", "Mono could not be reached.") from None
    if not signed:
        logger.warning(
            "Ignored a Mono webhook with an invalid signature from %s",
            request.client.host if request.client else "unknown",
        )
        raise _webhook_error(400, "invalid_signature", "The webhook signature is invalid.")
    try:
        data = json.loads(body)
    except ValueError:
        raise _webhook_error(400, "invalid_body", "The webhook body is not JSON.") from None
    payment = await service.apply_invoice_update(session, data) if isinstance(data, dict) else None
    if payment is None:
        logger.warning("Mono webhook for an unknown invoice was ignored")
    else:
        await workflow.release_stray_hold(session, payment, mono)
    return Response(status_code=status.HTTP_200_OK)
